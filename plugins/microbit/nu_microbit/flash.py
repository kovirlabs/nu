"""
Flashing: getting the learner's code (and, when it's needed, MicroPython
itself) onto a micro:bit. A GUI-free state machine, run on a worker thread
(see `worker.py`); everything that touches the board, the disk or the network
is a function on `BoardIO`, so tests swap in fakes.

    FIND_DRIVE -> READ_DETAILS -> FIND_PORT -> PROBE
    PROBE -> COPY_MAIN                    (MicroPython is running)
    PROBE -> FIRMWARE -> COPY_HEX -> WAIT_REMOUNT -> WAIT_REPL -> COPY_MAIN
                                          (it isn't, or the learner asked)
    COPY_MAIN -> DONE; any step can end in FAILED.

Each step reports a status line for the learner, and each one with a command
the learner could type (downloading the firmware, copying it to the drive,
mpremote) records that command in "What Nu ran".

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

import errno
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from . import board, firmware

logger = logging.getLogger(__name__)

# States.
FIND_DRIVE = "find drive"
READ_DETAILS = "read DETAILS.TXT"
FIND_PORT = "find serial port"
PROBE = "probe REPL"
FIRMWARE = "get firmware"
COPY_HEX = "copy firmware"
WAIT_REMOUNT = "wait for remount"
WAIT_REPL = "wait for MicroPython"
COPY_MAIN = "copy main.py"
DONE = "done"
FAILED = "failed"

#: Seconds to wait for the drive to go away once the firmware is copied
#: (DAPLink remounts it when it has flashed the file), and to come back.
REMOUNT_GONE_TIMEOUT = 30
REMOUNT_BACK_TIMEOUT = 60
#: Seconds to wait for MicroPython's REPL after flashing it.
REPL_TIMEOUT = 20
POLL_INTERVAL = 0.5
HEX_CHUNK = 16 * 1024
#: mpremote's own `reset` command (a hard reset, so main.py runs).
RESET_CODE = "import time, machine; time.sleep_ms(100); machine.reset()"


def mpremote_transport(port):
    """
    Open `port` with mpremote's serial transport: what `mpremote connect
    <port>` does. Imported here, so Nu starts even if mpremote is missing.
    """
    from mpremote.transport_serial import SerialTransport

    return SerialTransport(port, baudrate=board.BAUDRATE)


def copy_hex(source, drive, progress=None, cancelled=None):
    """
    Copy the .hex file `source` onto the micro:bit's `drive`: DAPLink flashes
    it as it arrives. `progress(done, total)` follows the bytes.

    An error before the last byte means the copy failed (the board was
    unplugged). Once every byte is written, DAPLink may already be
    remounting the drive, so an error closing the file is only logged: the
    REPL check after the remount says whether it worked.
    """
    total = os.path.getsize(source)
    target = os.path.join(drive, os.path.basename(source))
    done = 0
    out = open(target, "wb")
    try:
        with open(source, "rb") as hex_file:
            for chunk in iter(lambda: hex_file.read(HEX_CHUNK), b""):
                if cancelled and cancelled():
                    raise FlashError(_("Flashing stopped."))
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except BaseException:
        try:
            out.close()
        except OSError:
            pass
        raise
    try:
        out.flush()
        os.fsync(out.fileno())
        out.close()
    except OSError as ex:
        logger.info("Closing %s after the last byte: %r (expected)", target, ex)


@dataclass
class BoardIO:
    """Everything the job does to the outside world."""

    find_drive: Callable = board.find_drive
    read_details: Callable = board.read_details
    read_fail_txt: Callable = board.read_fail_txt
    find_serial_port: Callable = board.find_serial_port
    probe: Callable = board.probe_micropython
    local_firmware: Callable = firmware.local_copy
    download_firmware: Callable = firmware.download
    copy_hex: Callable = copy_hex
    transport: Callable = mpremote_transport
    sleep: Callable = time.sleep
    clock: Callable = time.monotonic


class FlashError(Exception):
    """A step failed; `message` and `information` are for the learner."""

    def __init__(self, message, information=""):
        super().__init__(message)
        self.message = message
        self.information = information


def _version_tuple(version):
    try:
        return tuple(int(part) for part in version.split("+")[0].split("."))
    except (AttributeError, ValueError):
        return None


@dataclass
class FlashJob:
    """
    One press of Flash. `code` is the bytes to put in main.py; `port` and
    `serial_number` the board Nu's device selector shows (either may be None);
    `source_name` the tab's file name, for the command shown to the learner;
    `force_firmware` puts MicroPython back on even if it's running.
    `status(text)` reports progress; `log_command(argv, note)` records a
    command (and returns its record, with `finish(code, output)`).
    """

    code: bytes
    cache_dir: str
    status: Callable
    log_command: Callable
    port: str = None
    serial_number: str = None
    source_name: str = "main.py"
    force_firmware: bool = False
    io: BoardIO = field(default_factory=BoardIO)
    windows: bool = None
    # Filled in as it runs.
    state: str = FIND_DRIVE
    history: list = field(default_factory=list)
    drive: str = None
    details: board.BoardDetails = None
    probe_result: board.Probe = None
    firmware_path: str = None
    done_message: str = ""
    error: FlashError = None
    _cancelled: bool = False

    def __post_init__(self):
        if self.windows is None:
            self.windows = sys.platform == "win32"

    # --- running ---

    def cancel(self):
        """Ask the job to stop at the next chance (Nu is quitting)."""
        self._cancelled = True

    def cancelled(self):
        return self._cancelled

    def _check_cancelled(self):
        if self._cancelled:
            raise FlashError(_("Flashing stopped."))

    def run(self):
        """Run every step; return True if the code is on the board."""
        steps = {
            FIND_DRIVE: self.find_drive,
            READ_DETAILS: self.read_details,
            FIND_PORT: self.find_port,
            PROBE: self.probe,
            FIRMWARE: self.get_firmware,
            COPY_HEX: self.copy_firmware,
            WAIT_REMOUNT: self.wait_for_remount,
            WAIT_REPL: self.wait_for_micropython,
            COPY_MAIN: self.copy_main,
        }
        try:
            while self.state in steps:
                self._check_cancelled()
                self.history.append(self.state)
                logger.info("micro:bit flash: %s", self.state)
                self.state = steps[self.state]()
        except FlashError as ex:
            self.error = ex
        except Exception as ex:
            logger.exception("Flashing the micro:bit failed")
            self.error = FlashError(
                _("There was a problem flashing the micro:bit."),
                _(
                    "Please don't unplug the micro:bit while it's flashing. "
                    "Nu's log has the details:\n{}"
                ).format(ex),
            )
        if self.error:
            logger.info("micro:bit flash failed: %s", self.error.message)
            self.state = FAILED
            self.history.append(FAILED)
            return False
        self.history.append(DONE)
        return True

    # --- the steps ---

    def find_drive(self):
        self.status(_("Looking for the micro:bit…"))
        self.drive = self.io.find_drive()
        if self.drive is None and self.io.find_drive(board.MAINTENANCE_LABEL):
            raise FlashError(
                _("Your micro:bit is in maintenance mode."),
                _(
                    "Its drive is called MAINTENANCE, which happens when it's "
                    "plugged in with its reset button held down. Unplug it, "
                    "plug it back in without pressing any buttons, and press "
                    "Flash again."
                ),
            )
        return READ_DETAILS

    def read_details(self):
        if self.drive is None:
            logger.info("No MICROBIT drive: carrying on with the serial port")
            return FIND_PORT
        try:
            self.details = self.io.read_details(self.drive)
        except OSError as ex:
            logger.warning("Couldn't read DETAILS.TXT on %s: %r", self.drive, ex)
            return FIND_PORT
        logger.info("micro:bit details: %s", self.details)
        if self.details.board_id and self.details.version is None:
            raise FlashError(
                _("Nu doesn't know this board."),
                _(
                    "Its drive says it's board {board_id} (interface "
                    "version {daplink}), which isn't a micro:bit Nu knows. "
                    "If it's a new micro:bit, a newer Nu may support it."
                ).format(
                    board_id=self.details.board_id,
                    daplink=self.details.daplink_version or "?",
                ),
            )
        return FIND_PORT

    def find_port(self):
        if not self.port:
            self.port = self.io.find_serial_port()
        if not self.port:
            if self.drive:
                raise FlashError(
                    _("Nu can't talk to the micro:bit."),
                    _(
                        "It found the micro:bit's MICROBIT drive but not its "
                        "serial connection, which it needs to copy your code. "
                        "Unplug the micro:bit, plug it back in, wait a few "
                        "seconds and press Flash again."
                    ),
                )
            raise FlashError(
                _("Could not find an attached BBC micro:bit."),
                _(
                    "Please make sure the micro:bit is plugged into this "
                    "computer with a USB cable that carries data (some cables "
                    "only charge), wait a few seconds and press Flash again."
                ),
            )
        return PROBE

    def probe(self):
        self.status(_("Checking for MicroPython on the micro:bit…"))
        try:
            self.probe_result = self.io.probe(self.port)
        except PermissionError as ex:
            raise self._permission_problem(ex)
        except OSError as ex:
            raise FlashError(
                _("Nu can't talk to the micro:bit."),
                _(
                    "Opening its serial connection ({port}) failed: {error}\n\n"
                    "Close any other program using the micro:bit, then unplug "
                    "it, plug it back in and press Flash again."
                ).format(port=self.port, error=ex),
            )
        logger.info("Probe: %s", self.probe_result)
        if self.probe_result.micropython and not self.force_firmware:
            return COPY_MAIN
        return FIRMWARE

    def _permission_problem(self, ex):
        return FlashError(
            _("Nu isn't allowed to use the micro:bit's serial connection."),
            _(
                "Opening {port} failed: {error}\n\n"
                "On Linux, your user needs to be in the group that owns "
                "serial ports. In a terminal, type:\n"
                "sudo usermod -a -G dialout $USER\n"
                "then log out, log back in and press Flash again."
            ).format(port=self.port, error=ex),
        )

    def _board_version(self):
        if self.details and self.details.version:
            return self.details.version
        return board.board_version(board.board_id_from_serial(self.serial_number))

    def get_firmware(self):
        if self.drive is None:
            raise FlashError(
                _("Nu can't find the micro:bit's MICROBIT drive."),
                _(
                    "There's no MicroPython on your micro:bit yet, and Nu "
                    "puts it there by copying it onto the micro:bit's drive. "
                    "Wait a few seconds for the drive to appear and press "
                    "Flash again. (On ChromeOS, share the MICROBIT drive with "
                    "Linux in the Files app first.)"
                ),
            )
        version = self._board_version()
        if version is None:
            raise FlashError(
                _("Nu can't tell which micro:bit this is."),
                _(
                    "It needs to know whether it's a V1 or a V2 to pick the "
                    "right MicroPython, but the drive has no readable "
                    "DETAILS.TXT. Unplug the micro:bit, plug it back in and "
                    "press Flash again."
                ),
            )
        pin = firmware.FIRMWARE[version]
        self.firmware_path = self.io.local_firmware(pin, self.cache_dir)
        if self.firmware_path:
            return COPY_HEX
        destination = os.path.join(self.cache_dir, pin.filename)
        record = self.log_command(
            ["curl", "-L", "-o", destination, pin.url],
            _(
                "Nu downloaded MicroPython itself, then checked its SHA-256 is {}."
            ).format(pin.sha256),
        )

        def progress(done, total):
            self.status(
                _("Downloading MicroPython for the micro:bit V{}… {}%").format(
                    version, _percent(done, total)
                )
            )

        try:
            self.firmware_path = self.io.download_firmware(
                pin, self.cache_dir, progress=progress, cancelled=self.cancelled
            )
        except firmware.FirmwareUnavailable as ex:
            record.finish(1, ex.message)
            raise FlashError(ex.message, ex.information) from ex
        record.finish(0)
        return COPY_HEX

    def copy_firmware(self):
        if self.windows:
            argv = ["copy", self.firmware_path, self.drive]
        else:
            argv = ["cp", self.firmware_path, self.drive.rstrip("/") + "/"]
        record = self.log_command(argv, None)

        def progress(done, total):
            self.status(
                _("Copying MicroPython onto the micro:bit… {}%").format(
                    _percent(done, total)
                )
            )

        try:
            self.io.copy_hex(
                self.firmware_path, self.drive, progress, cancelled=self.cancelled
            )
        except OSError as ex:
            record.finish(1, str(ex))
            raise FlashError(
                _("Copying MicroPython onto the micro:bit didn't finish."),
                _(
                    "Was it unplugged? ({})\n\nPlug it back in and press "
                    "Flash again. If it shows a sad face or its drive is "
                    "called MAINTENANCE, unplug it and plug it back in first."
                ).format(ex),
            ) from ex
        record.finish(0)
        return WAIT_REMOUNT

    def _poll(self, timeout, done):
        """Call `done()` every POLL_INTERVAL until it's true or `timeout` runs out."""
        deadline = self.io.clock() + timeout
        while True:
            self._check_cancelled()
            if done():
                return True
            if self.io.clock() >= deadline:
                return False
            self.io.sleep(POLL_INTERVAL)

    def wait_for_remount(self):
        self.status(_("Waiting for the micro:bit to restart…"))
        gone = self._poll(REMOUNT_GONE_TIMEOUT, lambda: self.io.find_drive() is None)
        if not gone:
            logger.info("The drive never went away; checking it anyway")
        found = []

        def back():
            drive = self.io.find_drive()
            if drive:
                found.append(drive)
            return bool(drive)

        if not self._poll(REMOUNT_BACK_TIMEOUT, back):
            raise FlashError(
                _("The micro:bit didn't come back after flashing."),
                _(
                    "Nu copied MicroPython onto it, but its drive didn't "
                    "reappear. Unplug it, plug it back in and press Flash "
                    "again."
                ),
            )
        self.drive = found[-1]
        failure = self.io.read_fail_txt(self.drive)
        if failure:
            raise FlashError(
                _("The micro:bit couldn't use the MicroPython file."),
                _("It left this message on its drive (FAIL.TXT):\n\n{}").format(
                    failure
                ),
            )
        return WAIT_REPL

    def wait_for_micropython(self):
        self.status(_("Waiting for MicroPython to start…"))

        def answers():
            port = (
                self.io.find_serial_port(self.serial_number)
                if self.serial_number
                else None
            ) or self.io.find_serial_port()
            if not port:
                return False
            try:
                result = self.io.probe(port)
            except OSError as ex:
                logger.info("Probe on %s: %r (retrying)", port, ex)
                return False
            if result.micropython:
                self.port = port
                self.probe_result = result
                return True
            return False

        if not self._poll(REPL_TIMEOUT, answers):
            raise FlashError(
                _("MicroPython didn't start on the micro:bit."),
                _(
                    "Nu copied MicroPython onto it, but it didn't answer. "
                    "Unplug the micro:bit, plug it back in and press Flash "
                    "again."
                ),
            )
        return COPY_MAIN

    def copy_main(self):
        argv = [
            "mpremote",
            "connect",
            self.port,
            "fs",
            "cp",
            self.source_name,
            ":main.py",
            "+",
            "reset",
        ]
        record = self.log_command(
            argv, _("Nu did this itself, through mpremote's Python API.")
        )

        def progress(done, total):
            self.status(
                _("Copying your code onto the micro:bit… {}%").format(
                    _percent(done, total)
                )
            )

        self.status(_("Copying your code onto the micro:bit…"))
        transport = None
        try:
            transport = self.io.transport(self.port)
            # Like the mpremote command: the first raw REPL entry soft-resets
            # (stopping the old program), `fs cp` writes the file, `reset`
            # hard-resets so main.py runs.
            transport.enter_raw_repl(soft_reset=True)
            transport.fs_writefile("main.py", self.code, progress_callback=progress)
            transport.exec_raw_no_follow(RESET_CODE)
        except PermissionError as ex:
            record.finish(1, str(ex))
            raise self._permission_problem(ex) from ex
        except Exception as ex:  # mpremote's TransportError, OSError, ...
            record.finish(1, str(ex))
            raise self._copy_problem(ex) from ex
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    logger.info("Closing the micro:bit's port failed", exc_info=True)
        record.finish(0)
        self.done_message = _("Done! Your code is on the micro:bit.")
        hint = self._update_hint()
        if hint:
            self.done_message += " " + hint
        return DONE

    def _copy_problem(self, ex):
        if getattr(ex, "errno", None) == errno.ENOSPC:
            return FlashError(
                _("Your code is too big for the micro:bit."),
                _(
                    "There isn't room for it in the micro:bit's storage. Try "
                    "making it shorter, or delete other files from the "
                    "micro:bit."
                ),
            )
        return FlashError(
            _("Nu couldn't copy your code onto the micro:bit."),
            _(
                "Talking to MicroPython on {port} failed: {error}\n\n"
                "Press the micro:bit's reset button and try again. If it "
                "keeps happening, hold Shift and click Flash to put "
                "MicroPython back on the micro:bit."
            ).format(port=self.port, error=ex or type(ex).__name__),
        )

    def _update_hint(self):
        """A nudge if the board's MicroPython is older than Nu's."""
        if not self.probe_result or not self.probe_result.version:
            return ""
        have = _version_tuple(self.probe_result.version)
        if not have:
            return ""
        pin = firmware.FIRMWARE.get(have[0])
        if pin and have < _version_tuple(pin.version):
            return _(
                "(It has MicroPython {} and Nu has {}: hold Shift and click "
                "Flash to update it.)"
            ).format(self.probe_result.version, pin.version)
        return ""


def _percent(done, total):
    return min(100, int(100 * done / total)) if total else 0
