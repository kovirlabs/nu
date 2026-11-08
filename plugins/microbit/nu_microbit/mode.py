"""
The BBC micro:bit mode for Nu: write MicroPython for the micro:bit, flash it
onto the board, and talk to it through the REPL and the plotter.

Copyright (c) 2015-2021 Nicholas H.Tollervey and others (see the AUTHORS file).
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
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from mu.plugin import Device, MicroPythonMode

from . import board, flash, worker
from .api import MICROBIT_APIS

logger = logging.getLogger(__name__)

#: The toolbar's Flash button (and its icon, images/microbit-flash.svg).
FLASH_BUTTON = "microbit-flash"


class MicrobitMode(MicroPythonMode):
    """
    The micro:bit mode. The REPL and plotter are MicroPythonMode's (the
    micro:bit's REPL is an ordinary MicroPython REPL on its serial port);
    Flash runs a `flash.FlashJob` on a worker thread.
    """

    name = _("BBC micro:bit")
    short_name = "microbit"
    description = _("Write MicroPython for the BBC micro:bit.")
    icon = "microbit"
    # Every micro:bit's USB interface (DAPLink) has these ids.
    #               VID,                 PID,                manufacturer, name
    valid_boards = [(board.MICROBIT_VID, board.MICROBIT_PID, None, "BBC micro:bit")]

    # Modules built into micro:bit MicroPython, which the learner's files
    # mustn't shadow.
    module_names = {
        "antigravity",
        "array",
        "audio",
        "builtins",
        "collections",
        "gc",
        "log",
        "love",
        "machine",
        "math",
        "microbit",
        "micropython",
        "music",
        "neopixel",
        "os",
        "power",
        "radio",
        "random",
        "speech",
        "struct",
        "sys",
        "this",
        "time",
        "ucollections",
        "uerrno",
        "ustruct",
        "utime",
    }

    flash_thread = None
    flash_worker = None
    flash_job = None
    active = False
    _reopen = ()

    def actions(self):
        """The toolbar buttons: Flash, REPL and (if available) Plotter."""
        buttons = [
            {
                "name": FLASH_BUTTON,
                "display_name": _("Flash"),
                "description": _(
                    "Flash your code onto the micro:bit. (Hold Shift to put "
                    "MicroPython itself back on.)"
                ),
                "handler": self.flash,
                "shortcut": "F3",
            },
            {
                "name": "repl",
                "display_name": _("REPL"),
                "description": _("Use the REPL to live-code on the micro:bit."),
                "handler": self.toggle_repl,
                "shortcut": "Ctrl+Shift+I",
            },
        ]
        if self.host.plotter_available:
            buttons.append(
                {
                    "name": "plotter",
                    "display_name": _("Plotter"),
                    "description": _("Plot incoming REPL data."),
                    "handler": self.toggle_plotter,
                    "shortcut": "CTRL+Shift+P",
                }
            )
        return buttons

    def api(self):
        """Autocomplete and call tips: what every Python has, plus micro:bit's."""
        return self.host.shared_apis() + MICROBIT_APIS

    def workspace_dir(self):
        """
        A `microbit` folder in the learner's workspace (the code lives on
        the board too, but it's kept here first).
        """
        workspace = self.host.workspace_dir()
        path = os.path.join(workspace, "microbit")
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            logger.exception("Couldn't make %s", path)
            return workspace
        return path

    def compatible_board(self, port):
        """
        A micro:bit's serial port (`port` is a Qt QSerialPortInfo): DAPLink's
        USB ids, named V1 or V2 from the board ID its serial number starts
        with.
        """
        if (port.vendorIdentifier(), port.productIdentifier()) != (
            board.MICROBIT_VID,
            board.MICROBIT_PID,
        ):
            return None
        serial_number = port.serialNumber()
        return Device(
            port.vendorIdentifier(),
            port.productIdentifier(),
            self.port_path(port.portName()),
            serial_number,
            port.manufacturer(),
            self.name,
            self.short_name,
            board.board_name(serial_number, port.description()),
        )

    def activate(self):
        self.active = True
        super().activate()

    def deactivate(self):
        self.active = False
        super().deactivate()

    # --- flashing ---

    def shift_held(self):
        """True if the Shift key is down (Shift+Flash re-flashes MicroPython)."""
        modifiers = QGuiApplication.queryKeyboardModifiers()
        return bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

    def board_io(self):
        """What the flash job uses to reach the board (tests replace it)."""
        return flash.BoardIO()

    def flash(self, event=None):
        """
        Put the current tab's code onto the micro:bit as main.py, putting
        MicroPython on first if it isn't there (or, with Shift held, if the
        learner asks).
        """
        if self.flash_thread is not None:
            self.host.show_status(_("Nu is already flashing the micro:bit…"))
            return
        text = self.host.current_text()
        if text is None:
            self.host.show_message(
                _("There's no code to flash."),
                _("Open or write some code first, then press Flash."),
            )
            return
        force = self.shift_held()
        if force and not self.host.confirm(
            _("Put MicroPython back on your micro:bit?"),
            _(
                "Nu will copy a fresh MicroPython onto the micro:bit, then "
                "your code. It takes about a minute: don't unplug the "
                "micro:bit until it's done."
            ),
            "Question",
        ):
            return
        device = self.host.current_device
        if device is not None and device.short_mode_name != self.short_name:
            device = None
        # The REPL and plotter hold the serial port: let go of it, and open
        # them again afterwards.
        self._reopen = tuple(
            name
            for name, is_open in (("repl", self.repl), ("plotter", self.plotter))
            if is_open
        )
        if self.plotter:
            self.remove_plotter()
        if self.repl:
            self.remove_repl()
        if self._reopen:
            self.host.show_status(
                _("Closed the REPL so Nu can use the micro:bit's connection.")
            )
        job = flash.FlashJob(
            code=text.encode("utf-8"),
            cache_dir=os.path.join(self.host.data_dir("microbit"), "firmware"),
            status=None,  # set by the worker
            log_command=self.host.log_command,
            port=device.port if device else None,
            serial_number=str(device.serial_number) if device else None,
            source_name=self.host.current_path() or "main.py",
            force_firmware=force,
            io=self.board_io(),
        )
        self.set_buttons(**{FLASH_BUTTON: False, "repl": False, "plotter": False})
        self.flash_job = job
        self.flash_thread, self.flash_worker = worker.start(
            job,
            self.on_flash_status,
            self.on_flash_succeeded,
            self.on_flash_failed,
            self.on_flash_finished,
        )

    def on_flash_status(self, text):
        self.host.show_status(text, 60)

    def on_flash_succeeded(self, message):
        self.host.show_status(message, 10)

    def on_flash_failed(self, message, information):
        self.host.show_status(message, 10)
        self.host.show_message(message, information)

    def on_flash_finished(self):
        """The worker's thread has stopped: tidy up and give the buttons back."""
        self.flash_thread = None
        self.flash_worker = None
        self.flash_job = None
        reopen, self._reopen = self._reopen, ()
        if not self.active:
            return
        self.set_buttons(**{FLASH_BUTTON: True, "repl": True, "plotter": True})
        if "repl" in reopen:
            self.add_repl()
        if "plotter" in reopen:
            self.add_plotter()

    def stop(self):
        """Nu is quitting: stop a flash in progress (as soon as it can)."""
        if self.flash_job is not None:
            self.flash_job.cancel()
        if self.flash_thread is not None:
            self.flash_thread.quit()
            self.flash_thread.wait(2000)
