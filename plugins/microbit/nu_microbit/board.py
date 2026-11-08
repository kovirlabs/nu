"""
Telling which micro:bit is plugged in, finding its drive and serial port, and
asking it whether MicroPython is running. GUI-free, so it can run on the flash
worker's thread and be tested without a board.

A micro:bit's USB interface chip runs DAPLink, which gives the computer two
things: a serial port (the MicroPython REPL, when MicroPython is running) and
a small drive called MICROBIT. Copying a .hex file onto the drive flashes it;
DETAILS.TXT on the drive says which board it is.

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

import ctypes
import glob
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from subprocess import check_output

import serial
from serial.tools import list_ports

logger = logging.getLogger(__name__)

#: DAPLink's USB vendor and product IDs (every micro:bit, V1 and V2).
MICROBIT_VID = 0x0D28
MICROBIT_PID = 0x0204
#: The REPL's speed.
BAUDRATE = 115200
#: The drive's label, and the bootloader's (when the board is started with
#: its reset button held down).
DRIVE_LABEL = "MICROBIT"
MAINTENANCE_LABEL = "MAINTENANCE"
#: DAPLink board IDs: the first four hex digits of the USB serial number and
#: of DETAILS.TXT's "Unique ID". https://tech.microbit.org/latest-revision/
V1_BOARD_IDS = frozenset({"9900", "9901"})
V2_BOARD_IDS = frozenset({"9903", "9904", "9905", "9906"})
#: How long to wait for the REPL to answer, in seconds.
PROBE_TIMEOUT = 3.0

#: The micro:bit MicroPython banner, e.g. "MicroPython v2.1.2 on 2023-10-30;
#: micro:bit v2.1.2 with nRF52833". The second version is the micro:bit
#: release, which is what Nu pins.
BANNER = re.compile(rb"MicroPython \S+ on [^;\r\n]*;\s*micro:bit v?([0-9][\w.+-]*)")
PROMPT = b">>> "


def board_version(board_id):
    """1 or 2 for a micro:bit board ID ("9904"), None if it isn't one."""
    if board_id in V1_BOARD_IDS:
        return 1
    if board_id in V2_BOARD_IDS:
        return 2
    return None


def board_id_from_serial(serial_number):
    """The board ID at the start of a DAPLink USB serial number, or None."""
    head = (serial_number or "")[:4]
    if len(head) == 4 and all(c in "0123456789abcdefABCDEF" for c in head):
        return head
    return None


def board_name(serial_number, description=""):
    """
    What to call the board in Nu's device selector: "BBC micro:bit V1" or
    "V2" when the serial number says, otherwise just "BBC micro:bit".
    """
    version = board_version(board_id_from_serial(serial_number))
    if version:
        return "BBC micro:bit V{}".format(version)
    return "BBC micro:bit"


@dataclass(frozen=True)
class BoardDetails:
    """What DETAILS.TXT says (any of it may be None)."""

    board_id: str
    version: int  # 1, 2, or None for a board Nu doesn't know
    daplink_version: str
    unique_id: str


def parse_details(text):
    """Parse the text of DAPLink's DETAILS.TXT into `BoardDetails`."""
    fields = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.startswith("#"):
            fields.setdefault(key.strip().lower(), value.strip())
    unique_id = fields.get("unique id") or None
    board_id = fields.get("board id") or board_id_from_serial(unique_id)
    daplink = fields.get("interface version") or fields.get("version") or None
    return BoardDetails(board_id, board_version(board_id), daplink, unique_id)


def read_details(drive):
    """Read and parse DETAILS.TXT on the drive at `drive` (OSError if absent)."""
    path = os.path.join(drive, "DETAILS.TXT")
    with open(path, encoding="utf-8", errors="replace") as details_file:
        return parse_details(details_file.read())


def read_fail_txt(drive):
    """
    The text of FAIL.TXT, which DAPLink leaves on the drive when it couldn't
    flash a file, or None if there's none.
    """
    try:
        with open(
            os.path.join(drive, "FAIL.TXT"), encoding="utf-8", errors="replace"
        ) as fail_file:
            return fail_file.read().strip()
    except OSError:
        return None


# --- the drive ---


def _is_label(name, label):
    """MICROBIT, or MICROBIT1 etc. when a second copy is mounted."""
    return name == label or (name.startswith(label) and name[len(label) :].isdigit())


def on_chromeos():
    """True inside ChromeOS's Linux container."""
    return os.path.exists("/mnt/chromeos")


def _posix_drive(label):
    for mount_command in ["mount", "/sbin/mount"]:
        try:
            mount_output = check_output(mount_command).splitlines()
        except FileNotFoundError:
            continue
        except Exception as ex:  # e.g. PermissionError: fall back to the globs
            logger.warning("Couldn't run %s: %r", mount_command, ex)
            continue
        for line in mount_output:
            parts = line.split()
            if len(parts) > 2:
                volume = parts[2].decode("utf-8", "replace")
                if _is_label(os.path.basename(volume), label):
                    return volume
        break
    # Where desktops automount drives (Linux's udisks, macOS).
    for pattern in [
        "/media/*/" + label,
        "/run/media/*/" + label,
        "/media/" + label,
        "/Volumes/" + label,
    ]:
        found = sorted(glob.glob(pattern))
        if found:
            return found[0]
    # ChromeOS shows a drive to Linux only once it's shared with Linux.
    chromeos_path = "/mnt/chromeos/removable/" + label
    if os.path.isdir(chromeos_path):
        return chromeos_path
    return None


def _windows_volume_label(path):
    """
    The volume label of the disk at `path` ("E:\\").
    Code from http://stackoverflow.com/a/12056414 (as Nu's CircuitPython mode).
    """
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(path), buffer, ctypes.sizeof(buffer), None, None, None, None, 0
    )
    return buffer.value


def _windows_drives():
    """
    The drive letters that exist. Windows can pop up "no disk in drive" for
    an empty USB slot; SetErrorMode(SEM_FAILCRITICALERRORS) stops that.
    """
    old_mode = ctypes.windll.kernel32.SetErrorMode(1)
    try:
        return [
            "{}:\\".format(letter)
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if os.path.exists("{}:\\".format(letter))
        ]
    finally:
        ctypes.windll.kernel32.SetErrorMode(old_mode)


def find_drive(label=DRIVE_LABEL):
    """
    The path of the mounted drive called `label` (MICROBIT by default), or
    None if there isn't one.
    """
    if os.name == "posix":
        return _posix_drive(label)
    if os.name == "nt":
        for drive in _windows_drives():
            if _windows_volume_label(drive) == label:
                return drive
        return None
    return None


# --- the serial port ---


def find_serial_port(serial_number=None):
    """
    The serial port of a plugged-in micro:bit (the one with `serial_number`,
    if given), found with pyserial, or None. Safe on any thread.
    """
    for port in list_ports.comports():
        if port.vid != MICROBIT_VID or port.pid != MICROBIT_PID:
            continue
        if serial_number and port.serial_number != serial_number:
            continue
        # macOS lists each port twice; /dev/cu.* is the one to use.
        if sys.platform == "darwin" and not port.device.startswith("/dev/cu"):
            continue
        return port.device
    return None


@dataclass(frozen=True)
class Probe:
    """What the REPL said: MicroPython or not, its micro:bit version, the text."""

    micropython: bool
    version: str
    banner: str


def probe_micropython(
    port,
    timeout=PROBE_TIMEOUT,
    serial_class=None,
    clock=time.monotonic,
    sleep=time.sleep,
):
    """
    Ask the board on `port` whether it runs MicroPython: stop whatever's
    running (Ctrl-C), ask the REPL for its banner (Ctrl-B) and read for up
    to `timeout` seconds. A board running a MakeCode program says nothing.
    Errors opening the port (it's busy, or gone) are raised.
    """
    serial_class = serial_class or serial.Serial
    data = b""
    with serial_class(port, BAUDRATE, timeout=0.1) as connection:
        connection.write(b"\r\x03\x03")
        sleep(0.2)
        connection.reset_input_buffer()
        connection.write(b"\x02")
        deadline = clock() + timeout
        while clock() < deadline:
            data += connection.read(256)
            if data.endswith(PROMPT):
                break
    match = BANNER.search(data)
    text = data.decode("utf-8", "replace").strip()
    if match:
        return Probe(True, match.group(1).decode("ascii", "replace"), text)
    if PROMPT in data:
        return Probe(True, None, text)
    return Probe(False, None, text)
