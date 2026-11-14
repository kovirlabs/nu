import os
import sys
from collections import namedtuple
import functools
import glob
import json
import logging
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile

from PyQt6.QtCore import (
    QObject,
    QProcess,
    pyqtSignal,
    QTimer,
    QProcessEnvironment,
)

from . import wheels
from . import settings
from . import config
from . import __version__ as mu_version
from .command_log import command_log, quote_command

wheels_dirpath = os.path.dirname(wheels.__file__)

logger = logging.getLogger(__name__)

ENCODING = sys.stdout.encoding if hasattr(sys.stdout, "encoding") else "utf-8"


class VirtualEnvironmentError(Exception):
    def __init__(self, message):
        self.message = message


class VirtualEnvironmentTimeoutError(VirtualEnvironmentError):
    def __init__(self, message, timeout):
        super().__init__(message)
        self.timeout = timeout


class VirtualEnvironmentEnsureError(VirtualEnvironmentError):
    pass


class VirtualEnvironmentCreateError(VirtualEnvironmentError):
    pass


def is_within(path, folder):
    """Whether `path` is `folder` or inside it (comparing real paths)."""
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    try:
        return os.path.commonpath([path, folder]) == folder
    except ValueError:  # e.g. on different Windows drives
        return False


#: A named environment's name: a plain folder name (see
#: `VirtualEnvironment.environment_name_problem`).
# What Nu records about an environment it made, inside the environment
# (see `VirtualEnvironment.write_record`), so every environment keeps its own.
ENVIRONMENT_RECORD = "nu-environment.json"
ENVIRONMENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ENVIRONMENT_NAME_MAX_LENGTH = 40
#: Names Windows keeps for devices: they can't be folder names there.
WINDOWS_RESERVED_NAMES = {"con", "prn", "aux", "nul"} | {
    "%s%d" % (device, n) for device in ("com", "lpt") for n in range(1, 10)
}


def same_path(path, other):
    """Whether two paths name the same file or folder (as written)."""
    return os.path.normcase(os.path.abspath(path)) == os.path.normcase(
        os.path.abspath(other)
    )


def is_named_environment(path):
    """
    Whether `path` is one of the learner's named environments: a folder
    directly in ``config.ENVS_DIR`` (the default one lives elsewhere).
    """
    return same_path(os.path.dirname(os.path.abspath(path)), config.ENVS_DIR)


def environment_interpreter(path, windows=None):
    """Where the Python of the environment at `path` is (or would be)."""
    if windows is None:
        windows = sys.platform == "win32"
    if windows:
        return os.path.join(path, "scripts", "python.exe")
    return os.path.join(path, "bin", "python")


def directory_is_venv(path, interpreter=None):
    """
    Whether the folder at `path` looks like a Python environment.

    There appears to be no canonical way to tell. Often the presence of a
    pyvenv.cfg file is enough, but this isn't always there. Specifically, on
    debian it's not when created by virtualenv. So we fall back to finding an
    executable python command where we expect (`interpreter`).

    On windows os.access X_OK is close to meaningless, but it will succeed
    for executable files (and everything else). On Posix it does distinguish
    executable files.
    """
    if os.path.isfile(os.path.join(path, "pyvenv.cfg")):
        return True
    if interpreter is None:
        interpreter = environment_interpreter(path)
    return os.access(interpreter, os.X_OK)


def pyvenv_version(path):
    """
    The Python version (e.g. ``"3.11.15"``) of the environment at `path` as
    recorded in its ``pyvenv.cfg`` (``version_info`` from uv, ``version``
    from the standard library's venv), or None if unknown.
    """
    try:
        with open(os.path.join(path, "pyvenv.cfg"), encoding="utf-8") as cfg:
            lines = cfg.read().splitlines()
    except OSError:
        return None
    for line in lines:
        key, _sep, value = line.partition("=")
        if key.strip() in ("version_info", "version") and value.strip():
            return value.strip()
    return None


def activate_command(path, windows=None):
    """
    The command to activate the environment at `path` in a terminal, quoted
    for this OS (or Windows', if `windows`): running ``Scripts\\activate``
    works in both cmd and PowerShell; elsewhere it's ``source bin/activate``.
    """
    if windows is None:
        windows = sys.platform == "win32"
    if windows:
        return quote_command([os.path.join(path, "scripts", "activate")], windows)
    return quote_command(["source", os.path.join(path, "bin", "activate")], windows)


def environment_display_name(folder):
    """
    A short, stable name for the environment in `folder` (a folder name):
    without the Python version and creation timestamp that
    `VirtualEnvironment._generate_dirpath` adds (``mu_venv-311-20261108-030353``
    → ``mu_venv``), so it doesn't change when Nu re-creates the env.
    """
    return re.sub(r"-\d+-\d{8}-\d{6}$", "", folder)


def compact(text):
    """Remove double line spaces and anything else which might help"""
    compacted = "\n".join(line for line in text.splitlines() if line.strip())
    return compacted or "No output received."


class Process(QObject):
    """
    Use the QProcess mechanism to run a subprocess asynchronously

    This will interact well with Qt Gui objects, eg by connecting the
    `output` signals to an `QTextEdit.append` method and the `started`
    and `finished` signals to a `QPushButton.setEnabled`.

    eg::
        import sys
        from PyQt6.QtCore import *
        from PyQt6.QtWidgets import *

        class Example(QMainWindow):

            def __init__(self):
                super().__init__()
                textEdit = QTextEdit()

                self.setCentralWidget(textEdit)
                self.setGeometry(300, 300, 350, 250)
                self.setWindowTitle('Main window')
                self.show()

                self.process = Process()
                self.process.output.connect(textEdit.append)
                self.process.run(sys.executable, ["-u", "-m", "pip", "list"])

        def main():
            app = QApplication(sys.argv)
            ex = Example()
            sys.exit(app.exec())
    """

    started = pyqtSignal()
    output = pyqtSignal(str)
    finished = pyqtSignal()
    Slots = namedtuple("Slots", ["started", "output", "finished"])
    Slots.__new__.__defaults__ = (None, None, None)

    def __init__(self):
        super().__init__()
        #
        # Always run unbuffered and with UTF-8 IO encoding
        #
        self.environment = QProcessEnvironment.systemEnvironment()
        self.environment.insert("PYTHONUNBUFFERED", "1")
        self.environment.insert("PYTHONIOENCODING", "utf-8")

    def _set_up_run(self, **envvars):
        """Set up common elements of a QProcess run"""
        self.process = QProcess()
        environment = QProcessEnvironment(self.environment)
        for k, v in envvars.items():
            environment.insert(k, v)
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

    def run_blocking(self, command, args, wait_for_s=30.0, **envvars):
        """Run `command` with `args` via QProcess, passing `envvars` as
        environment variables for the process.

        Wait `wait_for_s` seconds for completion and return any stdout/stderr
        """
        logger.info(
            "About to run blocking %s with args %s and envvars %s",
            command,
            args,
            envvars,
        )
        self._set_up_run(**envvars)
        self.process.start(command, args)
        return self.wait(wait_for_s=wait_for_s)

    def run(self, command, args, **envvars):
        """Run `command` asynchronously with `args` via QProcess, passing `envvars`
        as environment variables for the process."""
        logger.info(
            "About to run %s with args %s and envvars %s",
            command,
            args,
            envvars,
        )
        self._set_up_run(**envvars)
        self.process.readyRead.connect(self._readyRead)
        self.process.started.connect(self._started)
        self.process.finished.connect(self._finished)
        partial = functools.partial(self.process.start, command, args)
        QTimer.singleShot(1, partial)

    def wait(self, wait_for_s=30):
        """Wait for the process to complete, optionally timing out.
        Return any stdout/stderr.

        If the process fails to complete in time or returns an error, raise a
        VirtualEnvironmentError
        """
        finished = self.process.waitForFinished(int(1000 * wait_for_s))
        exit_status = self.process.exitStatus()
        exit_code = self.process.exitCode()
        output = self.data()
        #
        # if waitForFinished completes, either the process has successfully finished
        # or it crashed, was terminated or timed out. If it does finish successfully
        # we might still have an error code. In each case we might still have data
        # from stdout/stderr. Unfortunately there's no way to determine that the
        # process was timed out, as opposed to crashing in some other way
        #
        # The three elements in play are:
        #
        # finished (yes/no)
        # exitStatus (normal (0) / crashed (1)) -- we don't currently distinguish
        # exitCode (whatever the program returns; conventionally 0 => ok)
        #
        logger.debug(
            "Finished: %s; exitStatus %s; exitCode %s",
            finished,
            exit_status,
            exit_code,
        )

        #
        # Exceptions raised here will be caught by the crash-handler which will try to
        # generate a URI out of it. There's an upper limit on URI size of ~2000
        #
        if not finished:
            if exit_code and compact(output):
                logger.error(compact(output))
            elif exit_code:
                logger.error(
                    "Process failed with exit code %s but provided no message",
                    exit_code,
                )
            else:
                logger.error("Virtual environment creation timed out")
                raise VirtualEnvironmentTimeoutError(
                    "Virtual environment creation timed out:\n" + compact(output),
                    wait_for_s,
                )

            raise VirtualEnvironmentError(
                "Process did not terminate normally:\n" + compact(output)
            )

        if exit_code != 0:
            #
            # We finished normally but we might still have an error-code on finish
            #
            logger.error(compact(output))
            raise VirtualEnvironmentError(
                "Process finished but with error code %d:\n%s"
                % (exit_code, compact(output))
            )

        return output

    def data(self):
        """Return all the data from the running process, converted to unicode"""
        output = self.process.readAll().data()
        return output.decode(ENCODING, errors="replace")

    def _started(self):
        self.started.emit()

    def _readyRead(self):
        self.output.emit(self.data().strip())

    def _finished(self):
        self.finished.emit()


class Pip(object):
    """
    Proxy for various pip commands

    While this is a fairly useful abstraction in its own right, it's at
    least initially to assist in testing, so we can mock out various
    commands
    """

    def __init__(self, pip_executable):
        self.executable = pip_executable
        self.process = Process()
        self.timeout = 180.0

    def run(self, command, *args, wait_for_s=None, slots=Process.Slots(), **kwargs):
        """
        Run a command with args, treating kwargs as Posix switches.

        eg run("python", version=True)
        run("python", "-c", "import sys; print(sys.executable)")
        """
        #
        # Any keyword args are treated as command-line switches
        # As a special case, a boolean value indicates that the flag
        # is a yes/no switch
        #
        if not wait_for_s:
            wait_for_s = self.timeout
        params = [command, "--disable-pip-version-check"]
        for k, v in kwargs.items():
            switch = k.replace("_", "-")
            if v is False:
                switch = "no-" + switch
            params.append("--" + switch)
            if v is not True and v is not False:
                params.append(str(v))
        params.extend(args)

        if slots.output is None:
            result = self.process.run_blocking(
                self.executable, params, wait_for_s=wait_for_s
            )
            logger.debug("Process output: %s", compact(result.strip()))
            return result
        else:
            if slots.started:
                self.process.started.connect(slots.started)
            self.process.output.connect(slots.output)
            if slots.finished:
                self.process.finished.connect(slots.finished)
            self.process.run(self.executable, params)

    def install(self, packages, slots=Process.Slots(), **kwargs):
        """
        Use pip to install a package or packages.

        If the first parameter is a string one package is installed; otherwise
        it is assumed to be an iterable of package names.

        Any kwargs are passed as command-line switches. A value of None
        indicates a switch without a value (eg --upgrade)
        """
        if isinstance(packages, str):
            return self.run(
                "install", packages, wait_for_s=self.timeout, slots=slots, **kwargs
            )
        else:
            return self.run(
                "install", *packages, wait_for_s=self.timeout, slots=slots, **kwargs
            )

    def uninstall(self, packages, slots=Process.Slots(), **kwargs):
        """
        Use pip to uninstall a package or packages

        If the first parameter is a string one package is uninstalled;
        otherwise it is assumed to be an iterable of package names.

        Any kwargs are passed as command-line switches. A value of None
        indicates a switch without a value (eg --upgrade)
        """
        if isinstance(packages, str):
            return self.run(
                "uninstall",
                packages,
                wait_for_s=self.timeout,
                slots=slots,
                yes=True,
                **kwargs,
            )
        else:
            return self.run(
                "uninstall",
                *packages,
                wait_for_s=self.timeout,
                slots=slots,
                yes=True,
                **kwargs,
            )

    def version(self):
        """
        Get the pip version

        NB this is fairly trivial but is pulled out principally for
        testing purposes
        """
        return self.run("--version")

    def freeze(self):
        """
        Use pip to return a list of installed packages

        NB this is fairly trivial but is pulled out principally for
        testing purposes
        """
        return self.run("freeze")

    def list(self):
        """
        Use pip to return a list of installed packages

        NB this is fairly trivial but is pulled out principally for
        testing purposes
        """
        return self.run("list")

    def installed(self):
        """
        Yield tuples of (package_name, version)

        pip list gives a more consistent view of name/version
        than pip freeze which uses different annotations for
        file-installed wheels and editable (-e) installs
        """
        lines = self.list().splitlines()
        iterlines = iter(lines)
        #
        # The first two lines are headers
        #
        try:
            next(iterlines)
            next(iterlines)
        #
        # cf https://lgtm.com/rules/11000086/
        #
        except StopIteration:
            raise VirtualEnvironmentError("Unable to parse installed packages")

        for line in iterlines:
            #
            # Some lines have a third location element
            #
            name, version = line.split()[:2]
            yield name, version


#
# uv-based environment management (Phase 4, see TODO.md).
#
# `uv` is a single self-contained binary that manages its own Python
# interpreters and creates/maintains virtual environments. Driving the user's
# environment through `uv` decouples it from Mu's own interpreter (so a packaged
# Mu no longer needs a venv-capable bundled Python) and lets us surface the env
# to learners as a real, scriptable thing rather than hidden machinery.
#
# VirtualEnvironment now creates its environment with `uv venv` (see
# `create_venv`) and routes user-package install/remove/list through this
# wrapper; the baseline-wheel install still runs via pip into the seeded venv.
#
UV_ENV_VAR = "MU_UV"


class UvNotFound(VirtualEnvironmentError):
    """Raised when no `uv` executable can be located."""

    def __init__(self, message="Could not locate a `uv` executable"):
        super().__init__(message)


def _uv_from_package():
    """Return the path to the `uv` binary shipped by the PyPI ``uv`` package.

    The ``uv`` wheel (a runtime dependency) bundles the executable and exposes
    its location via ``uv.find_uv_bin()``. In a Briefcase-packaged app this is
    the binary's home: there's no system ``uv`` on ``PATH`` and ``MU_UV`` isn't
    set, but the wheel is installed into the app, so this resolves it without
    any path plumbing. Returns ``None`` if the package isn't importable or the
    binary it points at is missing (e.g. a dev checkout using a standalone uv).
    """
    try:
        import uv as uv_package

        candidate = uv_package.find_uv_bin()
    except (ImportError, AttributeError, FileNotFoundError):
        return None
    return candidate if candidate and os.path.exists(candidate) else None


def canonical_package_name(name):
    """Normalise a package name as PEP 503 does (``Foo_Bar`` -> ``foo-bar``)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def find_uv():
    """Locate the `uv` executable.

    Resolution order: the ``MU_UV`` override → a ``uv`` on the ``PATH`` (dev
    checkouts, and lets a user supply their own) → the binary bundled by the
    PyPI ``uv`` package (the packaged-app path, see :func:`_uv_from_package`).
    Raise :class:`UvNotFound` if none of these is available.
    """
    override = os.environ.get(UV_ENV_VAR)
    if override:
        if os.path.exists(override):
            return override
        raise UvNotFound(
            "%s points at a non-existent uv executable: %s" % (UV_ENV_VAR, override)
        )
    found = shutil.which("uv")
    if found:
        return found
    bundled = _uv_from_package()
    if bundled:
        return bundled
    raise UvNotFound(
        "Could not find a `uv` executable on PATH, via the %s "
        "environment variable, or bundled with the `uv` package" % UV_ENV_VAR
    )


class Uv(object):
    """
    Proxy for the `uv` package/environment manager.

    Wraps the subset of `uv` Mu needs to manage the user's environment —
    creating venvs, installing/removing/listing packages, and running scripts
    (including PEP 723 inline-dependency scripts via ``uv run``). Mirrors the
    blocking + ``Slots``-async calling style of :class:`Pip`, reusing the
    QProcess-based :class:`Process` runner so output streams to the GUI.

    When ``venv_path`` is given, package and run operations target that
    environment explicitly (``--python``) for determinism, rather than relying
    on an ambient ``VIRTUAL_ENV``.

    Every command it runs is recorded in the learner-visible
    :data:`~mu.command_log.command_log` (Phase 4b): the four ways of running
    uv below (``run_blocking``, ``run``, ``run_subprocess``, and
    ``script_command`` for the Run pane) each record theirs, so no caller can
    forget to.
    """

    def __init__(self, uv_executable=None, venv_path=None):
        self.executable = uv_executable or find_uv()
        self.venv_path = venv_path

    def __str__(self):
        return "<Uv %s (venv=%s)>" % (self.executable, self.venv_path)

    def _python_args(self):
        """`--python <venv>` selector, when this Uv targets a specific env."""
        return ["--python", str(self.venv_path)] if self.venv_path else []

    def _argv(self, command, args):
        """The arguments for uv (without the executable), as strings."""
        return [str(command), *(str(a) for a in args)]

    @staticmethod
    def _exit_code(process):
        """The exit code of a :class:`Process`'s QProcess; None if it never
        started or didn't exit normally (crashed or was killed)."""
        qprocess = getattr(process, "process", None)
        if qprocess is None:
            return None
        if qprocess.exitStatus() != QProcess.ExitStatus.NormalExit:
            return None
        return qprocess.exitCode()

    def run_blocking(
        self, command, *args, wait_for_s=180.0, note=None, keep_output=True, **envvars
    ):
        """Run a uv subcommand synchronously and return its combined output.

        In the command log, `note` is shown under the command, and its output
        is left out if `keep_output` is False (it's still logged on error).
        """
        argv = self._argv(command, args)
        record = command_log.start([self.executable, *argv], note=note)
        process = Process()
        try:
            output = process.run_blocking(
                self.executable,
                argv,
                wait_for_s=wait_for_s,
                **envvars,
            )
        except VirtualEnvironmentError as exc:
            record.finish(self._exit_code(process), exc.message)
            raise
        record.finish(self._exit_code(process), output if keep_output else None)
        return output

    def run_subprocess(self, command, *args):
        """
        Run a uv subcommand with :mod:`subprocess` (no Qt, so safe on a worker
        thread before the event loop runs — e.g. creating the environment at
        start-up). Return ``(succeeded, output)``.
        """
        argv = [self.executable, *self._argv(command, args)]
        record = command_log.start(argv)
        try:
            process = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except OSError as exc:
            record.finish(None, str(exc))
            return False, str(exc)
        output = process.stdout.decode(ENCODING, errors="replace")
        stderr_output = process.stderr.decode(ENCODING, errors="replace")
        if stderr_output:
            output += "\n" + stderr_output
        record.finish(process.returncode, output)
        return process.returncode == 0, output

    def script_command(self, script, cwd=None):
        """
        Record ``uv run --python <venv> --script <script>`` — how Nu runs a
        program with inline (PEP 723) dependencies — and return its
        :class:`~mu.command_log.CommandRecord`.

        Unlike the other methods this doesn't start the process: the Run pane
        does (it needs its own QProcess to talk to the program), launching
        ``record.argv`` and calling ``record.finish(exit_code)`` when it ends.
        """
        argv = [self.executable, "run", *self._python_args(), "--script", str(script)]
        return command_log.start(
            argv, cwd=cwd, note=_("Its output is in the Run pane.")
        )

    def run(self, command, *args, slots=Process.Slots(), **envvars):
        """Run a uv subcommand asynchronously, streaming via `slots`.

        Returns the live :class:`Process` so the caller can keep a reference;
        its ``command_record`` is the command's entry in the command log.
        """
        argv = self._argv(command, args)
        process = Process()
        record = command_log.start([self.executable, *argv])
        process.command_record = record
        # Connected before the caller's slots, so the record is complete by
        # the time their `finished` slot runs.
        process.output.connect(record.add_output)
        process.finished.connect(lambda: record.finish(self._exit_code(process)))
        if slots.started:
            process.started.connect(slots.started)
        if slots.output:
            process.output.connect(slots.output)
        if slots.finished:
            process.finished.connect(slots.finished)
        process.run(self.executable, argv, **envvars)
        return process

    def version(self):
        """Return the `uv` version string."""
        return self.run_blocking("--version").strip()

    def create_venv(self, path, python=None):
        """Create a virtual environment at `path` (optionally a specific
        Python version or interpreter via `python`)."""
        args = ["venv"]
        if python:
            args += ["--python", str(python)]
        args.append(str(path))
        return self.run_blocking(*args)

    def install(self, packages, slots=Process.Slots(), upgrade=False, **kwargs):
        """`uv pip install` the given package(s) into the target env."""
        packages = [packages] if isinstance(packages, str) else list(packages)
        args = ["pip", "install"]
        if upgrade:
            args.append("--upgrade")
        args += [*self._python_args(), *packages]
        return self.run(*args, slots=slots, **kwargs)

    def uninstall(self, packages, slots=Process.Slots(), **kwargs):
        """`uv pip uninstall` the given package(s) from the target env."""
        packages = [packages] if isinstance(packages, str) else list(packages)
        args = ["pip", "uninstall", *self._python_args(), *packages]
        return self.run(*args, slots=slots, **kwargs)

    def list_packages(self):
        """Return ``(name, version)`` tuples for packages in the target env."""
        output = self.run_blocking(
            "pip",
            "list",
            "--format=json",
            "--quiet",
            *self._python_args(),
            note=_("Nu reads this list to show your packages."),
            keep_output=False,
        )
        # Process merges stderr into the output, where uv reports e.g. the
        # environment it selected, so parse only the JSON line.
        json_lines = [line for line in output.splitlines() if line.startswith("[")]
        packages = json.loads(json_lines[0] if json_lines else output)
        return [(p["name"], p["version"]) for p in packages]


class SplashLogHandler(logging.NullHandler):
    """
    A simple log handler that does only one thing: use the referenced Qt signal
    to emit the log.
    """

    def __init__(self, emitter):
        """
        Returns an instance of the class that will use the Qt signal passed in
        as emitter.
        """
        super().__init__()
        self.setLevel(logging.DEBUG)
        self.emitter = emitter

    def emit(self, record):
        """
        Emits a record via the Qt signal.
        """
        messages = record.getMessage().splitlines()
        for msg in messages:
            output = "[{level}] - {message}".format(level=record.levelname, message=msg)
            self.emitter.emit(output)

    def handle(self, record):
        """
        Handles the log record.
        """
        self.emit(record)


class VirtualEnvironment(object):
    """
    Represents and contains methods for manipulating a virtual environment.
    """

    Slots = Process.Slots

    def __init__(self, dirpath=None, persist=True):
        """
        The environment at `dirpath`, or else the one venv.json names, or
        else a new default one. With `persist` False (an environment Nu is
        making or checking, not the one it uses) venv.json is neither read
        nor written.
        """
        self.process = Process()
        # Called with a line of text for the learner at each step of making
        # the environment (see `create_environment`), if set.
        self.progress = None
        # The uv process installing/removing user packages (see
        # install_user_packages), referenced so it isn't destroyed mid-run.
        self.user_package_process = None
        self._is_windows = sys.platform == "win32"
        self._bin_extension = ".exe" if self._is_windows else ""
        self.settings = settings.VirtualEnvironmentSettings()
        if persist:
            self.settings.init()
        dirpath_to_use = (
            dirpath or self.settings.get("dirpath") or self._generate_dirpath()
        )
        logger.info("Using dirpath: %s", dirpath_to_use)
        self.relocate(dirpath_to_use)

    def __str__(self):
        return "<%s at %s>" % (self.__class__.__name__, self.path)

    @staticmethod
    def _generate_dirpath():
        """
        Construct a unique virtual environment folder name

        To avoid clashing with previously-created virtual environments,
        construct one which includes the Python version and a timestamp
        """
        return "%s-%s-%s" % (
            config.VENV_DIR,
            "%s%s" % sys.version_info[:2],
            time.strftime("%Y%m%d-%H%M%S"),
        )

    def run_subprocess(self, *args, **kwargs):
        """Quick wrapper to run a subprocess and log the output

        Return True if the process succeeded, False otherwise
        """
        logger.info("Running %s with kwargs %s", args, kwargs)
        process = subprocess.run(
            list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
        )
        stdout_output = process.stdout.decode(ENCODING, errors="replace")
        stderr_output = process.stderr.decode(ENCODING, errors="replace")
        output = stdout_output
        if stderr_output:
            output += "\n\nSTDERR: " + stderr_output
        logger.debug(
            "Process returned {}; output: {}".format(
                process.returncode, compact(output)
            ),
        )
        return process.returncode == 0, output

    def reset_pip(self):
        """To avoid a problem where the same Pip process is executed by different
        threads, recreate the Pip process on demand
        """
        self.pip = Pip(self.pip_executable)

    def relocate(self, dirpath):
        """
        Relocate sets up variables for, eg, the expected location and name of
        the Python and Pip binaries, but doesn't access the file system. That's
        done by code in or called from `create`
        """
        logger.debug("Relocating to %s", dirpath)
        self.path = str(dirpath)
        self.name = os.path.basename(self.path)
        self._bin_directory = os.path.join(
            self.path, "scripts" if self._is_windows else "bin"
        )
        #
        # Pip and the interpreter will be set up when the virtualenv is created
        #
        self.interpreter = os.path.join(
            self._bin_directory, "python" + self._bin_extension
        )
        self.pip_executable = os.path.join(
            self._bin_directory, "pip" + self._bin_extension
        )
        self.reset_pip()
        logger.debug("Virtual environment set up %s at %s", self.name, self.path)
        self.settings["dirpath"] = self.path
        if not is_named_environment(self.path):
            # Remembered so the learner can come back to it after using a
            # named environment.
            self.settings["default_dirpath"] = self.path

    @property
    def display_name(self):
        """
        A short, stable name for the environment, for the learner: its
        folder name without the Python version and creation timestamp that
        `_generate_dirpath` adds (``mu_venv-311-20261108-030353`` →
        ``mu_venv``), so it doesn't change when Nu re-creates the env.
        """
        return environment_display_name(self.name)

    def python_version(self):
        """
        The environment's Python version (e.g. ``"3.11.15"``) as recorded in
        its ``pyvenv.cfg`` (``version_info`` from uv, ``version`` from the
        standard library's venv), or None if unknown. Reads a file rather
        than running the interpreter, so it's cheap enough for the UI.
        """
        return pyvenv_version(self.path)

    def describe(self):
        """
        The facts about this environment the learner sees (the admin dialog's
        Environment tab), as a GUI-free dict: its ``name``, folder (``path``),
        ``interpreter`` and ``python_version``; the commands to use it from a
        terminal — ``activate`` it, ``install`` a package into it, ``run`` a
        program with it (quoted for this OS; uv is shown as ``uv``, as the
        learner would type it); and the full path of Nu's ``uv`` (None if it
        can't be found).
        """
        try:
            uv_path = find_uv()
        except UvNotFound:
            uv_path = None
        # normpath: one kind of slash (a folder from settings or MU_DATA_DIR
        # may use / on Windows), as the learner would type it.
        path = os.path.normpath(self.path)
        interpreter = os.path.normpath(self.interpreter)
        activate = activate_command(path, self._is_windows)
        python = ["--python", interpreter]
        return {
            "name": self.display_name,
            "path": path,
            "interpreter": interpreter,
            "python_version": self.python_version(),
            "activate": activate,
            "install": quote_command(["uv", "pip", "install", *python, "cowsay"]),
            "run": quote_command(["uv", "run", *python, "hello.py"]),
            "uv": uv_path,
        }

    def activation_vars(self, base_path=None):
        """Environment-variable overrides that "activate" this venv for a
        spawned child process.

        Points ``VIRTUAL_ENV`` at this environment and prepends its
        ``bin``/``Scripts`` directory to ``PATH``, so the child — and anything
        it shells out to by name (``python``, ``pip``) or any library that keys
        off ``VIRTUAL_ENV`` — resolves against the user's environment rather
        than the system one. ``base_path`` defaults to the current process
        ``PATH``.

        Mu strips any *inherited* ``VIRTUAL_ENV`` at start-up (see ``app.run``,
        which kept a stray pointer to Mu's own env from breaking modes); this
        instead sets it explicitly, per child, to the user's env — the one
        whose interpreter actually runs their code.
        """
        if base_path is None:
            base_path = os.environ.get("PATH", "")
        path = self._bin_directory
        if base_path:
            path = self._bin_directory + os.pathsep + base_path
        return {"VIRTUAL_ENV": self.path, "PATH": path}

    def run_python(self, *args, slots=Process.Slots()):
        """
        Run the referenced Python interpreter with the passed in args

        If slots are supplied for the starting, output or finished signals
        they will be used; otherwise it will be assume that this running
        headless and the process will be run synchronously and output collected
        will be returned when the process is complete
        """
        if slots.output:
            if slots.started:
                self.process.started.connect(slots.started)
            self.process.output.connect(slots.output)
            if slots.finished:
                self.process.finished.connect(slots.finished)
            self.process.run(self.interpreter, args)
            return self.process
        else:
            output = self.process.run_blocking(self.interpreter, args)
            logger.debug("Python output: %s", output.strip())
            return output

    def _directory_is_venv(self):
        """
        Determine whether a directory appears to be an existing venv (see
        `directory_is_venv`).
        """
        return directory_is_venv(self.path, self.interpreter)

    def _report(self, text):
        """Tell the learner `text` while making an environment, if asked."""
        if self.progress:
            self.progress(text)

    def _replacement_dirpath(self):
        """
        Where to make a replacement for this environment once it's been moved
        out of the way (see `recreate` and `ensure_and_create`): a named
        environment is rebuilt in its own folder, so it keeps its name; the
        default one gets a new, timestamped folder.
        """
        if is_named_environment(self.path):
            return self.path
        return self._generate_dirpath()

    def default_dirpath(self):
        """
        The folder of the default environment (the one Nu makes by itself),
        even while a named one is in use; None if there's none yet.
        """
        path = self.settings.get("default_dirpath")
        if path:
            return path
        if not is_named_environment(self.path):
            return self.path
        # venv.json predates the key: the newest default-style folder.
        folders = [
            folder
            for folder in glob.glob(glob.escape(config.VENV_DIR) + "-*")
            if os.path.isdir(folder) and "." not in os.path.basename(folder)
        ]
        return max(folders) if folders else None

    def named_environment_paths(self):
        """
        The folders of the learner's named environments: every folder in
        ``config.ENVS_DIR`` with a valid name that looks like a Python
        environment (so one made there by hand with ``uv venv`` counts, and
        a moved-aside ``name.FAILED`` doesn't), by name.
        """
        try:
            entries = os.listdir(config.ENVS_DIR)
        except OSError:
            return []
        paths = []
        for entry in sorted(entries, key=str.casefold):
            path = os.path.join(config.ENVS_DIR, entry)
            if (
                ENVIRONMENT_NAME_RE.match(entry)
                and os.path.isdir(path)
                and directory_is_venv(path, environment_interpreter(path))
            ):
                paths.append(path)
        return paths

    def list_environments(self):
        """
        Every environment the learner can choose between, as GUI-free dicts:
        the default one first, then the named ones. Each has its ``name``,
        ``path``, ``python_version`` (from ``pyvenv.cfg``), whether it's the
        ``default``, whether it's ``in_use`` (this session's) and whether
        it's the one for the ``next_start`` (venv.json's ``dirpath``).
        """
        next_start = self.settings.get("dirpath") or self.path
        candidates = [(path, False) for path in self.named_environment_paths()]
        default = self.default_dirpath()
        if default:
            candidates.insert(0, (default, True))
        environments = []
        for path, is_default in candidates:
            environments.append(
                {
                    "name": environment_display_name(os.path.basename(path)),
                    "path": path,
                    "python_version": pyvenv_version(path),
                    "default": is_default,
                    "in_use": same_path(path, self.path),
                    "next_start": same_path(path, next_start),
                }
            )
        return environments

    def environment_name_problem(self, name):
        """
        What's wrong with `name` for a new named environment, in plain words,
        or None if it's fine: a plain folder name (letters, digits, ``-`` and
        ``_``) that isn't empty, too long or a Windows device name, and isn't
        taken, ignoring case (on every system, so the environments still work
        when copied to one that ignores case).
        """
        if not name:
            return _("Please give the environment a name.")
        if not ENVIRONMENT_NAME_RE.match(name):
            return _(
                "Please use only letters, digits, - and _ in the name, e.g. project-a."
            )
        if len(name) > ENVIRONMENT_NAME_MAX_LENGTH:
            return _("Please use a shorter name ({} characters at most).").format(
                ENVIRONMENT_NAME_MAX_LENGTH
            )
        if name.casefold() in WINDOWS_RESERVED_NAMES:
            return _("“{}” can't be a folder's name on Windows.").format(name)
        taken = {env["name"].casefold() for env in self.list_environments()}
        try:
            taken |= {entry.casefold() for entry in os.listdir(config.ENVS_DIR)}
        except OSError:
            pass
        if name.casefold() in taken:
            return _("There's already an environment called “{}”.").format(name)
        return None

    def create_environment(self, name, progress=None):
        """
        Make a new named environment, `name`, in ``config.ENVS_DIR`` the same
        way Nu makes the default one (see `create`): the same Python, pip,
        the baseline packages (Nu's and the plugins') and the REPL's kernel,
        then check it as Nu does at start. `progress` is called with a line
        for the learner at each step (first the ``uv venv`` command). Doesn't
        switch to it. Return its folder.

        Raise VirtualEnvironmentCreateError, with a plain message, if the
        name won't do or making it fails; then the half-made folder is
        removed (it has nothing of the learner's in it yet).
        """
        problem = self.environment_name_problem(name)
        if problem:
            raise VirtualEnvironmentCreateError(problem)
        path = os.path.join(config.ENVS_DIR, name)
        logger.info("Creating the environment %s at %s", name, path)
        try:
            os.makedirs(config.ENVS_DIR, exist_ok=True)
            environment = VirtualEnvironment(path, persist=False)
            environment.progress = progress
            environment.create()
            environment.ensure()
        except Exception as exc:
            logger.exception("Unable to create the environment at %s", path)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                logger.info("Removed the half-made environment at %s", path)
            reason = getattr(exc, "message", None) or str(exc)
            raise VirtualEnvironmentCreateError(
                _("Nu couldn't make the environment “{name}”.\n{reason}").format(
                    name=name, reason=reason
                )
            ) from exc
        logger.info("Created the environment %s at %s", name, path)
        return path

    def check_environment(self, path):
        """
        Whether Nu can use the environment at `path`, by the checks it makes
        at start (see `ensure`: its Python, the same version as Nu's, pip and
        the packages Nu needs): None if so, otherwise why not, in plain words.
        """
        if not os.path.isdir(path) or not directory_is_venv(path):
            return _("“{}” isn't a Python environment.").format(path)
        try:
            VirtualEnvironment(path, persist=False).ensure()
        except VirtualEnvironmentError as exc:
            return _("Nu can't use it: {}").format(exc.message)
        return None

    def switch_environment(self, path):
        """
        Use the environment at `path` from the next start (as with plugins,
        the running Nu keeps the one it has): check it (see
        `check_environment`) and save it as venv.json's ``dirpath``. Return
        None if that worked, otherwise why not, in plain words.
        """
        problem = self.check_environment(path)
        if problem:
            logger.warning("Not switching to %s: %s", path, problem)
            return problem
        logger.info("Using the environment at %s from the next start", path)
        self.settings["dirpath"] = path
        self.settings.save()
        return None

    def environment_delete_problem(self, path):
        """
        Why the environment at `path` can't be deleted, in plain words, or
        None if it can: only a named environment (in ``config.ENVS_DIR``)
        that Nu isn't using and won't use from the next start. The default
        one stays: it's where Nu goes back to, and Nu would make it again.
        """
        if not is_named_environment(path):
            return _("The default environment can't be deleted.")
        if same_path(path, self.path):
            return _(
                "Nu is using this environment. Use another one, restart Nu, "
                "then delete it."
            )
        if same_path(path, self.settings.get("dirpath") or self.path):
            return _(
                "Nu will use this environment from the next start. Choose "
                "another one first."
            )
        if not os.path.isdir(path):
            return _("“{}” isn't there any more.").format(path)
        return None

    def delete_environment(self, path):
        """
        Delete the named environment at `path`: its folder, with every
        package in it, and the REPL kernelspec an older Nu put in the
        learner's own Jupyter folder for it (only if that kernelspec runs
        this environment's Python). Return None if that worked, otherwise
        why not, in plain words (see `environment_delete_problem`); a folder
        that can't be removed completely (a file in use on Windows) is
        reported, with what's left where it was.
        """
        problem = self.environment_delete_problem(path)
        if problem:
            logger.warning("Not deleting the environment %s: %s", path, problem)
            return problem
        logger.info("Deleting the environment at %s", path)
        failures = []

        def failed(function, failed_path, error):
            failures.append(failed_path)

        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=failed)
        else:  # pragma: no cover (Python 3.11)
            shutil.rmtree(path, onerror=failed)
        if failures or os.path.exists(path):
            logger.error(
                "Couldn't delete all of %s: %s", path, ", ".join(map(str, failures))
            )
            return _(
                "Nu couldn't delete all of “{}”: a program may be using it. "
                "Close it, or restart your computer, and try again."
            ).format(path)
        self._remove_user_kernelspec(path)
        logger.info("Deleted the environment at %s", path)
        return None

    @staticmethod
    def _remove_user_kernelspec(path):
        """
        Remove the kernelspec ``ipykernel install --user`` made for the
        environment at `path` before Nu kept it inside the environment, if
        it's there and runs a Python from that environment.
        """
        try:
            from jupyter_core.paths import jupyter_data_dir

            spec_dir = os.path.join(
                jupyter_data_dir(),
                "kernels",
                os.path.basename(path).replace(" ", "-").lower(),
            )
            with open(os.path.join(spec_dir, "kernel.json"), encoding="utf-8") as f:
                interpreter = json.load(f)["argv"][0]
        except Exception:
            return
        environment = os.path.normcase(os.path.abspath(path))
        if os.path.normcase(os.path.abspath(interpreter)).startswith(
            environment + os.sep
        ):
            shutil.rmtree(spec_dir, ignore_errors=True)
            logger.info("Removed the kernelspec %s", spec_dir)

    def quarantine_venv(self, reason="FAILED"):
        """Rename an existing virtual environment folder out of the way to make
        it clearer which is the current one.

        NB if this fails (eg because of file locking) it won't matter: the folder
        will not be used and will simply be a little distracting
        """
        error_dirpath = self.path + "." + reason
        if os.path.exists(error_dirpath):
            # Moved aside before (a named environment keeps its folder).
            error_dirpath += time.strftime("-%Y%m%d-%H%M%S")
        try:
            os.rename(self.path, error_dirpath)
        except OSError:
            logger.exception("Unable to quarantine %s as %s", self.path, error_dirpath)
        else:
            logger.info("Quarantined %s as %s", self.path, error_dirpath)

    def recreate(self):
        """Recreate this virtual environment with updated baseline packages and the
        same user packages

        The intended use is when the Mu version changes as this can bring with it
        additional and/or updated packages. The simplest thing to do is to switch
        to a new venv and then pull in the packages the user had additionally installed
        """
        #
        # Keep track of the user packages installed into the current venv
        #
        _, user_packages = self.installed_packages()

        #
        # Now, quarantine the current venv with
        # a marker to say it's been superseded
        #
        self.quarantine_venv(reason="SUPERSEDED")

        #
        # Create a new venv which will then become the current one.
        # Install the (possibly updated) baseline packages
        #
        self.relocate(self._replacement_dirpath())
        self.create()

        #
        # Now reinstall the original user packages
        #
        if user_packages:
            logger.debug("About to reinstall user packages: %s", user_packages)
            self.install_user_packages(user_packages)

    def ensure_and_create(self, emitter=None):
        """Check whether we have a valid virtual environment in place and, if not,
        create a new one. Allow a couple of tries in case we have temporary glitches
        around the network, file contention etc.
        """
        splash_handler = None
        if emitter:
            splash_handler = SplashLogHandler(emitter)
            splash_handler.setLevel(logging.INFO)
            logger.addHandler(splash_handler)
            logger.info("Added log handler.")

        n_tries = 2
        n = 1
        #
        # First time around we'll have a path with nothing in it
        # Jump straight to creation and let the ensure take over afterwards
        # For the happy path we'll get a clean creation and a clean ensure
        #
        try_to_create = not os.path.exists(self.path)
        while True:
            logger.debug("Checking virtual environment; attempt #%d.", n)
            try:
                #
                # try_to_create will be True if this is a brand new install
                # or if we've failed to ensure at least once
                #
                if try_to_create:
                    self.create()
                    try_to_create = False

                #
                # Otherwise check whether the venv settings match the version of Mu
                # If not, recreate the venv with updated baseline packages and
                # the existing user packages
                #
                else:
                    venv_mu_version = self.made_by_version()
                    if venv_mu_version != mu_version:
                        logger.warning(
                            "Venv created by Mu version %s; Current Mu is version %s",
                            venv_mu_version,
                            mu_version,
                        )
                        self.recreate()

                #
                # In any situation (initial creation, recreation after Mu update,
                # regular run) ensure that the venv is still valid
                #
                self.ensure()
                logger.info("Valid virtual environment found at %s", self.path)

                #
                # If we reach this point, ensure hasn't raised an exception and
                # we're good to save settings and move on
                #
                self.settings.save()
                self.remove_old_bundled_pythons()
                break

            except VirtualEnvironmentError as exc:
                #
                # If any of the ensure/create steps cause a VirtualEnvironmentError
                # retry up to a maximum number in case we've just been unlucky
                # with network, file contention etc.
                #
                logger.error(exc.message)
                self.quarantine_venv()
                if n < n_tries:
                    self.relocate(self._replacement_dirpath())
                    try_to_create = True
                    if isinstance(exc, VirtualEnvironmentTimeoutError):
                        self.pip.timeout = exc.timeout * 2
                    n += 1
                else:
                    raise
            finally:
                if emitter and splash_handler:
                    logger.removeHandler(splash_handler)

    def ensure(self):
        """
        Ensure that virtual environment exists and is in a good state.

        If any of these fails, they should raise a (subclass of)
        VirtualEnvironmentError which will bubble up to `ensure_and_create` and be
        caught and acted on appropriately
        """
        self.ensure_path()
        self.ensure_interpreter()
        self.ensure_interpreter_version()
        self.ensure_pip()
        self.ensure_key_modules()

    def ensure_path(self):
        """
        Ensure that the virtual environment path exists and is a valid venv.
        """
        if not os.path.exists(self.path):
            raise VirtualEnvironmentEnsureError("%s does not exist." % self.path)
        elif not os.path.isdir(self.path):
            raise VirtualEnvironmentEnsureError(
                "%s exists but is not a directory." % self.path
            )
        elif not self._directory_is_venv():
            raise VirtualEnvironmentEnsureError(
                "Directory %s exists but is not a venv." % self.path
            )
        logger.info("Virtual Environment found at: %s", self.path)

    def ensure_interpreter(self):
        """
        Ensure there is an interpreter of the expected name at the expected
        location, given the platform and naming conventions.

        NB if the interpreter is present as a symlink to a system interpreter
        (likely for a venv) but the link is broken, then os.path.isfile will
        fail as though the file wasn't there. Which is what we want in these
        circumstances.
        """
        if os.path.isfile(self.interpreter):
            logger.info("Interpreter found at: %s", self.interpreter)
        elif os.environ.get("APPDIR") and os.environ.get("APPIMAGE"):
            # When packaged as a Linux AppImage, Mu Editor is mounted
            # on a random(ish) path each time it runs. This breaks the
            # existing venv: its interpreter symlinks to a path that
            # likely no longer exists. Fix that by re-symlinking to
            # the current and now valid interpreter path.
            # PS: This is a horrible hack and it seems to work! :)
            logger.info("No interpreter found at: %s", self.interpreter)
            try:
                os.unlink(self.interpreter)
            except OSError as exc:
                logger.warning(
                    "Unlinking %s failed: %s. Moving on.",
                    self.interpreter,
                    exc,
                )
            os.symlink(sys.executable, self.interpreter)
            logger.info(
                "Symlinked %s to AppImage's %s",
                self.interpreter,
                sys.executable,
            )
        else:
            raise VirtualEnvironmentEnsureError(
                "Interpreter not found where expected at: %s" % self.interpreter
            )

    def ensure_interpreter_version(self):
        """
        Ensure that the venv interpreter matches the version of Python running
        Mu.

        This is necessary because otherwise we'll have mismatched wheels etc.
        """
        current_version = "%s%s" % sys.version_info[:2]
        #
        # Can't use self.run_python as we're not yet within the Qt UI loop
        #
        ok, output = self.run_subprocess(
            self.interpreter,
            "-c",
            'import sys; print("%s%s" % sys.version_info[:2])',
            shell=True if self._is_windows else False,
        )
        if not ok:
            raise VirtualEnvironmentEnsureError(
                "Failed to run venv interpreter %s\n%s"
                % (self.interpreter, compact(output))
            )

        venv_version = output.strip()
        if current_version == venv_version:
            logger.info("Both interpreters at version %s", current_version)
        else:
            raise VirtualEnvironmentEnsureError(
                "Mu interpreter at version %s; venv interpreter at version %s."
                % (current_version, venv_version)
            )

    def ensure_key_modules(self):
        """
        Ensure that the venv interpreter is able to load key modules.
        """
        for module, *_ in wheels.mode_packages:
            logger.debug("Verifying import of: %s", module)
            ok, output = self.run_subprocess(
                self.interpreter,
                "-c",
                "import %s" % module,
                shell=True if self._is_windows else False,
            )
            if not ok:
                raise VirtualEnvironmentEnsureError(
                    "Failed to import: %s\n%s" % (module, compact(output))
                )

    def ensure_pip(self):
        """
        Ensure that pip is available.
        """
        if os.path.isfile(self.pip_executable):
            logger.info("Pip found at: %s", self.pip_executable)
        else:
            raise VirtualEnvironmentEnsureError(
                "Pip not found where expected at: %s" % self.pip_executable
            )

    def create(self):
        """Create a new virtualenv and install baseline packages & kernel

        If a failure occurs, attempt to move the failed attempt out of the way
        before re-raising the error.
        """
        self.create_venv()
        self._report(_("Adding Nu's packages…"))
        self.install_baseline_packages()
        self.register_baseline_packages()
        self._report(_("Setting up the REPL for it…"))
        self.install_jupyter_kernel()
        self.settings["mu_version"] = mu_version
        self.write_record()

    def write_record(self):
        """
        Write what Nu knows about this environment into it
        (`ENVIRONMENT_RECORD`): the Nu version that made it and its baseline
        packages. venv.json holds these too, but only for one environment;
        the record keeps them right for every named one, so one made by an
        older Nu is rebuilt when Nu next starts with it.
        """
        record = {
            "nu_version": mu_version,
            "baseline_packages": self.settings.get("baseline_packages") or [],
        }
        try:
            with open(
                os.path.join(self.path, ENVIRONMENT_RECORD), "w", encoding="utf-8"
            ) as f:
                json.dump(record, f, indent=2)
        except OSError:
            logger.exception("Unable to write the environment's record")

    def record(self):
        """
        What `write_record` wrote into this environment, or {} if nothing
        (an environment made by an older Nu, or by hand).
        """
        try:
            with open(
                os.path.join(self.path, ENVIRONMENT_RECORD), encoding="utf-8"
            ) as f:
                record = json.load(f)
        except (OSError, ValueError):
            return {}
        return record if isinstance(record, dict) else {}

    def made_by_version(self):
        """
        The version of Nu that made this environment: from its record, else
        (made before Nu kept one) venv.json's, which was the version that
        made whichever environment Nu was using.
        """
        return self.record().get("nu_version") or self.settings.get(
            "mu_version", "-no-version-"
        )

    def ensure_bundled_python(self):
        """
        Return the interpreter of the CPython bundled with the installer,
        extracting it into Mu's data directory on first use; None if this
        isn't an installer build (no archive) or extraction fails.

        The archive (a python-build-standalone "install_only" build, see
        ``wheels.download_python``) is extracted to a stable, writable
        location rather than used in place: the app bundle may be read-only,
        and a Linux AppImage is mounted at a different path on every launch,
        which would break a venv based on it.
        """
        archive = wheels.bundled_python_archive()
        if not archive:
            return None
        name = os.path.basename(archive)[: -len(".tar.gz")]
        target = os.path.join(config.DATA_DIR, "python", name)
        if self._is_windows:
            interpreter = os.path.join(target, "python", "python.exe")
        else:
            interpreter = os.path.join(target, "python", "bin", "python3")
        if os.path.isfile(interpreter):
            return interpreter

        logger.info("Extracting bundled Python %s to %s", name, target)
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            # Extract next to the target, then rename into place, so an
            # interrupted extraction never looks like a usable interpreter.
            partial = target + ".partial"
            if os.path.isdir(partial):
                shutil.rmtree(partial)
            os.makedirs(partial)
            with tarfile.open(archive) as tar:
                try:
                    tar.extractall(partial, filter="data")
                except TypeError:  # Python < 3.11.4 has no extraction filters
                    tar.extractall(partial)
            os.rename(partial, target)
        except (OSError, tarfile.TarError) as exc:
            logger.warning("Unable to extract bundled Python: %s", exc)
            return None
        if not os.path.isfile(interpreter):
            logger.warning("No interpreter at %s after extraction", interpreter)
            return None
        return interpreter

    def remove_old_bundled_pythons(self):
        """
        Delete the CPython builds an earlier Nu extracted (see
        :meth:`ensure_bundled_python`) and nothing uses any more: about 70 MB
        each, left in ``DATA_DIR/python/`` by every upgrade that bundles a
        newer build. Only in an installer build (one with a bundled archive);
        the current build is kept, and so is any build the current
        environment's ``pyvenv.cfg`` points into (it's based on that Python,
        e.g. if recreating it after the upgrade failed). Returns the folders
        removed.
        """
        archive = wheels.bundled_python_archive()
        root = os.path.join(config.DATA_DIR, "python")
        if not archive or not os.path.isdir(root):
            return []
        current = os.path.basename(archive)[: -len(".tar.gz")]
        in_use = self._pyvenv_paths()
        # Named environments made by Nu are based on a bundled Python too.
        for path in self.named_environment_paths():
            in_use += self._pyvenv_paths(path)
        removed = []
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if name in (current, current + ".partial") or not os.path.isdir(path):
                continue
            if any(is_within(used, path) for used in in_use):
                logger.info("Keeping %s: the environment %s uses it", path, self.path)
                continue
            logger.info("Removing a bundled Python no longer used: %s", path)
            try:
                shutil.rmtree(path)
            except OSError as exc:
                logger.warning("Unable to remove %s: %s", path, exc)
                continue
            removed.append(path)
        return removed

    def _pyvenv_paths(self, path=None):
        """
        The values in the ``pyvenv.cfg`` of the environment (this one, or the
        one at `path`): ``home``, and any other paths a tool wrote there; an
        empty list if it can't be read.
        """
        path = path or self.path
        try:
            with open(os.path.join(path, "pyvenv.cfg"), encoding="utf-8") as cfg:
                lines = cfg.read().splitlines()
        except OSError:
            return []
        values = (line.partition("=")[2].strip() for line in lines)
        return [value for value in values if value]

    def create_venv(self):
        """
        Create a new virtual environment using `uv`.

        ``uv venv --seed`` produces the same ``bin/python`` + ``bin/pip`` +
        ``pyvenv.cfg`` layout the rest of this module expects (so the pip-based
        baseline-wheel install downstream is unchanged).

        In an installer build the base interpreter is the CPython bundled with
        the app (see :meth:`ensure_bundled_python`), and pip is seeded from the
        bundled wheel with ``--no-index``, so the first launch needs no
        network. The app's own ``sys.executable`` can't be the base: in a
        packaged (Briefcase) app it's the launcher *stub*, not a real Python,
        so ``uv`` can't introspect it.

        Without a bundled CPython (a dev checkout) the base is pinned by
        **version** (e.g. ``3.12``) and uv resolves a genuine interpreter for
        it: a system install, a uv-managed CPython, or a download. Either way
        the version is the running app's Python, which is what the baseline
        wheels were built for.

        Run synchronously via ``Uv.run_subprocess`` (plain subprocess, not
        QProcess) because creation happens on the startup worker thread,
        before the Qt event loop is available. Like every uv command, it's
        recorded in the learner-visible command log.
        """
        logger.info("Creating virtualenv: {}".format(self.path))
        logger.info("Virtualenv name: {}".format(self.name))

        uv_executable = find_uv()
        python = self.ensure_bundled_python()
        seed_args = ["--seed"]
        if python:
            pip_wheels = glob.glob(os.path.join(wheels.PYTHON_DIRPATH, "pip-*.whl"))
            if pip_wheels:
                seed_args += ["--no-index", "--find-links", wheels.PYTHON_DIRPATH]
        else:
            python = "%d.%d" % sys.version_info[:2]
        command = ["uv", "venv", "--python", python, *seed_args, self.path]
        self._report("$ " + quote_command(command))
        ok, output = Uv(uv_executable).run_subprocess(
            "venv",
            "--python",
            python,
            *seed_args,
            self.path,
        )
        if output.strip():
            self._report(output.strip())
        if ok:
            logger.info(
                "Created virtual environment for Python %s at %s",
                python,
                self.path,
            )
        else:
            raise VirtualEnvironmentCreateError(
                "Unable to create a virtual environment using %s at %s\n%s"
                % (uv_executable, self.path, compact(output))
            )

    def install_jupyter_kernel(self):
        """
        Install a Jupyter kernel for Mu (the name of the kernel indicates this
        is a Mu-related kernel).

        Run via the *venv* interpreter, not Mu's own (`sys.executable`):
        ``ipykernel`` is a baseline package installed into the venv just above
        (see :meth:`create`), so it sits in the venv's own ``site-packages`` and
        is importable even under ``-I``. Mu's own interpreter can't be used in a
        packaged build — Briefcase installs the app's dependencies into a
        separate ``app_packages`` dir that is *not* on a fresh subprocess's path,
        so ``sys.executable -I -m ipykernel`` would fail to import ipykernel and
        take the whole startup down with it. The kernel's interpreter is forced
        to ``venv.interpreter`` at REPL start time anyway (see
        ``MuKernelManager`` in ``mu/modes/python3.py``), so pointing the spec at
        the venv python is also the more consistent choice.
        """
        kernel_name = self.name.replace(" ", "-")
        display_name = '"Python/Nu ({})"'.format(kernel_name)
        logger.info("Installing Jupyter Kernel: %s", kernel_name)
        ok, output = self.run_subprocess(
            self.interpreter,
            "-I",
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            kernel_name,
            "--display-name",
            display_name,
        )
        if ok:
            logger.info("Installed Jupyter Kernel: %s", kernel_name)
        else:
            raise VirtualEnvironmentCreateError(
                "Unable to install kernel\n%s" % compact(output)
            )

    def install_from_zipped_wheels(self, zipped_wheels_filepath):
        """Take a zip containing wheels, unzip it and install the wheels into
        the current virtualenv
        """
        with tempfile.TemporaryDirectory() as unpacked_wheels_dirpath:
            #
            # The wheel files are shipped in Mu-version-specific zip files to avoid
            # cross-contamination when a Mu version change happens and we still have
            # wheels from the previous installation.
            #
            with zipfile.ZipFile(zipped_wheels_filepath) as zip:
                zip.extractall(unpacked_wheels_dirpath)

            wheel_paths = sorted(
                glob.glob(os.path.join(unpacked_wheels_dirpath, "*.whl"))
            )
            if not wheel_paths:
                return
            # All in one go: uv resolves and installs them in a few seconds,
            # where installing them one by one with pip took minutes on the
            # learner's first start. Offline (--no-index): the installer
            # ships every wheel needed.
            names = [os.path.basename(wheel) for wheel in wheel_paths]
            logger.info("About to install from wheels: {}".format(", ".join(names)))
            self._report(
                _("Installing {} packages Nu needs (no internet needed)").format(
                    len(names)
                )
            )
            ok, output = Uv(find_uv()).run_subprocess(
                "pip",
                "install",
                "--python",
                self.interpreter,
                "--no-index",
                "--no-deps",
                *wheel_paths,
            )
            if not ok:
                raise VirtualEnvironmentCreateError(
                    "Unable to install the bundled packages:\n%s" % compact(output)
                )

    def install_baseline_packages(self):
        """
        Install all packages needed for non-core activity.

        The core needs a few packages (the REPL's kernel), and plugins
        declare what their modes need (see `wheels.baseline_packages`). The
        installers ship with all the necessary wheels for those packages so
        no network access is needed. But if the wheels aren't found, because
        we're not running from an installer, then just pip install in the
        usual way.
        """
        logger.info("Installing baseline packages.")
        logger.info("pip version: %s", compact(self.pip.version()))
        zipped_wheels_filepath = os.path.join(wheels_dirpath, "%s.zip" % mu_version)
        logger.info("Expecting zipped wheels at %s", zipped_wheels_filepath)
        if not os.path.exists(zipped_wheels_filepath):
            logger.warning("No zipped wheels found; downloading...")
            wheels.download(zipped_wheels_filepath, logger)

        self.install_from_zipped_wheels(zipped_wheels_filepath)

    def register_baseline_packages(self):
        """
        Keep track of the baseline packages installed into the empty venv.
        """
        self.reset_pip()
        packages = list(self.pip.installed())
        self.settings["baseline_packages"] = packages

    def baseline_packages(self):
        """
        Return the list of baseline packages: this environment's own (from
        its record), else venv.json's.
        """
        recorded = self.record().get("baseline_packages")
        if recorded:
            return recorded
        return self.settings.get("baseline_packages")

    def _uv(self):
        """Return a `Uv` proxy targeting this environment's interpreter.

        Built on demand (like `reset_pip`) so locating the `uv` binary is
        deferred to actual use and always reflects the current interpreter.
        """
        return Uv(venv_path=self.interpreter)

    def script_command(self, script, cwd):
        """
        Record, and return the :class:`~mu.command_log.CommandRecord` of, the
        ``uv run --python <this env> --script <script>`` command the Run
        button uses for a program with inline (PEP 723) dependencies; the Run
        pane launches it. Raise :class:`UvNotFound` if there's no uv.
        """
        return self._uv().script_command(script, cwd=cwd)

    def install_user_packages(self, packages, slots=Process.Slots()):
        """
        Install user defined packages. Return the command's
        :class:`~mu.command_log.CommandRecord` (so the UI can show it).
        """
        logger.info("Installing user packages: %s", ", ".join(packages))
        # Keep the process alive: Qt destroys (and kills) a QProcess as soon
        # as nothing references it.
        self.user_package_process = self._uv().install(
            packages, slots=slots, upgrade=True
        )
        return self.user_package_process.command_record

    def remove_user_packages(self, packages, slots=Process.Slots()):
        """
        Remove user defined packages. Return the command's
        :class:`~mu.command_log.CommandRecord` (so the UI can show it).
        """
        logger.info("Removing user packages: %s", ", ".join(packages))
        self.user_package_process = self._uv().uninstall(packages, slots=slots)
        return self.user_package_process.command_record

    def installed_packages(self):
        """
        List all the third party modules installed by the user in the venv
        containing the referenced Python interpreter.
        """
        logger.info("Discovering installed third party modules in venv.")
        baseline_packages = [name for name, version in self.baseline_packages()]
        # The baseline names come from `pip list` (e.g. "jupyter_client") but
        # uv reports normalised ones ("jupyter-client"), so compare those.
        baseline_names = {canonical_package_name(n) for n in baseline_packages}
        user_packages = []
        for package, version in self._uv().list_packages():
            if canonical_package_name(package) not in baseline_names:
                user_packages.append(package)
        logger.info(user_packages)

        return baseline_packages, user_packages


#
# Create a singleton virtual environment to be used throughout
# the application
#
venv = VirtualEnvironment()
