# -*- coding: utf-8 -*-
"""
Tests for the CircuitPython plugin (nu_circuitpython).
"""

import ctypes
import os
from importlib.metadata import entry_points
from unittest import mock

import pytest

import mu.wheels
from mu import resources
from mu.app import setup_modes
from mu.plugin import PLUGIN_API_VERSION, Device, Host, loader

import nu_circuitpython
from nu_circuitpython import CircuitPythonMode, CircuitPythonPlugin
from nu_circuitpython.api import ADAFRUIT_APIS

IMAGES_DIR = os.path.join(os.path.dirname(nu_circuitpython.__file__), "images")
TESTS_DIR = os.path.dirname(__file__)


def fixture_path(name):
    """The path of a fixture file kept next to these tests."""
    return os.path.join(TESTS_DIR, name)


@pytest.fixture
def host():
    return mock.MagicMock()


@pytest.fixture
def am(host):
    """A CircuitPython mode whose Host is a mock."""
    mode = CircuitPythonMode(mock.MagicMock(), mock.MagicMock())
    mode.host = host
    return mode


# --- the plugin, through Nu's real loading path ---


def test_entry_point_names_the_plugin():
    """
    The installed package advertises the plugin under the mode's old id, so
    Nu finds it like any other installed plugin.
    """
    (entry_point,) = [
        ep for ep in entry_points(group="mu.plugins") if ep.name == "circuitpython"
    ]
    assert entry_point.value == "nu_circuitpython:CircuitPythonPlugin"
    assert entry_point.load() is CircuitPythonPlugin
    assert entry_point.dist.name == "nu-circuitpython"


def test_targets_the_current_api():
    assert CircuitPythonPlugin.api_version == PLUGIN_API_VERSION


def test_loaded_by_setup_modes_from_its_entry_point():
    """
    Nu's startup loads the bundled plugin from its entry point and switched
    on, after the core's modes, under the "circuitpython" key saved sessions
    and settings use.
    """
    host_modes = setup_modes(mock.MagicMock(), mock.MagicMock())
    assert list(host_modes)[:2] == ["python", "debugger"]
    mode = host_modes["circuitpython"]
    assert isinstance(mode, CircuitPythonMode)
    (record,) = [r for r in mode.host.plugin_records if r.id == "circuitpython"]
    assert record.status == loader.LOADED
    assert record.kind == "bundled"  # it ships with Nu
    assert record.origin.startswith("nu-circuitpython ")


def test_not_built_into_the_core():
    """
    The core no longer ships the mode, its API stubs or its icons.
    """
    import mu.modes
    import mu.modes.api

    assert not hasattr(mu.modes, "CircuitPythonMode")
    assert not hasattr(mu.modes.api, "ADAFRUIT_APIS")
    for name in ("circuitpython", "circuitpython-serial", "serial"):
        for ext in (".png", ".svg"):
            assert not os.path.exists(os.path.join(resources.IMAGES_DIR, name + ext))


def test_loads_into_a_host():
    """
    Registering the plugin adds the mode and makes its icons available, and
    unloading takes both away again.
    """
    host = Host(mock.MagicMock(), mock.MagicMock())
    plugin = CircuitPythonPlugin()
    assert host.load_plugin(plugin) is True
    mode = host.modes["circuitpython"]
    assert mode.host is host
    assert resources.plugin_image_dirs() == [IMAGES_DIR]
    host.unload_plugin(plugin)
    assert host.modes == {}
    assert resources.plugin_image_dirs() == []


def test_icons_come_from_the_plugin():
    """
    The mode's icon and its Serial button's come from its images folder, and
    the Plotter button's from Nu's own.
    """
    host = Host(mock.MagicMock(), mock.MagicMock())
    host.load_plugin(CircuitPythonPlugin())
    mode = host.modes["circuitpython"]
    with mock.patch("mu.interface.panes.CHARTS", True):
        names = [action["name"] for action in mode.actions()]
    assert names == ["circuitpython-serial", "plotter"]
    for name in [mode.icon, "circuitpython-serial"]:
        assert os.path.dirname(resources.image_path(name)) == IMAGES_DIR, name
        assert not resources.load_icon(name).isNull(), name
    assert os.path.dirname(resources.image_path("plotter")) == resources.IMAGES_DIR


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


def test_needs_nothing_in_the_learner_env():
    """
    CircuitPython code runs on the board, so the plugin adds nothing to the
    learner's environment (or the installers' offline wheelhouse).
    """
    names = [name for name, _ in mu.wheels.baseline_packages()]
    assert "nu-circuitpython" not in names


# --- the mode ---


def test_circuitpython_mode(am, host):
    """
    Sanity check for setting up the mode.
    """
    assert am.name == "CircuitPython"
    assert am.short_name == "circuitpython"
    assert am.description is not None
    assert am.icon == "circuitpython"
    assert am.save_timeout == 0
    assert "code" not in am.module_names
    assert "board" in am.module_names

    host.plotter_available = True
    actions = am.actions()
    assert len(actions) == 2
    assert actions[0]["name"] == "circuitpython-serial"
    assert actions[0]["handler"] == am.toggle_repl
    assert actions[1]["name"] == "plotter"
    assert actions[1]["handler"] == am.toggle_plotter


def test_circuitpython_mode_no_charts(am, host):
    """
    If QCharts is not available, ensure the plotter feature is not available.
    """
    host.plotter_available = False
    actions = am.actions()
    assert len(actions) == 1
    assert actions[0]["name"] == "circuitpython-serial"
    assert actions[0]["handler"] == am.toggle_repl


def test_api(am, host):
    """
    Autocomplete is the entries every Python shares plus CircuitPython's.
    """
    host.shared_apis.return_value = ["shared"]
    assert am.api() == ["shared"] + ADAFRUIT_APIS
    assert ADAFRUIT_APIS


def _port(name="ttyACM0"):
    """A QSerialPortInfo stand-in for a board on serial port `name`."""
    port = mock.MagicMock()
    port.productIdentifier.return_value = 0x8019
    port.vendorIdentifier.return_value = 0x239A
    port.manufacturer.return_value = "Adafruit"
    port.serialNumber.return_value = "ABC123"
    port.portName.return_value = name
    return port


def test_compatible_board_is_a_circuitpython_repl(am):
    """
    A serial port adafruit_board_toolkit reports as a CircuitPython REPL is a
    board for this mode, described by a Device.
    """
    comport = mock.MagicMock(device="/dev/ttyACM0")
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_circuitpython.mode.circuitpython_serial.repl_comports",
            return_value=[mock.MagicMock(device="/dev/ttyACM1"), comport],
        ),
    ):
        device = am.compatible_board(_port())
    assert isinstance(device, Device)
    assert device == Device(
        0x239A,
        0x8019,
        "/dev/ttyACM0",
        "ABC123",
        "Adafruit",
        "CircuitPython",
        "circuitpython",
        "CircuitPython board",
    )
    assert device.short_mode_name == "circuitpython"
    assert device.board_name == "CircuitPython board"


def test_compatible_board_not_a_circuitpython_repl(am):
    """
    Any other serial port isn't a board for this mode.
    """
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_circuitpython.mode.circuitpython_serial.repl_comports",
            return_value=[mock.MagicMock(device="/dev/ttyACM1")],
        ),
    ):
        assert am.compatible_board(_port()) is None


def test_find_devices_without_a_board(am):
    """
    With nothing plugged in, the mode finds no devices.
    """
    with mock.patch("mu.modes.base.QSerialPortInfo.availablePorts", return_value=[]):
        assert am.find_devices(with_logging=False) == []


def test_serial_without_a_device(am):
    """
    The Serial button with no board attached says so, rather than failing.
    """
    am.editor.current_device = None
    am.toggle_repl(None)
    assert am.repl is False
    am.view.show_message.assert_called_once()
    assert (
        "Could not find an attached device." in (am.view.show_message.call_args[0][0])
    )
    am.view.add_micropython_repl.assert_not_called()


def test_plotter_without_a_device(am):
    """
    The Plotter button with no board attached says so, rather than failing.
    """
    am.editor.current_device = None
    am.toggle_plotter(None)
    assert am.plotter is False
    am.view.show_message.assert_called_once()
    am.view.add_micropython_plotter.assert_not_called()


# --- where the learner's files go ---


def test_workspace_dir_posix_exists(am):
    """
    Simulate being on os.name == 'posix' and a call to "mount" returns a
    record indicating a connected device.
    """
    with open(fixture_path("mount_exists.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with mock.patch("nu_circuitpython.mode.check_output", return_value=fixture):
                assert am.workspace_dir() == "/media/ntoll/CIRCUITPY"


def test_workspace_dir_posix_no_mount_command(am):
    """
    When the user doesn't have administrative privileges on OSX then the mount
    command isn't on their path. In which case, check Mu uses the more
    explicit /sbin/mount instead.
    """
    with open(fixture_path("mount_exists.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
    mock_check = mock.MagicMock(side_effect=[FileNotFoundError, fixture])
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_circuitpython.mode.check_output", mock_check),
    ):
        assert am.workspace_dir() == "/media/ntoll/CIRCUITPY"
        assert mock_check.call_count == 2
        assert mock_check.call_args_list[0][0][0] == "mount"
        assert mock_check.call_args_list[1][0][0] == "/sbin/mount"


def test_workspace_dir_posix_permission_denied(am, host):
    """
    When the mount command results in a Permission Denied error, show a
    message and use default workspace dir.
    """
    with open(fixture_path("mount_exists.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
    mock_check = mock.MagicMock(side_effect=[PermissionError, fixture])
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_circuitpython.mode.check_output", mock_check),
    ):
        assert am.workspace_dir() == "/media/ntoll/CIRCUITPY"
        assert mock_check.call_count == 2
        assert mock_check.call_args_list[0][0][0] == "mount"
        assert mock_check.call_args_list[1][0][0] == "/sbin/mount"
    assert host.show_message.call_count == 1


def test_workspace_dir_posix_exception_raised(am):
    """
    When the mount command results in an unexpected exception, log the error
    and use the default workspace dir.
    """
    with open(fixture_path("mount_exists.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
    mock_check = mock.MagicMock(side_effect=[ValueError, fixture])
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_circuitpython.mode.check_output", mock_check),
    ):
        assert am.workspace_dir() == "/media/ntoll/CIRCUITPY"
        assert mock_check.call_count == 2
        assert mock_check.call_args_list[0][0][0] == "mount"
        assert mock_check.call_args_list[1][0][0] == "/sbin/mount"


def test_workspace_dir_posix_missing(am):
    """
    Simulate being on os.name == 'posix' and a call to "mount" returns a
    no records associated with a micro:bit device.
    """
    with open(fixture_path("mount_missing.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with (
                mock.patch("nu_circuitpython.mode.check_output", return_value=fixture),
                mock.patch(
                    "nu_circuitpython.mode.MicroPythonMode.workspace_dir"
                ) as mpm,
            ):
                mpm.return_value = "foo"
                assert am.workspace_dir() == "foo"


def test_workspace_dir_posix_chromeos_exists(am):
    """
    Simulate being on os.name == 'posix' and a check in /mnt/chromeos/removable returns
    a record associated with a CIRCUITPY device.
    """
    with open(fixture_path("chromeos_devpath_exists.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with mock.patch("nu_circuitpython.mode.check_output", return_value=fixture):
                with mock.patch("os.path.exists", return_value=True):
                    assert am.workspace_dir() == "/mnt/chromeos/removable/CIRCUITPY/"


def test_workspace_dir_posix_chromeos_missing(am):
    """
    Simulate being on os.name == 'posix' and a check in /mnt/chromeos/removable returns
    no records associated with a CIRCUITPY device.
    """
    with open(fixture_path("chromeos_devpath_missing.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with mock.patch("nu_circuitpython.mode.check_output", return_value=fixture):
                with mock.patch("os.path.exists", return_value=False):
                    assert am.workspace_dir().endswith("mu_code")


@pytest.fixture
def windll():
    """
    Mocking the windll is tricky. It's not present on Posix platforms so
    we can't use standard patching. But it *is* present on Windows platforms
    so we need to unpatch once finished.
    """
    ctypes_has_windll = hasattr(ctypes, "windll")
    if ctypes_has_windll:
        mock_windll = mock.patch("ctypes.windll")
        mock_windll.start()
    else:
        mock_windll = mock.MagicMock()
        ctypes.windll = mock_windll

    yield mock_windll

    if ctypes_has_windll:
        mock_windll.stop()
    else:
        delattr(ctypes, "windll")


def test_workspace_dir_nt_exists(am, windll):
    """
    Simulate being on os.name == 'nt' and a disk with a volume name 'CIRCUITPY'
    exists indicating a connected device.

    """

    with mock.patch("os.name", "nt"):
        with mock.patch("os.path.exists", return_value=True):
            return_value = ctypes.create_unicode_buffer("CIRCUITPY")
            with mock.patch("ctypes.create_unicode_buffer", return_value=return_value):
                assert am.workspace_dir() == "A:\\"


def test_workspace_dir_nt_missing(am, windll):
    """
    Simulate being on os.name == 'nt' and a disk with a volume name 'CIRCUITPY'
    does not exist for a device.
    """
    with mock.patch("os.name", "nt"):
        with mock.patch("os.path.exists", return_value=True):
            return_value = ctypes.create_unicode_buffer(1024)
            with (
                mock.patch("ctypes.create_unicode_buffer", return_value=return_value),
                mock.patch(
                    "nu_circuitpython.mode.MicroPythonMode.workspace_dir"
                ) as mpm,
            ):
                mpm.return_value = "foo"
                assert am.workspace_dir() == "foo"


def test_workspace_dir_unknown_os(am):
    """
    Raises a NotImplementedError if the host OS is not supported.
    """
    with mock.patch("os.name", "foo"):
        with pytest.raises(NotImplementedError) as ex:
            am.workspace_dir()
    assert ex.value.args[0] == 'OS "foo" not supported.'


def test_workspace_dir_posix_chromeos_drive_not_shared(am, host):
    """
    On ChromeOS without the CIRCUITPY drive shared with Linux, the learner is
    told how to share it, and the usual workspace is used.
    """
    with open(fixture_path("chromeos_devpath_missing.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()

    def exists(path):
        return path == "/mnt/chromeos"

    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_circuitpython.mode.check_output", return_value=fixture),
        mock.patch("os.path.exists", side_effect=exists),
        mock.patch(
            "nu_circuitpython.mode.MicroPythonMode.workspace_dir",
            return_value="foo",
        ),
    ):
        assert am.workspace_dir() == "foo"
    message = host.show_message.call_args_list[0][0][0]
    assert "Share with Linux" in message


def test_workspace_dir_warns_once_without_a_device(am, host):
    """
    With no board attached the learner is warned the first time, and not
    again until a board has been found.
    """
    with open(fixture_path("mount_missing.txt"), "rb") as fixture_file:
        fixture = fixture_file.read()
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_circuitpython.mode.check_output", return_value=fixture),
        mock.patch("os.path.exists", return_value=False),
        mock.patch(
            "nu_circuitpython.mode.MicroPythonMode.workspace_dir",
            return_value="foo",
        ),
    ):
        assert am.workspace_dir() == "foo"
        assert am.workspace_dir() == "foo"
    host.show_message.assert_called_once()
    message, info = host.show_message.call_args[0]
    assert message == "Could not find an attached CircuitPython device."
    assert "foo" in info
    assert am.connected is False
