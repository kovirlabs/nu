# -*- coding: utf-8 -*-
"""
Tests for the plugin Host façade and PluginSettings.
"""

import logging
from unittest import mock

import pytest
from PyQt6.QtWidgets import QMessageBox

from mu import resources, settings
from mu.virtual_environment import venv
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
    assert list(modes) == ["python", "debugger"]
    hosts = {mode.host for mode in modes.values()}
    assert len(hosts) == 1
    assert isinstance(hosts.pop(), Host)


def test_setup_modes_gives_the_editor_the_host():
    """The editor reaches the plugin records (for the Plugins tab) this way."""
    editor = mock.MagicMock()
    with mock.patch("mu.app.load_plugins", return_value=[]):
        modes = setup_modes(editor, mock.MagicMock())
    assert editor.plugin_host is modes["python"].host


def test_describe_plugins(host):
    """The Plugins tab's rows, with the names of each plugin's modes."""
    from mu.plugin import loader

    plugin = AlphaPlugin()
    host.load_plugin(plugin)
    host.plugin_records = [
        loader.PluginRecord("alpha", "package", "a 1", loader.LOADED, plugin=plugin),
        loader.PluginRecord("off", "folder", "/off.py", loader.DISABLED),
    ]
    with mock.patch.object(settings, "settings", settings.UserSettings()):
        rows = host.describe_plugins()
    assert [(r["id"], r["modes"]) for r in rows] == [("alpha", ["Alpha"]), ("off", [])]


def test_plugins_folder(host, tmp_path, monkeypatch):
    """Where drop-in plugins go, for the Plugins tab's button."""
    from mu.plugin import loader

    monkeypatch.setattr(loader, "DROPIN_DIR", str(tmp_path / "p"))
    assert host.plugins_folder == str(tmp_path / "p")


def test_set_plugin_enabled(host):
    """
    Switching a plugin back on forgets its errors this session, so if it
    keeps failing Nu offers to switch it off again.
    """
    from mu.plugin import loader

    plugin = AlphaPlugin()
    host.load_plugin(plugin)
    host.plugin_records = [
        loader.PluginRecord("alpha", "package", "a 1", loader.LOADED, plugin=plugin),
        loader.PluginRecord("gone", "folder", "/gone.py", loader.DISABLED),
    ]
    store = settings.UserSettings()
    handler = host._error_handler
    handler._state(plugin).errors = 5
    handler._state(plugin).offered_switch_off = True
    with mock.patch.object(settings, "settings", store):
        host.set_plugin_enabled("alpha", False)
        assert handler.error_count(plugin) == 5  # switching off forgets nothing
        host.set_plugin_enabled("alpha", True)
        host.set_plugin_enabled("gone", True)  # not loaded: nothing to forget
    assert handler.error_count(plugin) == 0
    assert handler._state(plugin).offered_switch_off is False
    assert loader.disabled_plugins(store) == set()


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


@pytest.fixture
def image_dir(tmp_path):
    """A folder with one plugin image; never left registered after a test."""
    directory = tmp_path / "images"
    directory.mkdir()
    (directory / "rocket.png").write_bytes(b"")
    yield directory
    resources.unregister_image_dir(directory)


def test_register_images(host, image_dir):
    """
    Images a plugin registers are found by name until the plugin unloads.
    """

    class Pictured(Plugin):
        name = "Pictured"
        api_version = PLUGIN_API_VERSION

        def register(self, host):
            host.register_images(image_dir)

    plugin = Pictured()
    assert host.load_plugin(plugin)
    assert resources.plugin_image_dirs() == [str(image_dir)]
    assert resources.image_path("rocket") == str(image_dir / "rocket")
    host.unload_plugin(plugin)
    assert resources.plugin_image_dirs() == []


def test_register_images_clash_skips_the_plugin(host, tmp_path, caplog):
    """
    A plugin whose images clash with the core's fails to register, so it is
    logged and skipped with its modes rolled back, and its images aren't
    left behind.
    """
    good = tmp_path / "good"
    good.mkdir()
    (good / "rocket.png").write_bytes(b"")
    clashing = tmp_path / "clashing"
    clashing.mkdir()
    (clashing / "run.png").write_bytes(b"")

    class Clashing(ModePlugin):
        name = "Clashing"
        api_version = PLUGIN_API_VERSION
        mode = AlphaMode

        def register(self, host):
            super().register(host)
            host.register_images(good)
            host.register_images(clashing)

    with caplog.at_level(logging.ERROR):
        assert host.load_plugin(Clashing()) is False
    assert "'run'" in caplog.text
    assert host.modes == {}
    assert resources.plugin_image_dirs() == []


def test_register_images_from_the_core_are_kept(host, image_dir):
    """
    Images registered outside a plugin's register() belong to the core and
    aren't removed when a plugin unloads.
    """
    host.register_images(image_dir)
    host.load_plugin(AlphaPlugin())
    host.unload_plugin(host.plugins[0])
    assert resources.plugin_image_dirs() == [str(image_dir)]


# --- running the learner's program ---


def test_save_current_no_tab(host):
    host._view.current_tab = None
    assert host.save_current() is None
    host._editor.save.assert_not_called()


def test_save_current_saved_and_unchanged(host):
    tab = host._view.current_tab
    tab.path = "/work/game.py"
    tab.isModified.return_value = False
    assert host.save_current() == "/work/game.py"
    host._editor.save.assert_not_called()
    host._editor.save_tab_to_file.assert_not_called()


def test_save_current_saves_changes(host):
    tab = host._view.current_tab
    tab.path = "/work/game.py"
    tab.isModified.return_value = True
    assert host.save_current() == "/work/game.py"
    host._editor.save_tab_to_file.assert_called_once_with(tab)


def test_save_current_names_an_unsaved_tab(host):
    """
    An unnamed tab is saved through the editor, which asks for a name.
    """
    tab = host._view.current_tab
    tab.path = None

    def save():
        tab.path = "/work/new.py"
        tab.isModified.return_value = False

    host._editor.save.side_effect = save
    assert host.save_current() == "/work/new.py"
    host._editor.save_tab_to_file.assert_not_called()


def test_save_current_naming_cancelled(host):
    host._view.current_tab.path = None
    assert host.save_current() is None
    host._editor.save.assert_called_once_with()


def test_run_program(host):
    """
    The program runs in the learner's environment, from its own folder, with
    the learner's environment variables, its output in the output pane.
    """
    host._editor.envars = [["name", "value"]]
    runner = host._view.add_python3_runner.return_value
    with mock.patch.object(venv, "interpreter", "/venv/bin/python"):
        assert host.run_program("/work/game.py", python_args=["-m", "pgzero"])
    host._view.add_python3_runner.assert_called_once_with(
        interpreter="/venv/bin/python",
        script_name="/work/game.py",
        working_directory="/work",
        interactive=False,
        envars=[["name", "value"]],
        python_args=["-m", "pgzero"],
    )
    runner.process.waitForStarted.assert_called_once_with()


def test_run_program_interactive(host):
    with mock.patch.object(venv, "interpreter", "/venv/bin/python"):
        host.run_program("/work/game.py", interactive=True)
    kwargs = host._view.add_python3_runner.call_args.kwargs
    assert kwargs["interactive"] is True
    assert kwargs["python_args"] is None


def test_run_program_not_started(host):
    host._view.add_python3_runner.return_value = None
    assert host.run_program("/work/game.py") is False


def test_stop_program(host):
    runner = host._view.add_python3_runner.return_value
    host.run_program("/work/game.py")
    host.stop_program()
    runner.stop_process.assert_called_once_with()
    host._view.remove_python_runner.assert_called_once_with()
    host.stop_program()  # nothing running: just tidies the pane
    runner.stop_process.assert_called_once_with()
    assert host._view.remove_python_runner.call_count == 2


def test_update_action(host):
    slot = mock.MagicMock()
    host._view.button_bar.slots = {"play": slot}
    with mock.patch("mu.plugin.host.resources.load_icon") as load_icon:
        host.update_action(
            "play", display_name="Stop", description="Stop it.", icon="stop"
        )
    load_icon.assert_called_once_with("stop")
    slot.setIcon.assert_called_once_with(load_icon.return_value)
    slot.setText.assert_called_once_with("Stop")
    slot.setToolTip.assert_called_once_with("Stop it.")


def test_update_action_changes_only_whats_given(host):
    slot = mock.MagicMock()
    host._view.button_bar.slots = {"play": slot}
    host.update_action("play", display_name="Go")
    slot.setText.assert_called_once_with("Go")
    slot.setIcon.assert_not_called()
    slot.setToolTip.assert_not_called()


def test_update_action_unknown_button(host):
    host._view.button_bar.slots = {}
    with pytest.raises(ValueError, match="'play'"):
        host.update_action("play", display_name="Go")


def test_python_apis(host):
    """
    Plugins can build on the autocomplete entries of Nu's Python 3 mode.
    """
    from mu.modes.api import PI_APIS, PYTHON3_APIS, SHARED_APIS

    apis = host.python_apis()
    assert apis == SHARED_APIS + PYTHON3_APIS + PI_APIS
    apis.append("mine")
    assert "mine" not in host.python_apis()


def test_shared_apis(host):
    """
    A MicroPython-family mode builds on the entries every Python shares (not
    the Python 3 standard library's), as a new list each time.
    """
    from mu.modes.api import SHARED_APIS

    apis = host.shared_apis()
    assert apis == SHARED_APIS
    apis.append("mine")
    assert "mine" not in host.shared_apis()


@pytest.mark.parametrize("charts", [True, False])
def test_plotter_available(host, charts):
    """
    Whether the plotter can be shown (PyQt6-Charts imported), so a mode only
    offers a Plotter button that works.
    """
    with mock.patch("mu.interface.panes.CHARTS", charts):
        assert host.plotter_available is charts
