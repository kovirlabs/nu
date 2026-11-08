# -*- coding: utf-8 -*-
"""
Tests for the Pygame Zero plugin (nu_pygamezero).
"""

import os
import tempfile
from importlib.metadata import entry_points
from unittest import mock

import pytest

import mu.wheels
from mu import resources
from mu.app import setup_modes
from mu.plugin import PLUGIN_API_VERSION, Host, loader

import nu_pygamezero
from nu_pygamezero import PygameZeroPlugin, PyGameZeroMode
from nu_pygamezero.api import PYGAMEZERO_APIS
from nu_pygamezero.mode import ASSETS_DIR

IMAGES_DIR = os.path.join(os.path.dirname(nu_pygamezero.__file__), "images")


@pytest.fixture
def host():
    return mock.MagicMock()


@pytest.fixture
def pm(host):
    """A Pygame Zero mode whose Host is a mock."""
    mode = PyGameZeroMode(mock.MagicMock(), mock.MagicMock())
    mode.host = host
    return mode


# --- the plugin, through Nu's real loading path ---


def test_entry_point_names_the_plugin():
    """
    The installed package advertises the plugin under the mode's old id, so
    Nu finds it like any other installed plugin.
    """
    (entry_point,) = [
        ep for ep in entry_points(group="mu.plugins") if ep.name == "pygamezero"
    ]
    assert entry_point.value == "nu_pygamezero:PygameZeroPlugin"
    assert entry_point.load() is PygameZeroPlugin
    assert entry_point.dist.name == "nu-pygamezero"


def test_targets_the_current_api():
    assert PygameZeroPlugin.api_version == PLUGIN_API_VERSION


def test_loaded_by_setup_modes_from_its_entry_point():
    """
    Nu's startup loads the bundled plugin from its entry point and switched
    on, after the core's modes, under the "pygamezero" key saved sessions
    and settings use.
    """
    host_modes = setup_modes(mock.MagicMock(), mock.MagicMock())
    assert list(host_modes)[:3] == ["python", "circuitpython", "debugger"]
    mode = host_modes["pygamezero"]
    assert isinstance(mode, PyGameZeroMode)
    (record,) = [r for r in mode.host.plugin_records if r.id == "pygamezero"]
    assert record.status == loader.LOADED
    assert record.kind == "package"
    assert record.origin.startswith("nu-pygamezero ")


def test_loads_into_a_host():
    """
    Registering the plugin adds the mode and makes its icons available, and
    unloading takes both away again.
    """
    host = Host(mock.MagicMock(), mock.MagicMock())
    plugin = PygameZeroPlugin()
    assert host.load_plugin(plugin) is True
    mode = host.modes["pygamezero"]
    assert mode.host is host
    assert resources.plugin_image_dirs() == [IMAGES_DIR]
    host.unload_plugin(plugin)
    assert host.modes == {}
    assert resources.plugin_image_dirs() == []


def test_icons_come_from_the_plugin():
    """
    The mode's icon and every toolbar icon it uses exist: its own from its
    images folder, and Nu's "stop" from the core.
    """
    host = Host(mock.MagicMock(), mock.MagicMock())
    host.load_plugin(PygameZeroPlugin())
    mode = host.modes["pygamezero"]
    for name in [mode.icon] + [action["name"] for action in mode.actions()]:
        assert os.path.dirname(resources.image_path(name)) == IMAGES_DIR, name
        assert not resources.load_icon(name).isNull(), name
    assert os.path.dirname(resources.image_path("stop")) == resources.IMAGES_DIR


def test_images_load_without_qt_warnings():
    """
    Every image the plugin ships loads cleanly (as the core's are checked).
    """
    from PyQt6.QtCore import qInstallMessageHandler
    from PyQt6.QtGui import QPixmap

    warnings = []
    previous = qInstallMessageHandler(lambda *args: warnings.append(args[-1]))
    try:
        for filename in sorted(os.listdir(IMAGES_DIR)):
            pixmap = QPixmap(os.path.join(IMAGES_DIR, filename))
            assert not pixmap.isNull(), filename
    finally:
        qInstallMessageHandler(previous)
    assert warnings == []


def test_learner_env_packages():
    """
    pgzero and pygame go into the learner's environment (and the installers'
    offline wheelhouse) because this plugin declares them.
    """
    assert ("nu-pygamezero", ("pgzero>=1.2.1", "pygame>=2.6")) in (
        mu.wheels.baseline_packages()
    )


# --- the mode ---


def test_pgzero_mode(pm):
    """
    Sanity check for setting up of the mode.
    """
    assert pm.name == "Pygame Zero"
    assert pm.short_name == "pygamezero"
    assert pm.description is not None
    assert pm.icon == "pygamezero"
    assert pm.is_debugger is False
    assert pm.builtins
    assert pm.running is False

    actions = pm.actions()
    assert len(actions) == 5
    assert actions[0]["name"] == "play"
    assert actions[0]["handler"] == pm.play_toggle
    assert actions[1]["name"] == "images"
    assert actions[1]["handler"] == pm.show_images
    assert actions[2]["name"] == "fonts"
    assert actions[2]["handler"] == pm.show_fonts
    assert actions[3]["name"] == "sounds"
    assert actions[3]["handler"] == pm.show_sounds
    assert actions[4]["name"] == "music"
    assert actions[4]["handler"] == pm.show_music


def test_pgzero_api(pm, host):
    """
    Autocomplete is Nu's Python 3 entries plus Pygame Zero's.
    """
    host.python_apis.return_value = ["python"]
    assert pm.api() == ["python"] + PYGAMEZERO_APIS
    assert PYGAMEZERO_APIS


def test_pgzero_uses_the_user_environment():
    """
    Pygame Zero games run in the learner's environment, so the admin dialog
    shows its environment variables and third-party packages.
    """
    assert PyGameZeroMode.uses_user_environment is True


def test_pgzero_play_toggle_on(pm, host):
    """
    Check the handler for clicking play starts the new process and updates the
    UI state.
    """

    def run_game():
        pm.running = True

    pm.run_game = mock.MagicMock(side_effect=run_game)
    pm.set_buttons = mock.MagicMock()
    pm.play_toggle(None)
    pm.run_game.assert_called_once_with()
    host.update_action.assert_called_once_with(
        "play",
        display_name="Stop",
        description="Stop your Pygame Zero game.",
        icon="stop",
    )
    pm.set_buttons.assert_called_once_with(modes=False)


def test_pgzero_play_toggle_on_cancelled(pm, host):
    """
    Ensure the button states are correct if playing an unsaved script is
    cancelled before the process is allowed to start.
    """
    pm.run_game = mock.MagicMock()
    pm.set_buttons = mock.MagicMock()
    pm.play_toggle(None)
    pm.run_game.assert_called_once_with()
    host.update_action.assert_not_called()
    pm.set_buttons.assert_not_called()


def test_pgzero_play_toggle_off(pm, host):
    """
    Check the handler for clicking play stops the process and reverts the UI
    state.
    """
    pm.running = True
    pm.stop_game = mock.MagicMock()
    pm.set_buttons = mock.MagicMock()
    pm.play_toggle(None)
    pm.stop_game.assert_called_once_with()
    host.update_action.assert_called_once_with(
        "play",
        display_name="Play",
        description="Play your Pygame Zero game.",
        icon="play",
    )
    pm.set_buttons.assert_called_once_with(modes=True)


def test_pgzero_run_game(pm, host):
    """
    Running the game saves it, then runs it with "python -m pgzero".
    """
    host.save_current.return_value = "/foo/bar"
    host.run_program.return_value = True
    pm.run_game()
    host.save_current.assert_called_once_with()
    host.run_program.assert_called_once_with("/foo/bar", python_args=["-m", "pgzero"])
    assert pm.running is True


def test_pgzero_run_game_did_not_start(pm, host):
    host.save_current.return_value = "/foo/bar"
    host.run_program.return_value = False
    pm.run_game()
    assert pm.running is False


def test_pgzero_run_game_no_editor(pm, host):
    """
    If there's no active tab, there can be no runner either.
    """
    host.current_text.return_value = None
    pm.stop_game = mock.MagicMock()
    pm.run_game()
    assert pm.running is False
    pm.stop_game.assert_called_once_with()
    host.save_current.assert_not_called()
    host.run_program.assert_not_called()


def test_pgzero_run_game_saving_cancelled(pm, host):
    """
    If the learner doesn't name an unsaved file, nothing runs.
    """
    host.save_current.return_value = None
    pm.run_game()
    host.run_program.assert_not_called()
    assert pm.running is False


def test_pgzero_stop_game(pm, host):
    """
    Check that the child process is killed and the UI is reset.
    """
    pm.running = True
    pm.stop_game()
    host.stop_program.assert_called_once_with()
    assert pm.running is False


@pytest.mark.parametrize(
    "handler, asset_type",
    [
        ("show_images", "images"),
        ("show_fonts", "fonts"),
        ("show_sounds", "sounds"),
        ("show_music", "music"),
    ],
)
def test_pgzero_show_assets(pm, host, handler, asset_type):
    """
    The OS's file explorer opens the asset folder next to the current file.
    """
    pm.view.current_tab.path = os.path.join(tempfile.gettempdir(), "abc.py")
    getattr(pm, handler)(None)
    expected = os.path.join(tempfile.gettempdir(), asset_type)
    host.open_directory.assert_called_once_with(expected)


@pytest.mark.parametrize(
    "handler, asset_type",
    [
        ("show_images", "images"),
        ("show_fonts", "fonts"),
        ("show_sounds", "sounds"),
        ("show_music", "music"),
    ],
)
def test_pgzero_show_assets_no_file(pm, host, handler, asset_type, tmp_path):
    """
    Run the OS file explorer for the workspace if no file is current.
    """
    pm.view.current_tab = None
    with mock.patch.object(PyGameZeroMode, "workspace_dir", return_value=tmp_path):
        getattr(pm, handler)(None)
    host.open_directory.assert_called_once_with(os.path.join(tmp_path, asset_type))


def test_pgzero_ensure_workspace_assets(pm, tmp_path):
    """
    The asset folders Pygame Zero looks in are created in the workspace, and
    the demo images and sounds are copied into new ones.
    """
    pm.ensure_workspace_assets(str(tmp_path))
    assert sorted(os.listdir(tmp_path)) == ["fonts", "images", "music", "sounds"]
    demo_images = sorted(os.listdir(os.path.join(ASSETS_DIR, "images")))
    demo_sounds = sorted(os.listdir(os.path.join(ASSETS_DIR, "sounds")))
    assert "alien.png" in demo_images
    assert "eep.wav" in demo_sounds
    assert sorted(os.listdir(tmp_path / "images")) == demo_images
    assert sorted(os.listdir(tmp_path / "sounds")) == demo_sounds
    assert os.listdir(tmp_path / "fonts") == []
    assert os.listdir(tmp_path / "music") == []


def test_pgzero_ensure_workspace_assets_keeps_existing_folders(pm, tmp_path):
    """
    Folders the learner already has are left alone: nothing is copied back
    into them, so deleted demo files stay deleted.
    """
    for name in ("images", "sounds"):
        (tmp_path / name).mkdir()
    pm.ensure_workspace_assets(str(tmp_path))
    assert os.listdir(tmp_path / "images") == []
    assert os.listdir(tmp_path / "sounds") == []
    assert (tmp_path / "fonts").is_dir()
    assert (tmp_path / "music").is_dir()
