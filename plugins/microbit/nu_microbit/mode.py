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

from . import board, files, flash, worker
from .api import MICROBIT_APIS
from .files_pane import FilesPane

logger = logging.getLogger(__name__)

#: The toolbar's Flash button (and its icon, images/microbit-flash.svg).
FLASH_BUTTON = "microbit-flash"
#: The toolbar's Files button (and its icon, images/microbit-files.svg).
FILES_BUTTON = "microbit-files"
#: How long Nu waits, when quitting, for a flash to stop.
STOP_TIMEOUT_MS = 5000


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
    #: What "from microbit import *" brings in, so Check can still spot
    #: undefined names in code that uses it.
    star_imports = {
        "microbit": [
            "accelerometer",
            "button_a",
            "button_b",
            "compass",
            "display",
            "i2c",
            "Image",
            "panic",
            "pin0",
            "pin1",
            "pin2",
            "pin3",
            "pin4",
            "pin5",
            "pin6",
            "pin7",
            "pin8",
            "pin9",
            "pin10",
            "pin11",
            "pin12",
            "pin13",
            "pin14",
            "pin15",
            "pin16",
            "pin19",
            "pin20",
            "reset",
            "running_time",
            "sleep",
            "spi",
            "temperature",
            "uart",
        ]
    }

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
    files_pane = None
    files_handle = None
    files_thread = None
    files_worker = None
    files_job = None
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
                "name": FILES_BUTTON,
                "display_name": _("Files"),
                "description": _(
                    "See the files on your micro:bit, and copy files to and from it."
                ),
                "handler": self.toggle_files,
                "shortcut": "F4",
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
        # Nu takes the Files pane away with the mode.
        self.files_pane = None
        self.files_handle = None

    def busy(self):
        """True while a flash or a files job is using the micro:bit."""
        return self.flash_thread is not None or self.files_thread is not None

    def _device_port(self):
        """The serial port of the micro:bit in the device selector, or None."""
        device = self.host.current_device
        if device is None or device.short_mode_name != self.short_name:
            return None
        return device.port

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
        if self.files_thread is not None:
            self.host.show_status(_("Nu is busy with the micro:bit's files…"))
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
        self.set_buttons(
            **{
                FLASH_BUTTON: False,
                FILES_BUTTON: False,
                "repl": False,
                "plotter": False,
            }
        )
        if self.files_pane is not None:
            self.files_pane.set_busy(True, _("Flashing…"))
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
        if self.flash_thread is not None:
            # QThread.finished comes just before the thread really ends: let
            # it end before dropping the last reference, or Qt aborts when
            # the QThread is garbage-collected while still running.
            self.flash_thread.wait()
        self.flash_thread = None
        self.flash_worker = None
        self.flash_job = None
        reopen, self._reopen = self._reopen, ()
        if not self.active:
            return
        if self.files_pane is not None:
            # The REPL and plotter stay off while the Files pane has the
            # board; show what the flash did to its files.
            self.set_buttons(**{FLASH_BUTTON: True, FILES_BUTTON: True})
            self.files_pane.set_busy(False)
            self.run_files_job(files.LIST)
            return
        self.set_buttons(
            **{FLASH_BUTTON: True, FILES_BUTTON: True, "repl": True, "plotter": True}
        )
        if "repl" in reopen:
            self.add_repl()
        if "plotter" in reopen:
            self.add_plotter()

    # --- the Files pane ---

    def toggle_files(self, event=None):
        """Show the Files pane, or take it away."""
        if self.files_pane is None:
            self.open_files()
        else:
            self.close_files()

    def open_files(self):
        """
        Show the Files pane and list the micro:bit's files. It needs the
        board's serial port, so the REPL and plotter close (and can't be
        opened) while it's there.
        """
        if self.files_pane is not None:
            return
        if self.busy():
            self.host.show_status(_("Nu is busy with the micro:bit…"))
            return
        if self.repl or self.plotter:
            if self.plotter:
                self.remove_plotter()
            if self.repl:
                self.remove_repl()
            self.host.show_status(
                _("Closed the REPL so Nu can use the micro:bit's connection.")
            )
        pane = FilesPane(self.workspace_dir())
        pane.refresh_requested.connect(lambda: self.run_files_job(files.LIST))
        pane.get_requested.connect(self.copy_to_computer)
        pane.put_requested.connect(self.copy_to_microbit)
        pane.delete_requested.connect(self.delete_from_microbit)
        pane.open_requested.connect(self.host.open_file)
        self.files_pane = pane
        self.files_handle = self.host.add_pane(pane, _("micro:bit Files"))
        self.set_buttons(repl=False, plotter=False)
        self.run_files_job(files.LIST)

    def close_files(self):
        """Take the Files pane away; the REPL and plotter can be used again."""
        if self.files_handle is not None:
            self.host.remove_pane(self.files_handle)
        self.files_pane = None
        self.files_handle = None
        if self.active and not self.busy():
            self.set_buttons(repl=True, plotter=True)

    def files_io(self):
        """What a files job uses to reach the board (tests replace it)."""
        return files.FilesIO()

    def run_files_job(self, action, names=(), paths=()):
        """Do `action` (see `files.FilesJob`) on the micro:bit, off the GUI thread."""
        if self.busy():
            self.host.show_status(_("Nu is busy with the micro:bit…"))
            return
        job = files.FilesJob(
            action=action,
            local_dir=self.workspace_dir(),
            status=None,  # set by the worker
            log_command=self.host.log_command,
            port=self._device_port(),
            names=list(names),
            paths=list(paths),
            io=self.files_io(),
        )
        self.files_job = job
        if self.files_pane is not None:
            self.files_pane.set_busy(True, _("Talking to the micro:bit…"))
        self.set_buttons(**{FLASH_BUTTON: False, FILES_BUTTON: False})
        self.files_thread, self.files_worker = worker.start(
            job,
            self.on_files_status,
            self.on_files_succeeded,
            self.on_files_failed,
            self.on_files_finished,
        )

    def on_files_status(self, text):
        if self.files_pane is not None:
            self.files_pane.show_message(text)

    def on_files_succeeded(self, message):
        job = self.files_job
        if self.files_pane is None:
            return
        if job is not None and job.files is not None:
            self.files_pane.show_board_files(job.files)
        self.files_pane.show_local_files()
        self.files_pane.show_message(
            message
            + " "
            + _(
                "(Your micro:bit's program stops while Nu looks at its files: "
                "press its reset button to run it again.)"
            )
        )

    def on_files_failed(self, message, information):
        if self.files_pane is not None:
            self.files_pane.show_message(message)
            self.files_pane.show_local_files()
        self.host.show_message(message, information)

    def on_files_finished(self):
        """The files job's thread has stopped: tidy up, give the buttons back."""
        if self.files_thread is not None:
            self.files_thread.wait()  # see on_flash_finished
        self.files_thread = None
        self.files_worker = None
        self.files_job = None
        if self.files_pane is not None:
            self.files_pane.set_busy(False)
        if self.active:
            self.set_buttons(**{FLASH_BUTTON: True, FILES_BUTTON: True})

    def copy_to_computer(self, names):
        """Copy `names` from the micro:bit into the micro:bit folder."""
        folder = self.workspace_dir()
        existing = [n for n in names if os.path.exists(os.path.join(folder, n))]
        if existing and not self.host.confirm(
            _("Replace {} on your computer?").format(", ".join(existing)),
            _(
                "Your micro:bit folder already has a file with that name. "
                "Copying from the micro:bit replaces it."
            ),
            "Question",
        ):
            return
        self.run_files_job(files.GET, names=names)

    def copy_to_microbit(self, paths):
        """Copy the files `paths` onto the micro:bit."""
        on_board = {f.name for f in (self.files_pane.board_files or [])}
        existing = [
            os.path.basename(p) for p in paths if os.path.basename(p) in on_board
        ]
        if existing and not self.host.confirm(
            _("Replace {} on the micro:bit?").format(", ".join(existing)),
            _(
                "The micro:bit already has a file with that name. Copying "
                "from your computer replaces it."
            ),
            "Question",
        ):
            return
        self.run_files_job(files.PUT, paths=paths)

    def delete_from_microbit(self, names):
        """Delete `names` from the micro:bit, after asking."""
        if not self.host.confirm(
            _("Delete {} from the micro:bit?").format(", ".join(names)),
            _(
                "This can't be undone. Copy them to your computer first if "
                "you want to keep them."
            ),
            "Warning",
        ):
            return
        self.run_files_job(files.DELETE, names=names)

    def stop(self):
        """Nu is quitting: stop a flash or files job in progress (soon)."""
        for job, thread in (
            (self.flash_job, self.flash_thread),
            (self.files_job, self.files_thread),
        ):
            if job is not None:
                job.cancel()
            if thread is not None:
                thread.quit()
                # Steps notice the cancel within a second or so, but one may
                # be blocked on the board or the network for longer. Qt aborts
                # if a running QThread is destroyed, so as a last resort (Nu
                # is quitting anyway) stop it outright.
                if not thread.wait(STOP_TIMEOUT_MS):
                    logger.warning("The micro:bit thread didn't stop; terminating it")
                    thread.terminate()
                    thread.wait()
