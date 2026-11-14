"""
The files on a micro:bit: listing them, copying them to and from the
learner's computer, and deleting them, through mpremote's Python API (what
`mpremote fs ls`, `fs cp` and `fs rm` do). Like flashing, a GUI-free job run
on a worker thread (see `worker.py`), with everything that touches the board
or the disk injected so tests swap in fakes.

Each job is one press of a button in the Files pane: it opens the board's
serial port, does its operation, lists the files again (so the pane shows
the result) and closes the port. Every operation is recorded in "What Nu
Ran" as the mpremote command a learner could type.

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

import ast
import errno
import logging
import os
from dataclasses import dataclass, field
from typing import Callable

from . import board
from .flash import FlashError, mpremote_transport

logger = logging.getLogger(__name__)

# What a job does.
LIST = "list"
GET = "get"  # micro:bit -> computer
PUT = "put"  # computer -> micro:bit
DELETE = "delete"

#: The note on every command in "What Nu Ran".
NOTE = "Nu did this itself, through mpremote's Python API."
#: Lists the board's files as [(name, size), ...]. mpremote's own `fs_listdir`
#: needs `os.ilistdir`, which micro:bit MicroPython doesn't have: its flat file
#: system has `os.listdir` and `os.size` (as uflash/microfs used). Other
#: MicroPythons have `os.stat` instead, and folders, which are left out.
LIST_CODE = """\
import os
r = []
for n in os.listdir():
    try:
        r.append((n, os.size(n)))
    except AttributeError:
        s = os.stat(n)
        if not s[0] & 0x4000:
            r.append((n, s[6]))
print(repr(r))
"""


@dataclass(frozen=True)
class BoardFile:
    """A file on the micro:bit."""

    name: str
    size: int


@dataclass
class FilesIO:
    """Everything a files job does to the outside world."""

    transport: Callable = mpremote_transport
    find_serial_port: Callable = board.find_serial_port
    read_file: Callable = None
    write_file: Callable = None

    def __post_init__(self):
        self.read_file = self.read_file or _read_file
        self.write_file = self.write_file or _write_file


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()


def _write_file(path, data):
    with open(path, "wb") as f:
        f.write(data)


def local_files(folder):
    """
    The files in the learner's micro:bit folder `folder` (not its folders,
    nor hidden files), by name; [] if it can't be read.
    """
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(
        (
            name
            for name in names
            if not name.startswith(".") and os.path.isfile(os.path.join(folder, name))
        ),
        key=str.casefold,
    )


@dataclass
class FilesJob:
    """
    One file operation: `action` is LIST, GET (copy `names` from the
    micro:bit into `local_dir`), PUT (copy the local files `paths` onto the
    micro:bit) or DELETE (remove `names` from the micro:bit). Then the
    board's files are listed into `files`. `port` is the board Nu's device
    selector shows (None: find one). `status(text)` reports progress;
    `log_command(argv, note)` records a command (returning a record with
    `finish(code, output)`).
    """

    action: str
    local_dir: str
    status: Callable
    log_command: Callable
    port: str = None
    names: list = field(default_factory=list)
    paths: list = field(default_factory=list)
    io: FilesIO = field(default_factory=FilesIO)
    # Filled in as it runs.
    files: list = None
    done_message: str = ""
    error: FlashError = None
    _cancelled: bool = False

    def cancel(self):
        """Ask the job to stop before its next file (Nu is quitting)."""
        self._cancelled = True

    def run(self):
        """Do the operation, then list the board's files. True if it worked."""
        transport = None
        try:
            if not self.port:
                self.port = self.io.find_serial_port()
            if not self.port:
                raise FlashError(
                    _("Could not find an attached BBC micro:bit."),
                    _(
                        "Please make sure the micro:bit is plugged into this "
                        "computer with a USB cable that carries data (some "
                        "cables only charge), wait a few seconds and try again."
                    ),
                )
            self.status(_("Connecting to the micro:bit…"))
            transport = self._open()
            {
                LIST: lambda t: None,
                GET: self._get,
                PUT: self._put,
                DELETE: self._delete,
            }[self.action](transport)
            self.files = self._list(transport)
        except FlashError as ex:
            self.error = ex
        except Exception as ex:
            logger.exception("Working with the micro:bit's files failed")
            self.error = self._problem(ex)
        finally:
            if transport is not None:
                try:
                    transport.exit_raw_repl()
                except Exception:
                    logger.info("Leaving the raw REPL failed", exc_info=True)
                try:
                    transport.close()
                except Exception:
                    logger.info("Closing the micro:bit's port failed", exc_info=True)
        if self.error:
            logger.info("micro:bit files: %s", self.error.message)
            return False
        if not self.done_message:
            self.done_message = _("Your micro:bit has {} files.").format(
                len(self.files)
            )
        return True

    # --- the operations ---

    def _open(self):
        """Open the port and enter the raw REPL (stopping the board's program)."""
        try:
            transport = self.io.transport(self.port)
        except PermissionError as ex:
            raise FlashError(
                _("Nu isn't allowed to use the micro:bit's serial connection."),
                _(
                    "Opening {port} failed: {error}\n\n"
                    "On Linux, your user needs to be in the group that owns "
                    "serial ports. In a terminal, type:\n"
                    "sudo usermod -a -G dialout $USER\n"
                    "then log out and log back in."
                ).format(port=self.port, error=ex),
            ) from ex
        # Like mpremote: the first raw REPL entry soft-resets, stopping the
        # learner's program so it can't get in the way.
        transport.enter_raw_repl(soft_reset=True)
        return transport

    def _command(self, *args):
        return self.log_command(["mpremote", "connect", self.port, "fs", *args], NOTE)

    def _check_cancelled(self):
        if self._cancelled:
            raise FlashError(_("Stopped."))

    def _list(self, transport):
        record = self._command("ls")
        try:
            output = transport.exec(LIST_CODE)
            entries = ast.literal_eval(output.decode("utf-8").strip())
        except Exception as ex:
            record.finish(1, str(ex))
            raise
        files = sorted(
            (BoardFile(str(name), int(size)) for name, size in entries),
            key=lambda f: f.name.casefold(),
        )
        record.finish(0, "\n".join(f"{f.size:>7} {f.name}" for f in files))
        return files

    def _get(self, transport):
        for name in self.names:
            self._check_cancelled()
            target = os.path.join(self.local_dir, name)
            record = self._command("cp", ":" + name, target)
            self.status(_("Copying {} to your computer…").format(name))
            try:
                data = transport.fs_readfile(name)
                self.io.write_file(target, data)
            except Exception as ex:
                record.finish(1, str(ex))
                raise
            record.finish(0)
        self.done_message = _("Copied {} to your computer.").format(_names(self.names))

    def _put(self, transport):
        names = []
        for path in self.paths:
            self._check_cancelled()
            name = os.path.basename(path)
            record = self._command("cp", path, ":" + name)

            def progress(done, total, name=name):
                self.status(
                    _("Copying {} onto the micro:bit… {}%").format(
                        name, min(100, int(100 * done / total)) if total else 0
                    )
                )

            self.status(_("Copying {} onto the micro:bit…").format(name))
            try:
                data = self.io.read_file(path)
                transport.fs_writefile(name, data, progress_callback=progress)
            except Exception as ex:
                record.finish(1, str(ex))
                raise
            record.finish(0)
            names.append(name)
        self.done_message = _("Copied {} onto the micro:bit.").format(_names(names))

    def _delete(self, transport):
        for name in self.names:
            self._check_cancelled()
            record = self._command("rm", ":" + name)
            self.status(_("Deleting {} from the micro:bit…").format(name))
            try:
                transport.fs_rmfile(name)
            except Exception as ex:
                record.finish(1, str(ex))
                raise
            record.finish(0)
        self.done_message = _("Deleted {} from the micro:bit.").format(
            _names(self.names)
        )

    def _problem(self, ex):
        """What to tell the learner when talking to the board failed."""
        if getattr(ex, "errno", None) == errno.ENOSPC:
            return FlashError(
                _("There isn't room on the micro:bit."),
                _(
                    "Its storage is full. Delete some files from the micro:bit "
                    "and try again."
                ),
            )
        if isinstance(ex, PermissionError):
            return FlashError(
                _("Nu couldn't write that file on your computer."),
                str(ex),
            )
        return FlashError(
            _("Nu couldn't work with the micro:bit's files."),
            _(
                "Talking to MicroPython on {port} failed: {error}\n\n"
                "Press the micro:bit's reset button and try again. If it "
                "keeps happening, hold Shift and click Flash to put "
                "MicroPython back on the micro:bit."
            ).format(port=self.port, error=ex or type(ex).__name__),
        )


def _names(names):
    """'a.py', 'a.py and b.py' or '3 files', for a status line."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return _("{} and {}").format(*names)
    return _("{} files").format(len(names))
