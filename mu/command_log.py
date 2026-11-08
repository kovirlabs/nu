"""
A log of the commands Nu runs on the learner's behalf.

Nu manages the learner's Python environment with `uv`. Rather than hiding
that, every uv command Nu runs (creating the environment, adding, removing
and listing packages, running a script with inline dependencies) is recorded
here exactly as it ran, so the learner can see it — and type it themselves.
The `Uv` wrapper in `mu.virtual_environment` records each command it runs,
so no caller can forget to, and plugins add theirs (e.g. micro:bit's
`mpremote`) with `Host.log_command`.

GUI-free on purpose: the UI renders `command_log.render()` (see the
"What Nu Ran" section of the admin dialog), and each command also goes to
Nu's normal log file at INFO level, with uv's absolute path.

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

import collections
import datetime
import logging
import ntpath
import shlex
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

#: How many commands the log keeps (the oldest are forgotten first).
MAX_RECORDS = 50
#: How many lines of each command's output are kept.
TAIL_LINES = 12
#: Longer output lines (e.g. `uv pip list --format=json`) are cut to this.
MAX_LINE_LENGTH = 200


def quote_command(argv, windows=None):
    """
    Return `argv` as one line the learner could paste into a terminal:
    quoted for Windows' `cmd`/PowerShell (`windows=True`) or a POSIX shell.
    `windows` defaults to the platform Nu is running on.
    """
    if windows is None:
        windows = sys.platform == "win32"
    if windows:
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def program_name(path):
    """
    The name a learner would type for the program at `path`:
    `/opt/nu/bin/uv` and `C:\\Nu\\uv.exe` are both just `uv`.
    """
    name = ntpath.basename(path)  # Handles both / and \ separators.
    if name.lower().endswith(".exe"):
        name = name[: -len(".exe")]
    return name


class CommandRecord:
    """
    One command Nu ran: the real argv (`argv[0]` is the absolute path of the
    program), the folder it ran in, when it started, its exit code once
    known, and the last few lines of its output (or a `note` saying where the
    output went instead, e.g. the Run pane).
    """

    def __init__(self, argv, cwd=None, note=None, lock=None):
        self.argv = [str(arg) for arg in argv]
        self.cwd = cwd
        self.note = note
        self.started = datetime.datetime.now()
        self.exit_code = None
        self.finished = False
        self._output = collections.deque(maxlen=TAIL_LINES)
        self._lock = lock or threading.RLock()

    @property
    def program(self):
        """The absolute path of the program that ran."""
        return self.argv[0]

    def display(self, windows=None):
        """
        The command as the learner would type it: `uv pip install cowsay`
        (the program by name, its arguments quoted for the OS).
        """
        return quote_command([program_name(self.program)] + self.argv[1:], windows)

    def full_command(self, windows=None):
        """The command exactly as it ran, with the program's absolute path."""
        return quote_command(self.argv, windows)

    def add_output(self, text):
        """Add (some of) the command's output, keeping only the tail."""
        with self._lock:
            for line in text.splitlines():
                line = line.rstrip()
                if not line:
                    continue
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH] + "…"
                self._output.append(line)

    def output_tail(self):
        """The last lines of output (blank lines dropped), oldest first."""
        with self._lock:
            return list(self._output)

    def finish(self, exit_code, output=None):
        """
        Mark the command finished with `exit_code` (None if it couldn't be
        known), adding any final `output`. Only the first call counts.
        """
        with self._lock:
            if self.finished:
                return
            if output:
                self.add_output(output)
            self.exit_code = exit_code
            self.finished = True
            tail = "\n".join(self._output)
        logger.info(
            "Finished with exit code %s: %s%s",
            exit_code,
            self.display(),
            ("\n" + tail) if tail else "",
        )

    def status(self):
        """A short, human description of how the command got on."""
        if not self.finished:
            return _("still running")
        if self.exit_code is None:
            return _("finished")
        if self.exit_code == 0:
            return _("finished OK (exit code 0)")
        return _("failed (exit code {})").format(self.exit_code)


class CommandLog:
    """
    A bounded, thread-safe, in-memory log of `CommandRecord`s (the uv
    environment is first created on a worker thread, everything else on the
    Qt thread).
    """

    def __init__(self, max_records=MAX_RECORDS):
        self._lock = threading.RLock()
        self._records = collections.deque(maxlen=max_records)

    def start(self, argv, cwd=None, note=None):
        """
        Record that the command `argv` is starting (in folder `cwd`), and
        return its `CommandRecord` for the caller to `finish()`.
        """
        record = CommandRecord(argv, cwd=cwd, note=note, lock=self._lock)
        with self._lock:
            self._records.append(record)
        logger.info(
            "Nu ran: %s (program: %s; folder: %s)",
            record.display(),
            record.program,
            cwd or "-",
        )
        return record

    def records(self):
        """The recorded commands, oldest first."""
        with self._lock:
            return list(self._records)

    def clear(self):
        """Forget every recorded command."""
        with self._lock:
            self._records.clear()

    def render(self):
        """
        The log as plain text for the learner: each command as they'd type it
        (after a `$` prompt), when and where it ran and how it went, then the
        tail of its output. Newest last.
        """
        records = self.records()
        if not records:
            return _("Nu hasn't run any commands yet.")
        blocks = []
        for record in records:
            details = [record.started.strftime("%H:%M:%S")]
            if record.cwd:
                details.append(_("in {}").format(record.cwd))
            details.append(record.status())
            lines = ["$ " + record.display(), "  " + " · ".join(details)]
            lines += ["  | " + line for line in record.output_tail()]
            if record.note:
                lines.append("  " + record.note)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


#: The log of the commands Nu runs for the learner (one per app).
command_log = CommandLog()
