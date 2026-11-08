"""
The Host: the façade the core hands to plugins.

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
"""

import logging
import os

from PyQt6.QtWidgets import QMessageBox

from .. import resources, settings
from ..modes.api import PI_APIS, PYTHON3_APIS, SHARED_APIS
from ..modes.base import BaseMode
from ..virtual_environment import venv
from .base import PLUGIN_API_VERSION, check_compatible
from .errors import PluginErrorHandler

logger = logging.getLogger(__name__)


class PluginSettings:
    """
    A plugin's own corner of the user settings, persisted with them.

    Values live under `settings["plugins"][namespace]`, so plugins can't clash
    with each other or with the core's keys. Values must be JSON-serialisable.
    """

    def __init__(self, namespace, store=None):
        self.namespace = namespace
        self._store = settings.settings if store is None else store

    def _values(self):
        return dict(self._store.get("plugins", {}).get(self.namespace, {}))

    def get(self, key, default=None):
        """Return the value stored under `key`, or `default`."""
        return self._values().get(key, default)

    def set(self, key, value):
        """Store `value` under `key`; it is saved with the user's settings."""
        # Rebuild the nested dicts rather than mutating them in place, so the
        # settings object marks "plugins" as changed and saves it.
        values = self._values()
        values[key] = value
        plugins = dict(self._store.get("plugins", {}))
        plugins[self.namespace] = values
        self._store["plugins"] = plugins

    def __contains__(self, key):
        return key in self._values()


class Host:
    """
    The only supported way for a plugin to reach the editor.

    The core is free to change behind this class; a plugin should never need
    `mu.logic`, `mu.interface` or `mu.modes` internals. One Host is created per
    editor window and handed to every plugin's `register`/`unregister`.
    """

    #: The plugin API version this core provides.
    api_version = PLUGIN_API_VERSION

    def __init__(self, editor, view):
        self._editor = editor
        self._view = view
        self._modes = {}  # short_name -> mode instance
        self._owners = {}  # short_name -> owning plugin (None for the core)
        self._image_dirs = []  # (owning plugin or None, folder) pairs
        self._runner = None  # the program started by run_program
        self._plugins = []
        self._loading = None  # the plugin whose register() is running
        #: What happened to each discovered plugin (mu.plugin.loader.PluginRecord),
        #: filled in at startup by app.setup_modes.
        self.plugin_records = []
        # Reports errors in plugin code so they don't crash Nu (see errors.py).
        self._error_handler = PluginErrorHandler(self)

    # --- plugin lifecycle (used by the core) ---

    @property
    def modes(self):
        """The registered modes, as a {short_name: mode} dict (a copy)."""
        return dict(self._modes)

    @property
    def plugins(self):
        """The successfully loaded plugins, in load order (a copy)."""
        return list(self._plugins)

    def load_plugin(self, plugin):
        """
        Check `plugin` is compatible and call its `register`. Return True if
        it loaded.

        This never raises: an incompatible plugin, or one whose `register`
        fails, is logged and skipped, and any modes it registered before
        failing are removed again.
        """
        name = getattr(plugin, "name", repr(plugin))
        reason = check_compatible(getattr(plugin, "api_version", None))
        if reason:
            logger.warning("Skipping plugin %s: %s", name, reason)
            return False
        self._loading = plugin
        try:
            plugin.register(self)
        except Exception:
            logger.exception("Plugin %s failed to register; skipping it", name)
            self._remove_modes_of(plugin)
            self._remove_images_of(plugin)
            return False
        finally:
            self._loading = None
        self._plugins.append(plugin)
        logger.info("Loaded plugin %s", name)
        return True

    def unload_plugin(self, plugin):
        """
        Call `plugin.unregister` and remove the modes it registered. Errors in
        `unregister` are logged, not raised.
        """
        name = getattr(plugin, "name", repr(plugin))
        try:
            plugin.unregister(self)
        except Exception:
            logger.exception("Plugin %s failed to unregister", name)
        self._remove_modes_of(plugin)
        self._remove_images_of(plugin)
        if plugin in self._plugins:
            self._plugins.remove(plugin)
        logger.info("Unloaded plugin %s", name)

    def _modes_of(self, plugin):
        """The mode instances `plugin` registered."""
        return [
            self._modes[name] for name, owner in self._owners.items() if owner is plugin
        ]

    def _remove_modes_of(self, plugin):
        for short_name, owner in list(self._owners.items()):
            if owner is plugin:
                mode = self._modes.pop(short_name)
                del self._owners[short_name]
                try:
                    mode.stop()
                except Exception:
                    logger.exception("Mode %s failed to stop", short_name)

    def _remove_images_of(self, plugin):
        for owner, directory in list(self._image_dirs):
            if owner is plugin:
                resources.unregister_image_dir(directory)
                self._image_dirs.remove((owner, directory))

    # --- registration (call from Plugin.register) ---

    def register_mode(self, mode_class):
        """
        Create an instance of `mode_class` (a `mu.plugin.Mode` subclass) and
        make it available in the editor. Its `short_name` must be unique.
        Returns the new mode instance, whose `host` attribute is this Host.
        """
        if not (isinstance(mode_class, type) and issubclass(mode_class, BaseMode)):
            raise TypeError("{!r} is not a Mode subclass".format(mode_class))
        short_name = mode_class.short_name
        if short_name in self._modes:
            raise ValueError(
                "A mode called {!r} is already registered".format(short_name)
            )
        mode = mode_class(self._editor, self._view)
        mode.host = self
        if self._loading is not None:
            # A plugin's mode: errors in the methods the core calls are
            # reported instead of crashing Nu.
            self._error_handler.guard_mode(mode, self._loading)
        self._modes[short_name] = mode
        self._owners[short_name] = self._loading
        return mode

    def register_images(self, directory):
        """
        Make the images in `directory` (a str or os.PathLike) available by
        name, after Nu's own: a mode's `icon`, an action's `name` and
        `update_action(icon=...)` then find `name.svg` / `name.png` there.

        Every image name must be new. If one matches an image Nu or another
        plugin already has, this raises ValueError naming it, so the plugin
        fails to register and is skipped. The images are removed again when
        the plugin unloads.
        """
        resources.register_image_dir(directory)
        self._image_dirs.append((self._loading, directory))

    # --- talking to the learner ---

    def show_message(self, message, information=None, icon=None):
        """
        Show a modal message. `icon` is one of "NoIcon", "Question",
        "Information", "Warning" (the default) or "Critical".
        """
        self._view.show_message(message, information, icon)

    def confirm(self, message, information=None, icon=None):
        """
        Ask the learner to confirm with OK/Cancel; return True for OK. `icon`
        is as for `show_message`.
        """
        result = self._view.show_confirmation(message, information, icon)
        return result == QMessageBox.StandardButton.Ok

    def show_status(self, message, duration=5):
        """Show `message` in the status bar for `duration` seconds."""
        self._editor.show_status_message(message, duration)

    # --- the editor's state ---

    def current_text(self):
        """The text in the current tab, or None if no tab is open."""
        tab = self._view.current_tab
        return tab.text() if tab else None

    def current_path(self):
        """The file path of the current tab, or None if unsaved or no tab."""
        tab = self._view.current_tab
        return tab.path if tab else None

    def workspace_dir(self):
        """The learner's workspace directory (where files are saved)."""
        return BaseMode.workspace_dir()

    def open_directory(self, path):
        """Open `path` in the operating system's file manager."""
        self._view.open_directory_from_os(path)

    def save_current(self):
        """
        Save the current tab, asking the learner for a file name if it has
        none yet. Return its path, or None if there's no tab or the learner
        cancelled naming it.
        """
        tab = self._view.current_tab
        if tab is None:
            return None
        if tab.path is None:
            self._editor.save()  # asks for a name
        if tab.path and tab.isModified():
            self._editor.save_tab_to_file(tab)
        return tab.path

    def update_action(self, name, display_name=None, description=None, icon=None):
        """
        Change the toolbar button for the current mode's action `name`: its
        label, its tooltip and/or its icon (an image name, looked up like a
        mode's icons). Anything not given is left as it is. Raises ValueError
        if there's no such button (e.g. another mode is current).
        """
        slot = self._view.button_bar.slots.get(name)
        if slot is None:
            raise ValueError("There's no toolbar button called {!r}".format(name))
        if icon is not None:
            slot.setIcon(resources.load_icon(icon))
        if display_name is not None:
            slot.setText(display_name)
        if description is not None:
            slot.setToolTip(description)

    # --- running the learner's program ---

    def run_program(self, path, python_args=None, interactive=False):
        """
        Run the Python program at `path` the way the Run button does: with the
        learner's Python environment and environment variables, from the
        program's folder, its output in the output pane. `python_args` go to
        Python before the program (e.g. `["-m", "pgzero"]`); `interactive`
        leaves a Python prompt open when it finishes. Return True if it
        started. Save it first (see `save_current`).
        """
        self._runner = self._view.add_python3_runner(
            interpreter=venv.interpreter,
            script_name=path,
            working_directory=os.path.dirname(path),
            interactive=interactive,
            envars=self._editor.envars,
            python_args=python_args,
        )
        if self._runner is None:
            return False
        self._runner.process.waitForStarted()
        return True

    def stop_program(self):
        """Stop the program `run_program` started, and close its pane."""
        if self._runner:
            self._runner.stop_process()
            self._runner = None
        self._view.remove_python_runner()

    def python_apis(self):
        """
        The autocomplete and call tip entries of Nu's Python 3 mode (Python's
        built-ins and standard library, and common Raspberry Pi libraries),
        as a new list a mode's `api()` can add its own to.
        """
        return SHARED_APIS + PYTHON3_APIS + PI_APIS

    def shared_apis(self):
        """
        The autocomplete and call tip entries every Python has, MicroPython
        and CircuitPython included (built-ins, and str, list and dict
        methods), as a new list a MicroPython-family mode's `api()` can add
        its board's own to.
        """
        return list(SHARED_APIS)

    @property
    def plotter_available(self):
        """
        True if Nu can show the plotter (the optional PyQt6-Charts package is
        installed). Offer a Plotter button (`MicroPythonMode.toggle_plotter`)
        only when it is.
        """
        # Read when asked, not at import: the panes module is the one place
        # that knows whether Qt Charts imported.
        from ..interface import panes

        return panes.CHARTS

    # --- housekeeping ---

    def settings(self, namespace):
        """Settings that persist between sessions, private to `namespace`."""
        return PluginSettings(namespace)

    def logger(self, name):
        """A logger whose output goes to Nu's log file, as "mu.plugins.<name>"."""
        return logging.getLogger("mu.plugins." + name)
