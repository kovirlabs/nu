# -*- coding: utf-8 -*-
"""
Tests for nu_microbit.board: telling which micro:bit is plugged in, finding
its drive and serial port, and asking it whether MicroPython is running.

There's no micro:bit in CI: the drive, DETAILS.TXT, `mount` and the serial
port are all fixtures or fakes here (the README's checklist covers the real
thing).
"""

import ctypes
import os
from unittest import mock

import pytest

from nu_microbit import board

TESTS_DIR = os.path.dirname(__file__)


def fixture_bytes(name):
    with open(os.path.join(TESTS_DIR, name), "rb") as fixture_file:
        return fixture_file.read()


def fixture_text(name):
    with open(os.path.join(TESTS_DIR, name), encoding="utf-8", newline="") as f:
        return f.read()


# --- board ids ---


@pytest.mark.parametrize(
    "board_id, version",
    [
        ("9900", 1),
        ("9901", 1),
        ("9903", 2),
        ("9904", 2),
        ("9905", 2),
        ("9906", 2),
        ("9902", None),
        ("9907", None),
        ("0240", None),
        ("", None),
        (None, None),
    ],
)
def test_board_version(board_id, version):
    assert board.board_version(board_id) == version


@pytest.mark.parametrize(
    "serial_number, board_id",
    [
        ("9904360258994e45003c2013000000340000000097969", "9904"),
        ("9900000037024E45", "9900"),
        ("990", None),
        ("XYZW1234", None),
        ("", None),
        (None, None),
    ],
)
def test_board_id_from_serial(serial_number, board_id):
    """DAPLink's USB serial number starts with the board ID."""
    assert board.board_id_from_serial(serial_number) == board_id


@pytest.mark.parametrize(
    "serial_number, description, name",
    [
        ("99010000528", "mbed Serial Port", "BBC micro:bit V1"),
        ("99060000528", "", "BBC micro:bit V2"),
        ("02400000328", "BBC micro:bit CMSIS-DAP", "BBC micro:bit"),
        ("", "", "BBC micro:bit"),
    ],
)
def test_board_name(serial_number, description, name):
    assert board.board_name(serial_number, description) == name


# --- DETAILS.TXT ---


def test_parse_details_v2():
    details = board.parse_details(fixture_text("details_v2.txt"))
    assert details.board_id == "9904"
    assert details.version == 2
    assert details.daplink_version == "0255"
    assert details.unique_id.startswith("9904360258994e45")


def test_parse_details_v1():
    details = board.parse_details(fixture_text("details_v1.txt"))
    assert (details.board_id, details.version, details.daplink_version) == (
        "9901",
        1,
        "0253",
    )


def test_parse_details_old_daplink_with_crlf():
    """Older DAPLink (0234) has fewer lines, and Windows-style line ends."""
    text = fixture_text("details_v1_old.txt").replace("\r\n", "\n")
    details = board.parse_details(text.replace("\n", "\r\n"))
    assert (details.board_id, details.version, details.daplink_version) == (
        "9900",
        1,
        "0234",
    )


def test_parse_details_unknown_board():
    details = board.parse_details(fixture_text("details_unknown.txt"))
    assert details.board_id == "0240"
    assert details.version is None


def test_parse_details_board_id_line_wins():
    """Some DAPLink builds say the board ID outright."""
    details = board.parse_details(
        "Unique ID: 9900000037024e45\nBoard ID: 9904\nVersion: 0241\n"
    )
    assert details.board_id == "9904"
    assert details.version == 2
    assert details.daplink_version == "0241"


def test_parse_details_nothing_useful():
    details = board.parse_details("hello\n: nothing\n")
    assert details == board.BoardDetails(None, None, None, None)


def test_read_details(tmp_path):
    (tmp_path / "DETAILS.TXT").write_bytes(fixture_bytes("details_v2.txt"))
    assert board.read_details(str(tmp_path)).version == 2


def test_read_details_missing(tmp_path):
    with pytest.raises(OSError):
        board.read_details(str(tmp_path))


def test_read_fail_txt(tmp_path):
    assert board.read_fail_txt(str(tmp_path)) is None
    (tmp_path / "FAIL.TXT").write_text("error: The hex file cannot be decoded.\n")
    assert board.read_fail_txt(str(tmp_path)) == (
        "error: The hex file cannot be decoded."
    )


# --- finding the drive ---


@pytest.fixture
def no_globs():
    with mock.patch("nu_microbit.board.glob.glob", return_value=[]) as fake:
        yield fake


@pytest.fixture
def no_chromeos():
    with mock.patch("nu_microbit.board.os.path.isdir", return_value=False) as fake:
        yield fake


def test_find_drive_linux_mount(no_globs, no_chromeos):
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_microbit.board.check_output",
            return_value=fixture_bytes("mount_microbit.txt"),
        ),
    ):
        assert board.find_drive() == "/media/learner/MICROBIT"


def test_find_drive_macos_mount(no_globs, no_chromeos):
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_microbit.board.check_output",
            return_value=fixture_bytes("mount_macos.txt"),
        ),
    ):
        assert board.find_drive() == "/Volumes/MICROBIT"


def test_find_drive_maintenance(no_globs, no_chromeos):
    """The bootloader's MAINTENANCE drive is found by its own label."""
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_microbit.board.check_output",
            return_value=fixture_bytes("mount_maintenance.txt"),
        ),
    ):
        assert board.find_drive() is None
        assert board.find_drive(board.MAINTENANCE_LABEL) == (
            "/media/learner/MAINTENANCE"
        )


def test_find_drive_numbered_second_mount(no_globs, no_chromeos):
    """A second mount of the same label (MICROBIT1) is still the micro:bit."""
    output = b"/dev/sdd on /media/learner/MICROBIT1 type vfat (rw)\n"
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_microbit.board.check_output", return_value=output),
    ):
        assert board.find_drive() == "/media/learner/MICROBIT1"


def test_find_drive_not_fooled_by_similar_names(no_globs, no_chromeos):
    output = b"/dev/sdd on /media/learner/MICROBITS type vfat (rw)\n"
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_microbit.board.check_output", return_value=output),
    ):
        assert board.find_drive() is None


def test_find_drive_missing(no_globs, no_chromeos):
    with (
        mock.patch("os.name", "posix"),
        mock.patch(
            "nu_microbit.board.check_output",
            return_value=fixture_bytes("mount_missing.txt"),
        ),
    ):
        assert board.find_drive() is None


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError, ValueError])
def test_find_drive_mount_fails_then_globs(error, no_chromeos):
    """
    If `mount` can't be run, the usual automount folders are searched
    instead (Linux's /media and /run/media, macOS's /Volumes).
    """
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_microbit.board.check_output", side_effect=error),
        mock.patch(
            "nu_microbit.board.glob.glob",
            side_effect=lambda pattern: (
                ["/Volumes/MICROBIT"] if pattern.startswith("/Volumes") else []
            ),
        ) as globs,
    ):
        assert board.find_drive() == "/Volumes/MICROBIT"
    patterns = [c.args[0] for c in globs.call_args_list]
    assert patterns == [
        "/media/*/MICROBIT",
        "/run/media/*/MICROBIT",
        "/media/MICROBIT",
        "/Volumes/MICROBIT",
    ]


def test_find_drive_chromeos_shared(no_globs):
    """
    On ChromeOS the drive is only visible once shared with Linux, under
    /mnt/chromeos/removable.
    """
    with (
        mock.patch("os.name", "posix"),
        mock.patch("nu_microbit.board.check_output", return_value=b""),
        mock.patch(
            "nu_microbit.board.os.path.isdir",
            side_effect=lambda path: path == "/mnt/chromeos/removable/MICROBIT",
        ),
    ):
        assert board.find_drive() == "/mnt/chromeos/removable/MICROBIT"


def test_on_chromeos():
    with mock.patch("nu_microbit.board.os.path.exists", return_value=True):
        assert board.on_chromeos() is True
    with mock.patch("nu_microbit.board.os.path.exists", return_value=False):
        assert board.on_chromeos() is False


def test_find_drive_windows():
    labels = {"C:\\": "Windows", "E:\\": "MICROBIT"}
    with (
        mock.patch("os.name", "nt"),
        mock.patch("nu_microbit.board._windows_drives", return_value=list(labels)),
        mock.patch("nu_microbit.board._windows_volume_label", side_effect=labels.get),
    ):
        assert board.find_drive() == "E:\\"
        assert board.find_drive(board.MAINTENANCE_LABEL) is None


def test_find_drive_unknown_os():
    with mock.patch("os.name", "java"):
        assert board.find_drive() is None


@pytest.fixture
def windll():
    """
    ctypes.windll only exists on Windows: fake it elsewhere, patch it there
    (as the CircuitPython plugin's tests do).
    """
    if hasattr(ctypes, "windll"):  # pragma: no cover (Windows)
        with mock.patch("ctypes.windll") as fake:
            yield fake
    else:
        ctypes.windll = mock.MagicMock()
        try:
            yield ctypes.windll
        finally:
            del ctypes.windll


def test_windows_volume_label(windll):
    buffer = ctypes.create_unicode_buffer("MICROBIT", 1024)
    with mock.patch("ctypes.create_unicode_buffer", return_value=buffer):
        assert board._windows_volume_label("E:\\") == "MICROBIT"
    assert windll.kernel32.GetVolumeInformationW.call_count == 1


def test_windows_drives(windll):
    """
    Only drive letters that exist are asked for their label, with Windows'
    "no disk in drive" popups switched off meanwhile.
    """
    windll.kernel32.SetErrorMode.return_value = 7
    with mock.patch(
        "nu_microbit.board.os.path.exists",
        side_effect=lambda path: path in ("C:\\", "E:\\"),
    ):
        assert board._windows_drives() == ["C:\\", "E:\\"]
    assert windll.kernel32.SetErrorMode.call_args_list == [mock.call(1), mock.call(7)]


# --- finding the serial port ---


def comport(device, vid=board.MICROBIT_VID, pid=board.MICROBIT_PID, serial="9904"):
    port = mock.MagicMock()
    port.device = device
    port.vid = vid
    port.pid = pid
    port.serial_number = serial
    return port


def test_find_serial_port():
    ports = [
        comport("/dev/ttyUSB0", vid=0x1A86, pid=0x7523),
        comport("/dev/ttyACM0", serial="99040001"),
    ]
    with mock.patch("nu_microbit.board.list_ports.comports", return_value=ports):
        assert board.find_serial_port() == "/dev/ttyACM0"
        assert board.find_serial_port("99040001") == "/dev/ttyACM0"
        assert board.find_serial_port("99060002") is None


def test_find_serial_port_prefers_the_same_board():
    ports = [
        comport("/dev/ttyACM0", serial="99010001"),
        comport("/dev/ttyACM1", serial="99040001"),
    ]
    with mock.patch("nu_microbit.board.list_ports.comports", return_value=ports):
        assert board.find_serial_port("99040001") == "/dev/ttyACM1"


def test_find_serial_port_macos_uses_cu():
    ports = [comport("/dev/tty.usbmodem1102"), comport("/dev/cu.usbmodem1102")]
    with (
        mock.patch("nu_microbit.board.list_ports.comports", return_value=ports),
        mock.patch("nu_microbit.board.sys.platform", "darwin"),
    ):
        assert board.find_serial_port() == "/dev/cu.usbmodem1102"


def test_find_serial_port_none():
    with mock.patch("nu_microbit.board.list_ports.comports", return_value=[]):
        assert board.find_serial_port() is None


# --- asking the board whether it runs MicroPython ---

V2_BANNER = (
    b"\r\nMicroPython v2.1.2 on 2023-10-30; micro:bit v2.1.2 with nRF52833\r\n"
    b'Type "help()" for more information.\r\n>>> '
)
V1_BANNER = (
    b"MicroPython v1.9.2-34-gd64154c73 on 2017-09-01; micro:bit v1.0.1 with "
    b'nRF51822\r\nType "help()" for more information.\r\n>>> '
)


class FakeSerial:
    """
    A serial port that answers Ctrl-B with `reply`, `chunk` bytes per read.
    """

    instances = []

    def __init__(self, port, baudrate, timeout, reply=b"", chunk=16):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reply = reply
        self.chunk = chunk
        self.written = []
        self.pending = b""
        self.closed = False
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def write(self, data):
        self.written.append(data)
        if data == b"\x02":
            self.pending += self.reply

    def reset_input_buffer(self):
        self.pending = b""

    def read(self, size):
        data, self.pending = self.pending[: self.chunk], self.pending[self.chunk :]
        return data


def serial_answering(reply, chunk=16):
    def make(port, baudrate, timeout):
        return FakeSerial(port, baudrate, timeout, reply=reply, chunk=chunk)

    return make


class Clock:
    """A clock that moves on by `step` seconds each time it's read."""

    def __init__(self, step=0.1):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


def test_probe_finds_micropython_v2():
    FakeSerial.instances.clear()
    sleeps = []
    result = board.probe_micropython(
        "/dev/ttyACM0",
        serial_class=serial_answering(V2_BANNER),
        clock=Clock(),
        sleep=sleeps.append,
    )
    assert result.micropython is True
    assert result.version == "2.1.2"
    assert "micro:bit v2.1.2" in result.banner
    (port,) = FakeSerial.instances
    assert (port.port, port.baudrate) == ("/dev/ttyACM0", 115200)
    # Ctrl-C (twice) stops whatever's running, then Ctrl-B asks for the banner.
    assert port.written == [b"\r\x03\x03", b"\x02"]
    assert port.closed
    assert sleeps


def test_probe_finds_micropython_v1():
    result = board.probe_micropython(
        "COM3",
        serial_class=serial_answering(V1_BANNER),
        clock=Clock(),
        sleep=lambda s: None,
    )
    assert (result.micropython, result.version) == (True, "1.0.1")


def test_probe_prompt_without_microbit_banner():
    """
    A MicroPython prompt but no micro:bit banner: MicroPython of some other
    kind (version unknown).
    """
    result = board.probe_micropython(
        "COM3",
        serial_class=serial_answering(b"MicroPython v1.22 on 2024; RP2\r\n>>> "),
        clock=Clock(),
        sleep=lambda s: None,
    )
    assert (result.micropython, result.version) == (True, None)


def test_probe_silence_means_no_micropython():
    """A MakeCode program (or nothing) doesn't answer: no MicroPython."""
    clock = Clock(step=0.5)
    result = board.probe_micropython(
        "COM3",
        timeout=3,
        serial_class=serial_answering(b""),
        clock=clock,
        sleep=lambda s: None,
    )
    assert result == board.Probe(False, None, "")
    assert clock.now >= 3


def test_probe_open_error_propagates():
    def broken(port, baudrate, timeout):
        raise OSError("busy")

    with pytest.raises(OSError):
        board.probe_micropython("COM3", serial_class=broken, sleep=lambda s: None)


def test_probe_uses_pyserial_by_default():
    with mock.patch(
        "nu_microbit.board.serial.Serial", side_effect=serial_answering(V2_BANNER)
    ) as opened:
        result = board.probe_micropython("/dev/ttyACM0", sleep=lambda s: None)
    assert result.version == "2.1.2"
    opened.assert_called_once_with("/dev/ttyACM0", 115200, timeout=0.1)
