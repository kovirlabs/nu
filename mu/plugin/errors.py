"""
Keeping Nu running when a plugin has an error.

Copyright (c) 2026 the Nu contributors (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

A plugin's code runs in two ways, and both are covered:

- The core calls a plugin mode's methods (`activate`, `actions`, `api`, ...).
  `PluginErrorHandler.guard_mode` wraps those methods: an error is reported
  and a safe fallback is returned, so e.g. a mode whose `api()` fails just has
  no autocomplete.
- Qt calls the plugin's button handlers, timers and signal handlers. An error
  there reaches `sys.excepthook`; `app.excepthook` first asks
  `handle_uncaught`, which recognises plugin code in the traceback and reports
  the error instead of letting Nu exit.

Either way the learner sees a dialog naming the plugin (rate limited, so a
failing timer can't bury them in dialogs), the details go to the log, and a
plugin that keeps failing is offered to be switched off.
"""

import functools
import logging
import time
import traceback

from ..modes.base import BaseMode
from . import loader

logger = logging.getLogger(__name__)


class PluginError(Exception):
    """
    Raise this from plugin code for an *expected* problem the learner can
    fix, e.g. "Plug in your micro:bit first". Nu shows `message` (and the
    optional `information`) as is, rather than reporting a bug in the plugin.
    """

    def __init__(self, message, information=None):
        super().__init__(message)
        self.message = message
        self.information = information


def _workspace_dir_fallback():
    return BaseMode.workspace_dir()


#: Mode methods the core calls, and what to return if a plugin's version
#: fails (None means return None).
GUARDED_MODE_METHODS = {
    "activate": None,
    "deactivate": None,
    "ensure_state": None,
    "stop": None,
    "actions": list,
    "api": list,
    "workspace_dir": _workspace_dir_fallback,
    "find_devices": list,
    "device_changed": None,
    "open_file": None,
    "remove_repl": None,
    "remove_plotter": None,
    "remove_fs": None,
}


class _PluginState:
    def __init__(self):
        self.errors = 0
        self.last_dialog = None
        self.offered_switch_off = False
        self.seen = set()


class PluginErrorHandler:
    """
    Reports errors in plugin code to the learner and the log, so Nu keeps
    running. There is one per Host.
    """

    #: Minimum seconds between error dialogs for the same plugin.
    DIALOG_INTERVAL = 30
    #: After this many errors, offer to switch the plugin off.
    SWITCH_OFF_AFTER = 3

    def __init__(self, host, clock=time.monotonic):
        self._host = host
        self._clock = clock
        self._states = {}
        self._dialog_open = False

    def _state(self, plugin):
        return self._states.setdefault(id(plugin), _PluginState())

    def error_count(self, plugin):
        """How many unexpected errors `plugin` has had this session."""
        return self._state(plugin).errors

    # --- working out whose code failed ---

    def _plugin_modules(self):
        """Map each loaded plugin's top-level module name to the plugin."""
        modules = {}
        for plugin in self._host.plugins:
            classes = [type(plugin)] + [
                type(mode) for mode in self._host._modes_of(plugin)
            ]
            for cls in classes:
                top = cls.__module__.split(".")[0]
                if top not in ("mu", "builtins", "__main__"):
                    modules[top] = plugin
        return modules

    def owner(self, tb):
        """
        The plugin whose code appears in traceback `tb` (the innermost one,
        if several), or None if it's all core code. A frame counts as the
        plugin's if it's in the plugin's modules, or is a method called on
        one of the plugin's modes (e.g. inherited MicroPythonMode code).
        """
        modules = self._plugin_modules()
        modes = {
            id(mode): plugin
            for plugin in self._host.plugins
            for mode in self._host._modes_of(plugin)
        }
        found = None
        for frame, _ in traceback.walk_tb(tb):
            top = frame.f_globals.get("__name__", "").split(".")[0]
            plugin = modules.get(top)
            if plugin is None:
                plugin = modes.get(id(frame.f_locals.get("self")))
            if plugin is not None:
                found = plugin
        return found

    def handle_uncaught(self, exc_type, exc, tb):
        """
        Called from `app.excepthook`. If plugin code raised the exception,
        report it and return True (Nu carries on); otherwise return False.
        """
        if issubclass(exc_type, KeyboardInterrupt):
            return False
        try:
            plugin = self.owner(tb)
        except Exception:
            logger.exception("Couldn't work out where an error came from")
            return False
        if plugin is None:
            return False
        if exc is None:
            exc = exc_type()
        self.report(plugin, exc, tb)
        return True

    # --- guarding the calls the core makes into plugin modes ---

    def guard_mode(self, mode, plugin):
        """Wrap `mode`'s core-called methods so errors are reported."""
        for name, fallback in GUARDED_MODE_METHODS.items():
            method = getattr(mode, name, None)
            if callable(method):
                setattr(mode, name, self._guarded(plugin, method, name, fallback))

    def _guarded(self, plugin, method, name, fallback):
        @functools.wraps(method)
        def guarded(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except (Exception, SystemExit) as ex:
                self.report(plugin, ex, ex.__traceback__, where=name)
                return fallback() if fallback else None

        return guarded

    # --- telling the learner ---

    def report(self, plugin, exc, tb=None, where=None):
        """
        Tell the learner (and the log) that `plugin` raised `exc`. This never
        raises.
        """
        try:
            if isinstance(exc, PluginError):
                self._report_expected(plugin, exc)
            else:
                self._report_unexpected(plugin, exc, tb, where)
        except Exception:
            logger.exception("Failed to report an error in plugin %s", plugin)

    def _report_expected(self, plugin, exc):
        logger.info("Plugin %s: %s", plugin.name, exc.message)
        if self._dialog_open:
            self._host.show_status(exc.message)
            return
        self._show_dialog(
            self._host.show_message, exc.message, exc.information, "Information"
        )

    def _report_unexpected(self, plugin, exc, tb, where):
        state = self._state(plugin)
        state.errors += 1
        signature = (type(exc).__name__, str(exc), where)
        location = " in {}()".format(where) if where else ""
        if signature in state.seen:
            logger.error(
                "Plugin %s failed again%s: %s: %s (error #%d)",
                plugin.name,
                location,
                type(exc).__name__,
                exc,
                state.errors,
            )
        else:
            state.seen.add(signature)
            logger.error(
                "Plugin %s failed%s",
                plugin.name,
                location,
                exc_info=(type(exc), exc, tb or exc.__traceback__),
            )

        now = self._clock()
        recently = (
            state.last_dialog is not None
            and now - state.last_dialog < self.DIALOG_INTERVAL
        )
        if self._dialog_open or recently:
            self._host.show_status(
                _("The {} plugin had another problem (see the log).").format(
                    plugin.name
                )
            )
            return
        state.last_dialog = now

        plugin_id = self._plugin_id(plugin)
        if (
            state.errors >= self.SWITCH_OFF_AFTER
            and plugin_id
            and not state.offered_switch_off
        ):
            state.offered_switch_off = True
            message = _("The {} plugin keeps having problems.").format(plugin.name)
            information = _(
                "Nu is still running. Switch the plugin off? It won't be "
                "loaded the next time Nu starts. (You can switch it back on "
                "by removing it from disabled_plugins in settings.json.)"
            )
            if self._show_dialog(self._host.confirm, message, information, "Question"):
                loader.set_plugin_enabled(plugin_id, False)
                self._host.show_status(
                    _("The {} plugin is switched off from the next start.").format(
                        plugin.name
                    )
                )
            return

        message = _(
            "The {} plugin had a problem and stopped what it was doing."
        ).format(plugin.name)
        information = _(
            "Nu is still running, so you can carry on. If it keeps happening, "
            "tell the plugin's author:\n\n{}: {}\n\nThe full details are in "
            "Nu's log."
        ).format(type(exc).__name__, exc)
        self._show_dialog(self._host.show_message, message, information, "Warning")

    def _show_dialog(self, show, message, information, icon):
        # A modal dialog runs a nested event loop, so a plugin timer can fail
        # again while it's open; those errors go to the status bar instead.
        self._dialog_open = True
        try:
            return show(message, information, icon)
        finally:
            self._dialog_open = False

    def _plugin_id(self, plugin):
        for record in self._host.plugin_records:
            if record.plugin is plugin:
                return record.id
        return None


# The handler `app.excepthook` consults; set by `install`.
_active = None


def install(handler):
    """Make `handler` the one `app.excepthook` consults."""
    global _active
    _active = handler


def handle_uncaught(exc_type, exc, tb):
    """
    For `app.excepthook`: return True if the exception came from a plugin
    and has been reported, so Nu should carry on.
    """
    if _active is None:
        return False
    try:
        return _active.handle_uncaught(exc_type, exc, tb)
    except Exception:
        logger.exception("Plugin error handling failed")
        return False
