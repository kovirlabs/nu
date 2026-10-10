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

from PyQt6.QtWidgets import QMessageBox

from .. import settings
from ..modes.base import BaseMode
from .base import PLUGIN_API_VERSION, check_compatible

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
        self._plugins = []
        self._loading = None  # the plugin whose register() is running
        #: What happened to each discovered plugin (mu.plugin.loader.PluginRecord),
        #: filled in at startup by app.setup_modes.
        self.plugin_records = []

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
        if plugin in self._plugins:
            self._plugins.remove(plugin)
        logger.info("Unloaded plugin %s", name)

    def _remove_modes_of(self, plugin):
        for short_name, owner in list(self._owners.items()):
            if owner is plugin:
                mode = self._modes.pop(short_name)
                del self._owners[short_name]
                try:
                    mode.stop()
                except Exception:
                    logger.exception("Mode %s failed to stop", short_name)

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
        self._modes[short_name] = mode
        self._owners[short_name] = self._loading
        return mode

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

    # --- housekeeping ---

    def settings(self, namespace):
        """Settings that persist between sessions, private to `namespace`."""
        return PluginSettings(namespace)

    def logger(self, name):
        """A logger whose output goes to Nu's log file, as "mu.plugins.<name>"."""
        return logging.getLogger("mu.plugins." + name)
