# -*- coding: utf-8 -*-
"""
Tests for the plugin Host façade and PluginSettings.
"""

import logging
from unittest import mock

import pytest
from PyQt6.QtWidgets import QMessageBox

from mu import settings
from mu.app import setup_modes
from mu.plugin import PLUGIN_API_VERSION, Host, ModePlugin, Plugin, PluginSettings
from mu.modes.base import BaseMode


class AlphaMode(BaseMode):
    name = "Alpha"
    short_name = "alpha"


class BetaMode(BaseMode):
    name = "Beta"
    short_name = "beta"


class AlphaPlugin(ModePlugin):
    name = "Alpha plugin"
    api_version = PLUGIN_API_VERSION
    mode = AlphaMode


@pytest.fixture
def host():
    return Host(mock.MagicMock(), mock.MagicMock())


def test_register_mode(host):
    """
    A registered mode is built with the editor and view, knows its host, and
    shows up in `modes` under its short_name.
    """
    mode = host.register_mode(AlphaMode)
    assert isinstance(mode, AlphaMode)
    assert mode.editor is host._editor
    assert mode.view is host._view
    assert mode.host is host
    assert host.modes == {"alpha": mode}


def test_modes_is_a_copy(host):
    host.register_mode(AlphaMode)
    host.modes.clear()
    assert "alpha" in host.modes


def test_register_mode_rejects_duplicates(host):
    host.register_mode(AlphaMode)

    class Imposter(BaseMode):
        short_name = "alpha"

    with pytest.raises(ValueError, match="already registered"):
        host.register_mode(Imposter)


@pytest.mark.parametrize("not_a_mode", [object, AlphaMode(None, None), "alpha"])
def test_register_mode_rejects_non_modes(host, not_a_mode):
    with pytest.raises(TypeError):
        host.register_mode(not_a_mode)


def test_load_plugin(host):
    plugin = AlphaPlugin()
    assert host.load_plugin(plugin) is True
    assert host.plugins == [plugin]
    assert "alpha" in host.modes


def test_load_plugin_skips_incompatible(host, caplog):
    """
    An incompatible plugin is logged and skipped without its register()
    ever running.
    """

    class FuturePlugin(AlphaPlugin):
        name = "Future"
        api_version = "99.0"
        register = mock.MagicMock()

    with caplog.at_level(logging.WARNING):
        assert host.load_plugin(FuturePlugin()) is False
    FuturePlugin.register.assert_not_called()
    assert host.plugins == []
    assert host.modes == {}
    assert "Skipping plugin Future" in caplog.text


def test_load_plugin_without_api_version(host):
    class Lazy(Plugin):
        pass

    assert host.load_plugin(Lazy()) is False


def test_load_plugin_isolates_failures(host, caplog):
    """
    A plugin whose register() raises is skipped, and modes it registered
    before failing are removed (and stopped) again. Other modes are kept.
    """
    host.register_mode(BetaMode)

    class Broken(Plugin):
        name = "Broken"
        api_version = PLUGIN_API_VERSION

        def register(self, host):
            self.mode = host.register_mode(AlphaMode)
            self.mode.stop = mock.MagicMock()
            raise RuntimeError("boom")

    broken = Broken()
    with caplog.at_level(logging.ERROR):
        assert host.load_plugin(broken) is False
    assert list(host.modes) == ["beta"]
    assert host.plugins == []
    broken.mode.stop.assert_called_once_with()
    assert "Plugin Broken failed to register" in caplog.text
    # The failed plugin's mode name is free to use again.
    assert host.load_plugin(AlphaPlugin()) is True


def test_load_plugin_survives_a_failing_stop(host):
    class Broken(Plugin):
        api_version = PLUGIN_API_VERSION

        def register(self, host):
            mode = host.register_mode(AlphaMode)
            mode.stop = mock.MagicMock(side_effect=RuntimeError("stop"))
            raise RuntimeError("boom")

    assert host.load_plugin(Broken()) is False
    assert host.modes == {}


def test_unload_plugin(host):
    """
    Unloading calls unregister() and removes only that plugin's modes.
    """
    core = host.register_mode(BetaMode)
    plugin = AlphaPlugin()
    plugin.unregister = mock.MagicMock()
    host.load_plugin(plugin)
    host.unload_plugin(plugin)
    plugin.unregister.assert_called_once_with(host)
    assert host.modes == {"beta": core}
    assert host.plugins == []


def test_unload_plugin_survives_a_failing_unregister(host, caplog):
    plugin = AlphaPlugin()
    plugin.unregister = mock.MagicMock(side_effect=RuntimeError("boom"))
    host.load_plugin(plugin)
    with caplog.at_level(logging.ERROR):
        host.unload_plugin(plugin)
    assert host.modes == {}
    assert host.plugins == []
    assert "failed to unregister" in caplog.text


def test_unload_plugin_that_never_loaded(host):
    host.unload_plugin(AlphaPlugin())
    assert host.plugins == []


def test_show_message(host):
    host.show_message("Hello", "More", icon="Information")
    host._view.show_message.assert_called_once_with("Hello", "More", "Information")


@pytest.mark.parametrize(
    "button, expected",
    [(QMessageBox.StandardButton.Ok, True), (QMessageBox.StandardButton.Cancel, False)],
)
def test_confirm(host, button, expected):
    host._view.show_confirmation.return_value = button
    assert host.confirm("Sure?") is expected
    host._view.show_confirmation.assert_called_once_with("Sure?", None, None)


def test_show_status(host):
    host.show_status("Flashed", duration=2)
    host._editor.show_status_message.assert_called_once_with("Flashed", 2)


def test_current_tab_details(host):
    tab = host._view.current_tab
    tab.text.return_value = "print('hi')"
    tab.path = "/tmp/hi.py"
    assert host.current_text() == "print('hi')"
    assert host.current_path() == "/tmp/hi.py"


def test_current_tab_details_with_no_tab(host):
    host._view.current_tab = None
    assert host.current_text() is None
    assert host.current_path() is None


def test_workspace_dir(host):
    with mock.patch.object(BaseMode, "workspace_dir", return_value="/ws"):
        assert host.workspace_dir() == "/ws"


def test_open_directory(host):
    host.open_directory("/ws")
    host._view.open_directory_from_os.assert_called_once_with("/ws")


def test_logger(host):
    assert host.logger("microbit").name == "mu.plugins.microbit"


def test_settings_namespaced_and_persisted():
    """
    Plugin settings live under settings["plugins"][namespace], marked dirty so
    they are saved, and namespaces don't see each other's values.
    """
    store = settings.UserSettings()
    one = PluginSettings("one", store)
    two = PluginSettings("two", store)
    assert one.get("port") is None
    assert one.get("port", "auto") == "auto"
    assert "port" not in one
    one.set("port", "COM3")
    two.set("port", "/dev/ttyACM0")
    assert one.get("port") == "COM3"
    assert "port" in one
    assert store["plugins"] == {
        "one": {"port": "COM3"},
        "two": {"port": "/dev/ttyACM0"},
    }
    assert "plugins" in store._dirty


def test_host_settings_uses_user_settings(host):
    plugin_settings = host.settings("microbit")
    assert plugin_settings.namespace == "microbit"
    assert plugin_settings._store is settings.settings


def test_setup_modes_registers_builtins_through_a_host():
    """
    The built-in modes go through the plugin Host, keyed as before.
    """
    with mock.patch("mu.app.load_plugins", return_value=[]):
        modes = setup_modes(mock.MagicMock(), mock.MagicMock())
    assert list(modes) == ["python", "circuitpython", "debugger", "pygamezero"]
    hosts = {mode.host for mode in modes.values()}
    assert len(hosts) == 1
    assert isinstance(hosts.pop(), Host)


def test_setup_modes_adds_plugin_modes():
    """
    Plugins are loaded into the same Host after the built-in modes, and what
    happened to each is kept on the Host.
    """

    def load_plugins(host):
        host.load_plugin(AlphaPlugin())
        return ["record"]

    with mock.patch("mu.app.load_plugins", side_effect=load_plugins):
        modes = setup_modes(mock.MagicMock(), mock.MagicMock())
    assert list(modes)[-1] == "alpha"
    assert modes["alpha"].host.plugin_records == ["record"]
