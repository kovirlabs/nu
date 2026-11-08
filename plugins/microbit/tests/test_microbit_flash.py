# -*- coding: utf-8 -*-
"""
Tests for nu_microbit.flash: the flash state machine, run against a fake
micro:bit (drive, DETAILS.TXT, serial port, REPL, firmware cache and an
mpremote transport that records what it was asked to do).
"""

import errno
import os
from unittest import mock

import pytest

from nu_microbit import board, firmware, flash

V2 = board.BoardDetails("9904", 2, "0255", "9904abc")
V1 = board.BoardDetails("9900", 1, "0234", "9900abc")
MICROPYTHON = board.Probe(True, "2.1.2", "MicroPython v2.1.2 …; micro:bit v2.1.2")
NOTHING = board.Probe(False, None, "")


class FakeRecord:
    def __init__(self, argv, note):
        self.argv = argv
        self.note = note
        self.finished = None

    def finish(self, code, output=None):
        self.finished = (code, output)


class FakeTransport:
    def __init__(self, port, fail=None, fail_on="fs_writefile"):
        self.port = port
        self.calls = []
        self.fail = fail
        self.fail_on = fail_on
        self.closed = False

    def _maybe_fail(self, name):
        if self.fail is not None and self.fail_on == name:
            raise self.fail

    def enter_raw_repl(self, soft_reset=True):
        self.calls.append(("enter_raw_repl", soft_reset))
        self._maybe_fail("enter_raw_repl")

    def fs_writefile(self, dest, data, progress_callback=None):
        self.calls.append(("fs_writefile", dest, data))
        self._maybe_fail("fs_writefile")
        progress_callback(len(data) // 2, len(data))
        progress_callback(len(data), len(data))

    def exec_raw_no_follow(self, code):
        self.calls.append(("exec_raw_no_follow", code))

    def close(self):
        self.closed = True
        self._maybe_fail("close")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeMicrobit:
    """
    A scripted micro:bit. `drives` is what successive find_drive() calls
    return (the last value repeats); likewise `probes`.
    """

    def __init__(
        self,
        drives=("/media/l/MICROBIT",),
        details=V2,
        port="/dev/ttyACM0",
        probes=(MICROPYTHON,),
        firmware_path="/cache/micropython-microbit-v2.1.2.hex",
        maintenance=False,
    ):
        self.drives = list(drives)
        self.details = details
        self.port = port
        self.probes = list(probes)
        self.firmware_path = firmware_path
        self.maintenance = maintenance
        self.transports = []
        self.copied = []
        self.downloaded = []
        self.fail_txt = None
        self.transport_error = None
        self.transport_fail_on = "fs_writefile"
        self.clock = Clock()

    def find_drive(self, label=board.DRIVE_LABEL):
        if label == board.MAINTENANCE_LABEL:
            return "/media/l/MAINTENANCE" if self.maintenance else None
        return self.drives.pop(0) if len(self.drives) > 1 else self.drives[0]

    def read_details(self, drive):
        if isinstance(self.details, Exception):
            raise self.details
        return self.details

    def find_serial_port(self, serial_number=None):
        return self.port

    def probe(self, port):
        result = self.probes.pop(0) if len(self.probes) > 1 else self.probes[0]
        if isinstance(result, Exception):
            raise result
        return result

    def local_firmware(self, pin, cache_dir):
        return self.firmware_path

    def download_firmware(self, pin, cache_dir, progress, cancelled):
        self.downloaded.append(pin)
        progress(1, 2)
        progress(2, 2)
        return os.path.join(cache_dir, pin.filename)

    def copy_hex(self, source, drive, progress, cancelled=None):
        self.copied.append((source, drive))
        progress(1, 4)
        progress(4, 4)

    def transport(self, port):
        transport = FakeTransport(port, self.transport_error, self.transport_fail_on)
        self.transports.append(transport)
        return transport

    def read_fail_txt(self, drive):
        return self.fail_txt

    def io(self):
        return flash.BoardIO(
            find_drive=self.find_drive,
            read_details=self.read_details,
            read_fail_txt=self.read_fail_txt,
            find_serial_port=self.find_serial_port,
            probe=self.probe,
            local_firmware=self.local_firmware,
            download_firmware=self.download_firmware,
            copy_hex=self.copy_hex,
            transport=self.transport,
            sleep=self.clock.sleep,
            clock=self.clock,
        )


def make_job(microbit, **kwargs):
    statuses = []
    records = []

    def log_command(argv, note):
        record = FakeRecord(argv, note)
        records.append(record)
        return record

    job = flash.FlashJob(
        code=kwargs.pop("code", b"from microbit import *\ndisplay.scroll('hi')\n"),
        cache_dir="/cache",
        status=statuses.append,
        log_command=log_command,
        io=microbit.io(),
        windows=kwargs.pop("windows", False),
        **kwargs,
    )
    job.statuses = statuses
    job.records = records
    return job


# --- the quick path: MicroPython is already there ---


def test_micropython_running_copies_main():
    microbit = FakeMicrobit()
    job = make_job(microbit, source_name="/home/l/mu_code/microbit/hello.py")
    assert job.run() is True
    assert job.history == [
        flash.FIND_DRIVE,
        flash.READ_DETAILS,
        flash.FIND_PORT,
        flash.PROBE,
        flash.COPY_MAIN,
        flash.DONE,
    ]
    (transport,) = microbit.transports
    assert transport.port == "/dev/ttyACM0"
    assert transport.calls == [
        ("enter_raw_repl", True),
        ("fs_writefile", "main.py", job.code),
        ("exec_raw_no_follow", flash.RESET_CODE),
    ]
    assert transport.closed
    (record,) = job.records
    assert record.argv == [
        "mpremote",
        "connect",
        "/dev/ttyACM0",
        "fs",
        "cp",
        "/home/l/mu_code/microbit/hello.py",
        ":main.py",
        "+",
        "reset",
    ]
    assert "mpremote's Python API" in record.note
    assert record.finished == (0, None)
    assert job.done_message == "Done! Your code is on the micro:bit."
    assert "Copying your code onto the micro:bit… 100%" in job.statuses
    assert microbit.copied == [] and microbit.downloaded == []


def test_uses_the_selected_port():
    microbit = FakeMicrobit(port=None)
    job = make_job(microbit, port="COM7")
    assert job.run() is True
    assert microbit.transports[0].port == "COM7"


def test_no_drive_is_fine_when_micropython_runs():
    """
    Linux desktops without automounting never mount the drive: copying the
    code only needs the serial port.
    """
    microbit = FakeMicrobit(drives=(None,))
    job = make_job(microbit)
    assert job.run() is True
    assert job.details is None


def test_unreadable_details_is_fine_when_micropython_runs():
    microbit = FakeMicrobit(details=OSError("gone"))
    assert make_job(microbit).run() is True


def test_older_micropython_gets_an_update_hint():
    microbit = FakeMicrobit(
        probes=(board.Probe(True, "2.0.0", "…"),),
    )
    job = make_job(microbit)
    assert job.run() is True
    assert "It has MicroPython 2.0.0 and Nu has 2.1.2" in job.done_message
    assert "hold Shift" in job.done_message


@pytest.mark.parametrize("version", ["2.1.2", "2.2.0-beta.1", None, "x.y"])
def test_no_hint_for_current_or_unknown_versions(version):
    microbit = FakeMicrobit(probes=(board.Probe(True, version, "…"),))
    job = make_job(microbit)
    assert job.run() is True
    assert job.done_message == "Done! Your code is on the micro:bit."


# --- the full path: MicroPython goes on first ---


def test_no_micropython_flashes_firmware_then_copies_main():
    microbit = FakeMicrobit(
        drives=("/media/l/MICROBIT", None, None, "/media/l/MICROBIT"),
        probes=(NOTHING, NOTHING, MICROPYTHON),
    )
    job = make_job(microbit)
    assert job.run() is True
    assert job.history == [
        flash.FIND_DRIVE,
        flash.READ_DETAILS,
        flash.FIND_PORT,
        flash.PROBE,
        flash.FIRMWARE,
        flash.COPY_HEX,
        flash.WAIT_REMOUNT,
        flash.WAIT_REPL,
        flash.COPY_MAIN,
        flash.DONE,
    ]
    assert microbit.copied == [
        ("/cache/micropython-microbit-v2.1.2.hex", "/media/l/MICROBIT")
    ]
    cp, mpremote = job.records
    assert cp.argv == [
        "cp",
        "/cache/micropython-microbit-v2.1.2.hex",
        "/media/l/MICROBIT/",
    ]
    assert cp.finished == (0, None)
    assert mpremote.argv[0] == "mpremote"
    for status in [
        "Copying MicroPython onto the micro:bit… 100%",
        "Waiting for the micro:bit to restart…",
        "Waiting for MicroPython to start…",
    ]:
        assert status in job.statuses


def test_v1_gets_v1_firmware():
    microbit = FakeMicrobit(
        details=V1, probes=(NOTHING, MICROPYTHON), firmware_path=None
    )
    job = make_job(microbit)
    assert job.run() is True
    assert microbit.downloaded == [firmware.FIRMWARE[1]]


def test_copy_command_on_windows():
    microbit = FakeMicrobit(drives=("E:\\",), probes=(NOTHING, MICROPYTHON))
    job = make_job(microbit, windows=True)
    assert job.run() is True
    assert job.records[0].argv == [
        "copy",
        "/cache/micropython-microbit-v2.1.2.hex",
        "E:\\",
    ]


def test_forced_reflash_even_with_micropython():
    """Shift+Flash: the learner asked for MicroPython to go back on."""
    microbit = FakeMicrobit()
    job = make_job(microbit, force_firmware=True)
    assert job.run() is True
    assert flash.FIRMWARE in job.history
    assert microbit.copied


def test_firmware_downloaded_when_not_cached():
    microbit = FakeMicrobit(probes=(NOTHING, MICROPYTHON), firmware_path=None)
    job = make_job(microbit)
    assert job.run() is True
    assert microbit.downloaded == [firmware.FIRMWARE[2]]
    download, cp, _ = job.records
    pin = firmware.FIRMWARE[2]
    assert download.argv == [
        "curl",
        "-L",
        "-o",
        os.path.join("/cache", pin.filename),
        pin.url,
    ]
    assert pin.sha256 in download.note
    assert download.finished == (0, None)
    assert "Downloading MicroPython for the micro:bit V2… 100%" in job.statuses
    assert cp.argv[1] == os.path.join("/cache", pin.filename)


def test_firmware_offline():
    microbit = FakeMicrobit(probes=(NOTHING,), firmware_path=None)

    def offline(pin, cache_dir, progress, cancelled):
        raise firmware.FirmwareUnavailable("No internet.", "Put X in Y.")

    microbit.download_firmware = offline
    job = make_job(microbit)
    assert job.run() is False
    assert (job.error.message, job.error.information) == ("No internet.", "Put X in Y.")
    assert job.records[0].finished == (1, "No internet.")
    assert microbit.copied == []


def test_board_version_from_serial_number_when_details_unreadable():
    microbit = FakeMicrobit(details=OSError("no"), probes=(NOTHING, MICROPYTHON))
    microbit.firmware_path = None
    job = make_job(microbit, serial_number="9900000123")
    assert job.run() is True
    assert microbit.downloaded == [firmware.FIRMWARE[1]]


def test_unknown_version_without_details_fails():
    microbit = FakeMicrobit(details=OSError("no"), probes=(NOTHING,))
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu can't tell which micro:bit this is."


def test_no_drive_and_no_micropython_fails():
    microbit = FakeMicrobit(drives=(None,), probes=(NOTHING,))
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu can't find the micro:bit's MICROBIT drive."
    assert "ChromeOS" in job.error.information


def test_copy_interrupted():
    microbit = FakeMicrobit(probes=(NOTHING,))

    def unplugged(source, drive, progress, cancelled=None):
        raise OSError(errno.EIO, "Input/output error")

    microbit.copy_hex = unplugged
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == (
        "Copying MicroPython onto the micro:bit didn't finish."
    )
    assert "unplugged" in job.error.information
    assert job.records[0].finished[0] == 1


def test_drive_never_comes_back():
    microbit = FakeMicrobit(drives=("/media/l/MICROBIT", None), probes=(NOTHING,))
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "The micro:bit didn't come back after flashing."
    # It waited for the drive to go, then for it to come back.
    assert microbit.clock.now >= flash.REMOUNT_BACK_TIMEOUT


def test_drive_never_goes_away_is_checked_anyway():
    """
    If the remount was too quick to see, the drive is checked as it is and
    the REPL check decides.
    """
    microbit = FakeMicrobit(probes=(NOTHING, MICROPYTHON))
    job = make_job(microbit)
    assert job.run() is True
    assert microbit.clock.now >= flash.REMOUNT_GONE_TIMEOUT


def test_drive_comes_back_under_another_name():
    microbit = FakeMicrobit(
        drives=("/media/l/MICROBIT", None, "/media/l/MICROBIT1"),
        probes=(NOTHING, MICROPYTHON),
    )
    job = make_job(microbit)
    assert job.run() is True
    assert job.drive == "/media/l/MICROBIT1"


def test_fail_txt_after_flashing():
    microbit = FakeMicrobit(
        drives=("/media/l/MICROBIT", None, "/media/l/MICROBIT"), probes=(NOTHING,)
    )
    microbit.fail_txt = "error: The hex file cannot be decoded."
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "The micro:bit couldn't use the MicroPython file."
    assert "cannot be decoded" in job.error.information


def test_micropython_never_starts():
    microbit = FakeMicrobit(
        drives=("/media/l/MICROBIT", None, "/media/l/MICROBIT"),
        probes=(NOTHING, OSError("busy"), NOTHING),
    )
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "MicroPython didn't start on the micro:bit."
    assert microbit.clock.now >= flash.REPL_TIMEOUT


def test_wait_for_micropython_refinds_the_port():
    """
    After flashing, the port is found again (by serial number first): it can
    come back under another name.
    """
    microbit = FakeMicrobit(probes=(NOTHING, MICROPYTHON))
    asked = []
    ports = iter([None, None, "/dev/ttyACM1"])

    def find_serial_port(serial_number=None):
        asked.append(serial_number)
        return next(ports, "/dev/ttyACM1")

    microbit.find_serial_port = find_serial_port
    job = make_job(microbit, port="/dev/ttyACM0", serial_number="99040001")
    assert job.run() is True
    assert job.port == "/dev/ttyACM1"
    assert asked[:2] == ["99040001", None]


# --- refusing politely ---


def test_unknown_board_refused():
    microbit = FakeMicrobit(details=board.BoardDetails("0240", None, "0254", "0240"))
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu doesn't know this board."
    assert "0240" in job.error.information and "0254" in job.error.information
    assert microbit.transports == []


def test_maintenance_mode():
    microbit = FakeMicrobit(drives=(None,), maintenance=True)
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Your micro:bit is in maintenance mode."


def test_no_microbit_at_all():
    microbit = FakeMicrobit(drives=(None,), port=None)
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Could not find an attached BBC micro:bit."


def test_drive_but_no_serial_port():
    microbit = FakeMicrobit(port=None)
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu can't talk to the micro:bit."
    assert "MICROBIT drive" in job.error.information


def test_probe_permission_denied_explains_dialout():
    microbit = FakeMicrobit(probes=(PermissionError(13, "Permission denied"),))
    job = make_job(microbit)
    assert job.run() is False
    assert "isn't allowed" in job.error.message
    assert "dialout" in job.error.information


def test_probe_port_busy():
    microbit = FakeMicrobit(probes=(OSError(16, "Device or resource busy"),))
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu can't talk to the micro:bit."
    assert "/dev/ttyACM0" in job.error.information


# --- copying main.py going wrong ---


def test_copy_main_transport_error():
    microbit = FakeMicrobit()
    microbit.transport_error = RuntimeError("could not enter raw repl")
    microbit.transport_fail_on = "enter_raw_repl"
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Nu couldn't copy your code onto the micro:bit."
    assert "could not enter raw repl" in job.error.information
    assert "hold Shift" in job.error.information
    assert job.records[-1].finished == (1, "could not enter raw repl")
    assert microbit.transports[0].closed


def test_copy_main_too_big():
    microbit = FakeMicrobit()
    microbit.transport_error = OSError(errno.ENOSPC, "No space left")
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "Your code is too big for the micro:bit."


def test_copy_main_permission_denied():
    microbit = FakeMicrobit()

    def denied(port):
        raise PermissionError(13, "Permission denied")

    microbit.transport = denied
    job = make_job(microbit)
    assert job.run() is False
    assert "dialout" in job.error.information


def test_copy_main_close_error_is_ignored():
    microbit = FakeMicrobit()
    microbit.transport_error = OSError("port vanished on reset")
    microbit.transport_fail_on = "close"
    job = make_job(microbit)
    assert job.run() is True


# --- stopping, and the unexpected ---


def test_cancel_stops_before_the_next_step():
    microbit = FakeMicrobit()
    job = make_job(microbit)
    job.status = lambda text: job.cancel()
    assert job.run() is False
    assert job.error.message == "Flashing stopped."
    assert job.cancelled()


def test_cancel_stops_a_wait():
    microbit = FakeMicrobit(drives=("/media/l/MICROBIT",), probes=(NOTHING,))
    job = make_job(microbit)
    real_sleep = microbit.clock.sleep

    def sleep(seconds):
        real_sleep(seconds)
        job.cancel()

    job.io.sleep = sleep
    assert job.run() is False
    assert job.error.message == "Flashing stopped."


def test_unexpected_error_is_reported_not_raised():
    microbit = FakeMicrobit()

    def broken(drive):
        raise ZeroDivisionError("oops")

    microbit.read_details = broken
    job = make_job(microbit)
    assert job.run() is False
    assert job.error.message == "There was a problem flashing the micro:bit."
    assert "oops" in job.error.information
    assert job.state == flash.FAILED


def test_default_io_is_the_real_thing():
    io = flash.BoardIO()
    assert io.find_drive is board.find_drive
    assert io.probe is board.probe_micropython
    assert io.download_firmware is firmware.download
    assert io.transport is flash.mpremote_transport


def test_windows_defaults_to_the_platform():
    with mock.patch("nu_microbit.flash.sys.platform", "win32"):
        job = flash.FlashJob(b"", "/c", print, print)
    assert job.windows is True


def test_mpremote_transport_opens_the_port():
    pytest.importorskip("mpremote")
    with mock.patch("mpremote.transport_serial.SerialTransport") as transport:
        assert flash.mpremote_transport("/dev/ttyACM0") is transport.return_value
    transport.assert_called_once_with("/dev/ttyACM0", baudrate=115200)


# --- copy_hex, on real files ---


def test_copy_hex(tmp_path):
    source = tmp_path / "micropython.hex"
    source.write_bytes(b"x" * (flash.HEX_CHUNK * 2 + 10))
    drive = tmp_path / "MICROBIT"
    drive.mkdir()
    seen = []
    flash.copy_hex(str(source), str(drive), lambda d, t: seen.append((d, t)))
    assert (drive / "micropython.hex").read_bytes() == source.read_bytes()
    assert seen[-1] == (flash.HEX_CHUNK * 2 + 10,) * 2
    assert len(seen) == 3


def test_copy_hex_drive_gone_before_the_end(tmp_path):
    source = tmp_path / "micropython.hex"
    source.write_bytes(b"x" * 10)
    with pytest.raises(OSError):
        flash.copy_hex(str(source), str(tmp_path / "missing"))


def test_copy_hex_write_fails_midway(tmp_path):
    source = tmp_path / "micropython.hex"
    source.write_bytes(b"x" * 10)
    drive = tmp_path / "MICROBIT"
    drive.mkdir()
    out = mock.MagicMock()
    out.write.side_effect = OSError(errno.EIO, "unplugged")
    out.close.side_effect = OSError("and closing too")
    with mock.patch("builtins.open", side_effect=[out, open(source, "rb")]):
        with pytest.raises(OSError, match="unplugged"):
            flash.copy_hex(str(source), str(drive))


def test_copy_hex_error_after_the_last_byte_is_ignored(tmp_path):
    """DAPLink may be remounting already: closing can fail, harmlessly."""
    source = tmp_path / "micropython.hex"
    source.write_bytes(b"x" * 10)
    drive = tmp_path / "MICROBIT"
    drive.mkdir()
    with mock.patch("nu_microbit.flash.os.fsync", side_effect=OSError("gone")):
        flash.copy_hex(str(source), str(drive))


def test_copy_hex_cancelled(tmp_path):
    source = tmp_path / "micropython.hex"
    source.write_bytes(b"x" * 10)
    drive = tmp_path / "MICROBIT"
    drive.mkdir()
    with pytest.raises(flash.FlashError):
        flash.copy_hex(str(source), str(drive), cancelled=lambda: True)


def test_percent():
    assert flash._percent(1, 3) == 33
    assert flash._percent(5, 3) == 100
    assert flash._percent(5, 0) == 0
