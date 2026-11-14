# -*- coding: utf-8 -*-
"""
Tests for the micro:bit plugin (nu_microbit) and its mode, with a mock Host
(and, for loading, Nu's real one). No board: see the README's checklist.
"""

import os
from importlib.metadata import PackageNotFoundError, distribution, entry_points
from unittest import mock

import pytest
import time

from PyQt6.QtCore import QCoreApplication, Qt

import mu.wheels
from mu import resources
from mu.app import setup_modes
from mu.plugin import PLUGIN_API_VERSION, Device, Host, loader

import nu_microbit
from nu_microbit import board, flash, mode as mode_module
from nu_microbit import MicrobitMode, MicrobitPlugin
from nu_microbit.api import MICROBIT_APIS

IMAGES_DIR = os.path.join(os.path.dirname(nu_microbit.__file__), "images")

try:
    distribution("nu-microbit")
    INSTALLED = True
except PackageNotFoundError:  # pragma: no cover (without the microbit extra)
    INSTALLED = False


def wait_until(condition, timeout=5.0):
    """Process Qt events until `condition()` is true; False on timeout."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        QCoreApplication.processEvents()
        time.sleep(0.005)
    return True


needs_install = pytest.mark.skipif(
    not INSTALLED, reason="nu-microbit isn't installed (uv sync --all-extras)"
)


@pytest.fixture
def host(tmp_path):
    host = mock.MagicMock()
    host.data_dir.return_value = str(tmp_path / "data" / "microbit")
    host.current_path.return_value = None
    host.current_text.return_value = "from microbit import *\n"
    host.current_device = None
    host.workspace_dir.return_value = str(tmp_path / "mu_code")
    return host


@pytest.fixture
def mm(host):
    """A micro:bit mode whose Host is a mock."""
    mode = MicrobitMode(mock.MagicMock(), mock.MagicMock())
    mode.host = host
    mode.view.button_bar.slots = {}
    return mode


# --- the plugin, through Nu's real loading path ---


@needs_install
def test_entry_point_names_the_plugin():
    (entry_point,) = [
        ep for ep in entry_points(group="mu.plugins") if ep.name == "microbit"
    ]
    assert entry_point.value == "nu_microbit:MicrobitPlugin"
    assert entry_point.load() is MicrobitPlugin
    assert entry_point.dist.name == "nu-microbit"


def test_targets_the_current_api():
    assert MicrobitPlugin.api_version == PLUGIN_API_VERSION


def test_has_a_name_and_description():
    assert MicrobitPlugin.name == "BBC micro:bit"
    assert "micro:bit" in MicrobitPlugin.description


@needs_install
def test_loaded_by_setup_modes_as_an_installed_package():
    """
    Installed (the `microbit` extra), it loads from its entry point under the
    "microbit" key old sessions use. It's opt-in, not bundled: the Plugins
    tab says "Installed package".
    """
    host_modes = setup_modes(mock.MagicMock(), mock.MagicMock())
    mode = host_modes["microbit"]
    assert isinstance(mode, MicrobitMode)
    (record,) = [r for r in mode.host.plugin_records if r.id == "microbit"]
    assert record.status == loader.LOADED
    assert record.kind == "package"
    assert "nu-microbit" not in loader.BUNDLED_DISTRIBUTIONS


def test_not_a_dependency_of_nu():
    """Opt-in until validated on hardware: only Nu's `microbit` extra has it."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).parents[3] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text())
    assert not any(
        dep.startswith("nu-microbit") for dep in project["project"]["dependencies"]
    )
    assert project["project"]["optional-dependencies"]["microbit"] == [
        "nu-microbit>=0.1"
    ]
    assert (
        "./plugins/microbit"
        not in project["tool"]["briefcase"]["app"]["mu"]["requires"]
    )


def test_icons_moved_out_of_the_core():
    for name in ("microbit", "flash", "microbit-flash"):
        for ext in (".png", ".svg"):
            assert not os.path.exists(os.path.join(resources.IMAGES_DIR, name + ext))


def test_loads_into_a_host():
    host = Host(mock.MagicMock(), mock.MagicMock())
    plugin = MicrobitPlugin()
    assert host.load_plugin(plugin) is True
    mode = host.modes["microbit"]
    assert mode.host is host
    assert resources.plugin_image_dirs() == [IMAGES_DIR]
    host.unload_plugin(plugin)
    assert host.modes == {}


def test_icons_come_from_the_plugin():
    host = Host(mock.MagicMock(), mock.MagicMock())
    host.load_plugin(MicrobitPlugin())
    mode = host.modes["microbit"]
    with mock.patch("mu.interface.panes.CHARTS", True):
        names = [action["name"] for action in mode.actions()]
    assert names == ["microbit-flash", "repl", "plotter"]
    for name in [mode.icon, "microbit-flash"]:
        assert os.path.dirname(resources.image_path(name)) == IMAGES_DIR, name
        assert not resources.load_icon(name).isNull(), name
    for name in ["repl", "plotter"]:
        assert os.path.dirname(resources.image_path(name)) == resources.IMAGES_DIR


def test_images_load_without_qt_warnings():
    from PyQt6.QtCore import qInstallMessageHandler
    from PyQt6.QtGui import QPixmap

    warnings = []
    previous = qInstallMessageHandler(lambda *args: warnings.append(args[-1]))
    try:
        for filename in sorted(os.listdir(IMAGES_DIR)):
            assert not QPixmap(os.path.join(IMAGES_DIR, filename)).isNull(), filename
    finally:
        qInstallMessageHandler(previous)
    assert warnings == []


def test_needs_nothing_in_the_learner_env():
    names = [name for name, _ in mu.wheels.baseline_packages()]
    assert "nu-microbit" not in names


# --- the mode ---


def test_mode_basics(mm):
    assert mm.name == "BBC micro:bit"
    assert mm.short_name == "microbit"
    assert mm.icon == "microbit"
    assert "microbit" in mm.module_names
    assert mm.valid_boards == [(0x0D28, 0x0204, None, "BBC micro:bit")]


def test_actions(mm, host):
    host.plotter_available = True
    actions = mm.actions()
    assert [a["name"] for a in actions] == ["microbit-flash", "repl", "plotter"]
    assert actions[0]["handler"] == mm.flash
    assert actions[0]["shortcut"] == "F3"
    assert "Shift" in actions[0]["description"]
    assert actions[1]["handler"] == mm.toggle_repl
    assert actions[2]["handler"] == mm.toggle_plotter


def test_actions_without_charts(mm, host):
    host.plotter_available = False
    assert [a["name"] for a in mm.actions()] == ["microbit-flash", "repl"]


def test_api(mm, host):
    host.shared_apis.return_value = ["shared"]
    apis = mm.api()
    assert apis[0] == "shared"
    assert apis[1:] == MICROBIT_APIS
    names = [entry.split("(")[0].split(" ")[0] for entry in MICROBIT_APIS]
    for name in [
        "microbit.display.show",
        "microbit.display.scroll",
        "microbit.microphone.sound_level",
        "microbit.speaker.on",
        "audio.SoundEffect",
        "log.add",
        "power.deep_sleep",
        "microbit.pin_logo.is_touched",
        "microbit.run_every",
        "radio.send",
        "music.play",
        "neopixel.NeoPixel",
        "speech.say",
    ]:
        assert name in names, name
    assert len(set(MICROBIT_APIS)) == len(MICROBIT_APIS)


def test_workspace_dir(mm, tmp_path):
    path = mm.workspace_dir()
    assert path == str(tmp_path / "mu_code" / "microbit")
    assert os.path.isdir(path)


def test_workspace_dir_cant_be_made(mm, tmp_path):
    with mock.patch("nu_microbit.mode.os.makedirs", side_effect=OSError):
        assert mm.workspace_dir() == str(tmp_path / "mu_code")


def qt_port(vid=0x0D28, pid=0x0204, serial="9906000012345", description="mbed"):
    port = mock.MagicMock()
    port.vendorIdentifier.return_value = vid
    port.productIdentifier.return_value = pid
    port.serialNumber.return_value = serial
    port.manufacturer.return_value = "ARM"
    port.description.return_value = description
    port.portName.return_value = "ttyACM0"
    return port


def test_compatible_board(mm):
    with mock.patch("os.name", "posix"):
        device = mm.compatible_board(qt_port())
    assert isinstance(device, Device)
    assert (device.vid, device.pid) == (0x0D28, 0x0204)
    assert device.port == "/dev/ttyACM0"
    assert device.serial_number == "9906000012345"
    assert device.board_name == "BBC micro:bit V2"
    assert device.short_mode_name == "microbit"


def test_compatible_board_v1(mm):
    with mock.patch("os.name", "posix"):
        assert mm.compatible_board(qt_port(serial="99010000")).board_name == (
            "BBC micro:bit V1"
        )


@pytest.mark.parametrize("vid, pid", [(0x239A, 0x0204), (0x0D28, 0x0205)])
def test_compatible_board_not_a_microbit(mm, vid, pid):
    assert mm.compatible_board(qt_port(vid=vid, pid=pid)) is None


def test_find_devices_without_a_board(mm):
    with mock.patch(
        "mu.modes.base.QSerialPortInfo.availablePorts",
        return_value=[qt_port(vid=0x1234)],
    ):
        assert mm.find_devices() == []


def test_repl_without_a_device(mm):
    """No board: the REPL says so (MicroPythonMode's message), no crash."""
    mm.editor.current_device = None
    mm.toggle_repl(None)
    assert mm.view.show_message.call_count == 1
    assert "Could not find an attached device." in mm.view.show_message.call_args[0]


def test_plotter_without_a_device(mm):
    mm.editor.current_device = None
    mm.toggle_plotter(None)
    assert "Could not find an attached device." in mm.view.show_message.call_args[0]


EXAMPLES = [
    "buttons.py",
    "dice.py",
    "heartbeat.py",
    "hello.py",
    "score_keeper.py",
    "tilt_plot.py",
]


def test_examples_copied_the_first_time(mm, tmp_path):
    workspace = tmp_path / "mu_code"
    mm.ensure_workspace_assets(str(workspace))
    examples = workspace / "microbit" / "examples"
    assert sorted(os.listdir(examples)) == EXAMPLES
    assert "from microbit import *" in (examples / "hello.py").read_text()
    # The learner's changes (and deletions) stay.
    (examples / "hello.py").write_text("# mine")
    (examples / "dice.py").unlink()
    mm.ensure_workspace_assets(str(workspace))
    assert (examples / "hello.py").read_text() == "# mine"
    assert not (examples / "dice.py").exists()


def test_examples_cant_be_copied(mm, tmp_path, caplog):
    with mock.patch("nu_microbit.mode.shutil.copytree", side_effect=OSError("full")):
        mm.ensure_workspace_assets(str(tmp_path))
    assert "Couldn't copy the micro:bit examples" in caplog.text


def test_examples_are_valid_micropython_for_the_microbit():
    """
    Each example compiles, and every name it takes from `microbit` is one
    the micro:bit has (Check's list of what `from microbit import *` brings).
    """
    import ast
    import builtins

    known = set(MicrobitMode.star_imports["microbit"])
    builtins_and_modules = set(dir(builtins)) | {"random", "f"}
    for name in EXAMPLES:
        path = os.path.join(mode_module.EXAMPLES_DIR, name)
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, name)
        assigned = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        } | {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        used = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        unknown = used - known - assigned - builtins_and_modules
        assert not unknown, (name, unknown)


def test_activate_and_deactivate(mm):
    mm.activate()
    assert mm.active is True
    mm.view.show_device_selector.assert_called_once_with()
    mm.deactivate()
    assert mm.active is False


# --- Flash ---


@pytest.fixture
def started(mm):
    """Patch the worker so flash() hands over its job without a thread."""
    with mock.patch("nu_microbit.mode.worker.start") as start:
        start.return_value = (mock.MagicMock(), mock.MagicMock())
        mm.shift_held = mock.MagicMock(return_value=False)
        yield start


def started_job(start):
    return start.call_args[0][0]


def test_flash_starts_a_job(mm, host, started, tmp_path):
    host.current_device = Device(
        0x0D28, 0x0204, "/dev/ttyACM0", 99040001, "ARM", "BBC micro:bit", "microbit"
    )
    host.current_path.return_value = "/home/l/mu_code/microbit/hi.py"
    mm.view.button_bar.slots = {
        name: mock.MagicMock() for name in ["microbit-flash", "repl", "plotter"]
    }
    mm.flash()
    job = started_job(started)
    assert isinstance(job, flash.FlashJob)
    assert job.code == b"from microbit import *\n"
    assert job.port == "/dev/ttyACM0"
    assert job.serial_number == "99040001"
    assert job.source_name == "/home/l/mu_code/microbit/hi.py"
    assert job.cache_dir == str(tmp_path / "data" / "microbit" / "firmware")
    assert job.force_firmware is False
    assert job.log_command is host.log_command
    host.data_dir.assert_called_once_with("microbit")
    for slot in mm.view.button_bar.slots.values():
        slot.setEnabled.assert_called_once_with(False)
    assert started.call_args[0][1:] == (
        mm.on_flash_status,
        mm.on_flash_succeeded,
        mm.on_flash_failed,
        mm.on_flash_finished,
    )
    assert mm.flash_job is job


def test_flash_ignores_another_modes_device(mm, host, started):
    host.current_device = Device(
        1, 2, "COM9", "x", "y", "CircuitPython", "circuitpython"
    )
    mm.flash()
    job = started_job(started)
    assert (job.port, job.serial_number, job.source_name) == (None, None, "main.py")


def test_flash_without_a_tab(mm, host, started):
    host.current_text.return_value = None
    mm.flash()
    assert host.show_message.call_args[0][0] == "There's no code to flash."
    started.assert_not_called()


def test_flash_while_flashing(mm, host, started):
    mm.flash_thread = mock.MagicMock()
    mm.flash()
    host.show_status.assert_called_once_with("Nu is already flashing the micro:bit…")
    started.assert_not_called()


def test_shift_flash_asks_first(mm, host, started):
    mm.shift_held.return_value = True
    host.confirm.return_value = False
    mm.flash()
    started.assert_not_called()
    host.confirm.return_value = True
    mm.flash()
    assert started_job(started).force_firmware is True
    assert "MicroPython back on" in host.confirm.call_args[0][0]


def test_flash_closes_the_repl_and_plotter_and_reopens_them(mm, host, started):
    mm.repl = True
    mm.plotter = True
    mm.connection = mock.MagicMock()
    mm.add_repl = mock.MagicMock()
    mm.add_plotter = mock.MagicMock()
    mm.active = True
    mm.flash()
    assert (mm.repl, mm.plotter, mm.connection) == (False, False, None)
    host.show_status.assert_called_once_with(
        "Closed the REPL so Nu can use the micro:bit's connection."
    )
    mm.on_flash_finished()
    mm.add_repl.assert_called_once_with()
    mm.add_plotter.assert_called_once_with()
    assert mm.flash_thread is None and mm.flash_job is None


def test_flash_finished_after_leaving_the_mode(mm, started):
    """Another mode is current: leave its buttons and panes alone."""
    mm.repl = True
    mm.add_repl = mock.MagicMock()
    mm.flash()
    mm.active = False
    mm.set_buttons = mock.MagicMock()
    mm.on_flash_finished()
    mm.add_repl.assert_not_called()
    mm.set_buttons.assert_not_called()


def test_flash_finished_gives_the_buttons_back(mm, started):
    mm.active = True
    mm.set_buttons = mock.MagicMock()
    mm.on_flash_finished()
    mm.set_buttons.assert_called_once_with(
        **{"microbit-flash": True, "repl": True, "plotter": True}
    )


def test_flash_reports(mm, host):
    mm.on_flash_status("Looking…")
    host.show_status.assert_called_with("Looking…", 60)
    mm.on_flash_succeeded("Done!")
    host.show_status.assert_called_with("Done!", 10)
    mm.on_flash_failed("Broken.", "Because.")
    host.show_message.assert_called_once_with("Broken.", "Because.")


def test_stop_cancels_a_flash(mm):
    job = mock.MagicMock()
    thread = mock.MagicMock()
    mm.flash_job, mm.flash_thread = job, thread
    mm.stop()
    job.cancel.assert_called_once_with()
    thread.quit.assert_called_once_with()
    thread.wait.assert_called_once_with(mode_module.STOP_TIMEOUT_MS)
    thread.terminate.assert_not_called()


def test_stop_terminates_a_stuck_flash(mm):
    thread = mock.MagicMock()
    thread.wait.side_effect = [False, True]
    mm.flash_job, mm.flash_thread = mock.MagicMock(), thread
    mm.stop()
    thread.terminate.assert_called_once_with()
    assert thread.wait.call_count == 2


def test_stop_when_idle(mm):
    mm.stop()


def test_shift_held(mm):
    with mock.patch(
        "nu_microbit.mode.QGuiApplication.queryKeyboardModifiers",
        return_value=Qt.KeyboardModifier.ShiftModifier,
    ):
        assert mm.shift_held() is True
    with mock.patch(
        "nu_microbit.mode.QGuiApplication.queryKeyboardModifiers",
        return_value=Qt.KeyboardModifier.NoModifier,
    ):
        assert mm.shift_held() is False


def test_board_io_is_the_real_one(mm):
    assert mm.board_io().find_drive is board.find_drive


def test_flash_with_no_microbit_end_to_end(mm, host):
    """
    The whole path on a real worker thread, with nothing plugged in: the
    learner is told there's no micro:bit, and the buttons come back.
    """
    io = flash.BoardIO(
        find_drive=lambda label=board.DRIVE_LABEL: None,
        find_serial_port=lambda serial_number=None: None,
    )
    mm.board_io = lambda: io
    mm.shift_held = lambda: False
    mm.active = True
    mm.set_buttons = mock.MagicMock()
    mm.flash()
    thread = mm.flash_thread
    # Pump events by hand: a QEventLoop can return at once if an earlier
    # test asked the application to quit.
    assert wait_until(lambda: mm.flash_thread is None)
    assert thread.isFinished()
    host.show_message.assert_called_once()
    assert host.show_message.call_args[0][0] == (
        "Could not find an attached BBC micro:bit."
    )
    assert mm.flash_thread is None
    mm.set_buttons.assert_called_with(
        **{"microbit-flash": True, "repl": True, "plotter": True}
    )
    assert mode_module.FLASH_BUTTON == "microbit-flash"


def test_check_understands_from_microbit_import_star():
    """
    With the mode's star_imports, Check reads "from microbit import *" as
    naming the micro:bit's things: no noise about the star import, and a
    real undefined name is still caught.
    """
    import mu.logic
    from nu_microbit.mode import MicrobitMode

    code = "from microbit import *\ndisplay.scroll('hi')\nsleep(10)\nprint(oops)\n"
    result = mu.logic.check_flake(
        "main.py", code, star_imports=MicrobitMode.star_imports
    )
    messages = [log["message"] for logs in result.values() for log in logs]
    assert messages == ["undefined name 'oops'"]
