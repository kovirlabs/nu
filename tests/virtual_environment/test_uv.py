# -*- coding: utf-8 -*-
"""
Tests for the uv-based environment management (Phase 4).

These cover the `find_uv` locator and the `Uv` command-builder. Command
composition is asserted by mocking the QProcess-based `Process` runner, in the
same style as test_pip.py — no real `uv` binary is required.
"""

import os
import random
from unittest import mock

import pytest

import mu.virtual_environment
from mu.command_log import CommandLog

VE = mu.virtual_environment
Uv = VE.Uv


def rstring(length=10, characters="abcdefghijklmnopqrstuvwxyz"):
    letters = list(characters)
    random.shuffle(letters)
    return "".join(letters[:length])


#
# find_uv
#
def test_find_uv_from_env_var(tmp_path):
    """MU_UV pointing at an existing file wins."""
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("")
    with mock.patch.dict(os.environ, {VE.UV_ENV_VAR: str(fake_uv)}):
        assert VE.find_uv() == str(fake_uv)


def test_find_uv_env_var_missing_file(tmp_path):
    """MU_UV pointing at a non-existent file raises UvNotFound."""
    missing = str(tmp_path / "nope")
    with mock.patch.dict(os.environ, {VE.UV_ENV_VAR: missing}):
        with pytest.raises(VE.UvNotFound):
            VE.find_uv()


def test_find_uv_falls_back_to_path():
    """With MU_UV unset, fall back to `uv` on the PATH."""
    found = "/usr/local/bin/uv"
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(VE.shutil, "which", return_value=found) as which:
            assert VE.find_uv() == found
    which.assert_called_once_with("uv")


def test_find_uv_falls_back_to_bundled_package():
    """With MU_UV unset and nothing on PATH, use the binary bundled by the
    `uv` PyPI package (the packaged-app path)."""
    bundled = "/opt/mu/app_packages/uv/bin/uv"
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(VE.shutil, "which", return_value=None):
            with mock.patch.object(VE, "_uv_from_package", return_value=bundled):
                assert VE.find_uv() == bundled


def test_find_uv_not_found():
    """No MU_UV, nothing on PATH, and no bundled uv raises UvNotFound."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(VE.shutil, "which", return_value=None):
            with mock.patch.object(VE, "_uv_from_package", return_value=None):
                with pytest.raises(VE.UvNotFound):
                    VE.find_uv()


#
# _uv_from_package
#
def test_uv_from_package_returns_existing_binary(tmp_path):
    """When the `uv` package is importable and its binary exists, return it."""
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("")
    fake_module = mock.Mock()
    fake_module.find_uv_bin.return_value = str(fake_uv)
    with mock.patch.dict("sys.modules", {"uv": fake_module}):
        assert VE._uv_from_package() == str(fake_uv)


def test_uv_from_package_missing_binary(tmp_path):
    """A reported binary that doesn't exist on disk yields None."""
    fake_module = mock.Mock()
    fake_module.find_uv_bin.return_value = str(tmp_path / "nope")
    with mock.patch.dict("sys.modules", {"uv": fake_module}):
        assert VE._uv_from_package() is None


def test_uv_from_package_not_importable():
    """When the `uv` package can't be imported, return None (dev checkout)."""
    with mock.patch.dict("sys.modules", {"uv": None}):
        assert VE._uv_from_package() is None


def test_uv_from_package_without_find_uv_bin():
    """A `uv` module lacking find_uv_bin (AttributeError) yields None."""
    fake_module = mock.Mock(spec=[])  # no attributes -> find_uv_bin raises
    with mock.patch.dict("sys.modules", {"uv": fake_module}):
        assert VE._uv_from_package() is None


#
# Uv construction
#
def test_uv_uses_explicit_executable():
    """An explicit executable is retained and find_uv is not consulted."""
    executable = "uv-" + rstring()
    with mock.patch.object(VE, "find_uv") as find_uv:
        uv = Uv(uv_executable=executable)
    assert uv.executable == executable
    find_uv.assert_not_called()


def test_uv_locates_executable_when_unset():
    """With no executable given, Uv locates one via find_uv."""
    located = "uv-" + rstring()
    with mock.patch.object(VE, "find_uv", return_value=located):
        uv = Uv()
    assert uv.executable == located


#
# Command composition (blocking)
#
def test_uv_run_blocking_builds_command():
    """run_blocking forwards command + stringified args to Process."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run_blocking") as run_blocking:
        uv.run_blocking("venv", "/tmp/x", 3)
    run_blocking.assert_called_once()
    args, kwargs = run_blocking.call_args
    assert args[0] == "uv"
    assert args[1] == ["venv", "/tmp/x", "3"]


def test_uv_version():
    """version() runs `uv --version` and strips the result."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run_blocking", return_value="uv 0.9.0\n"):
        assert uv.version() == "uv 0.9.0"


def test_uv_create_venv_with_python():
    """create_venv passes --python and the target path."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run_blocking") as run_blocking:
        uv.create_venv("/tmp/env", python="3.14")
    args, _ = run_blocking.call_args
    assert args[1] == ["venv", "--python", "3.14", "/tmp/env"]


def test_uv_list_packages_parses_json():
    """list_packages parses uv's --format=json output into tuples."""
    uv = Uv(uv_executable="uv", venv_path="/tmp/env")
    payload = (
        '[{"name": "pgzero", "version": "1.2.1"}, '
        '{"name": "pygame", "version": "2.1.0"}]'
    )
    with mock.patch.object(VE.Process, "run_blocking", return_value=payload):
        assert uv.list_packages() == [
            ("pgzero", "1.2.1"),
            ("pygame", "2.1.0"),
        ]


def test_uv_list_packages_targets_venv():
    """When venv_path is set, pip operations select it via --python."""
    uv = Uv(uv_executable="uv", venv_path="/tmp/env")
    with mock.patch.object(VE.Process, "run_blocking", return_value="[]"):
        uv.list_packages()
        args, _ = VE.Process.run_blocking.call_args
    assert args[1] == [
        "pip",
        "list",
        "--format=json",
        "--quiet",
        "--python",
        "/tmp/env",
    ]


def test_uv_list_packages_ignores_uv_status_lines():
    """
    Regression: uv reports the environment it selected ("Using Python 3.11.15
    environment at: ...") on stderr, and Process merges stderr into the output.
    That line must not break the JSON parse -- it used to raise
    JSONDecodeError, which crashed Nu when opening the admin dialog.
    """
    uv = Uv(uv_executable="uv", venv_path="/tmp/env")
    output = (
        "Using Python 3.11.15 environment at: /tmp/env\n"
        '[{"name": "pgzero", "version": "1.2.1"}]\n'
    )
    with mock.patch.object(VE.Process, "run_blocking", return_value=output):
        assert uv.list_packages() == [("pgzero", "1.2.1")]


#
# Command composition (async / Slots), mirroring test_pip.py
#
def test_uv_install_streams_via_slots():
    """install runs `uv pip install` asynchronously through Process.run."""
    uv = Uv(uv_executable="uv", venv_path="/tmp/env")
    with mock.patch.object(VE.Process, "run") as run:
        uv.install(["requests", "rich"])
    args, _ = run.call_args
    assert args[0] == "uv"
    assert args[1] == [
        "pip",
        "install",
        "--python",
        "/tmp/env",
        "requests",
        "rich",
    ]


def test_uv_install_accepts_single_string():
    """A single package name is accepted as a string."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run") as run:
        uv.install("requests")
    args, _ = run.call_args
    assert args[1] == ["pip", "install", "requests"]


def test_uv_install_upgrade_flag():
    """upgrade=True injects --upgrade ahead of the package list."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run") as run:
        uv.install(["requests"], upgrade=True)
    args, _ = run.call_args
    assert args[1] == ["pip", "install", "--upgrade", "requests"]


def test_uv_uninstall_builds_command():
    """uninstall runs `uv pip uninstall` for the given packages."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run") as run:
        uv.uninstall(["requests"])
    args, _ = run.call_args
    assert args[1] == ["pip", "uninstall", "requests"]


#
# Every uv command is recorded in the command log (Phase 4b)
#
@pytest.fixture
def log():
    """A fresh command log in place of the app-wide one."""
    fresh = CommandLog()
    with mock.patch.object(VE, "command_log", fresh):
        yield fresh


def _fake_qprocess(exit_code=0, normal=True):
    qprocess = mock.Mock()
    qprocess.exitCode.return_value = exit_code
    qprocess.exitStatus.return_value = (
        VE.QProcess.ExitStatus.NormalExit
        if normal
        else VE.QProcess.ExitStatus.CrashExit
    )
    return qprocess


def test_uv_run_blocking_records_the_command(log):
    uv = Uv(uv_executable="/opt/uv", venv_path="/env/bin/python")

    def fake_run_blocking(self, command, args, wait_for_s=30.0, **envvars):
        self.process = _fake_qprocess(0)
        return "Using Python 3.11 environment\n[]"

    with mock.patch.object(VE.Process, "run_blocking", fake_run_blocking):
        uv.list_packages()
    (record,) = log.records()
    assert record.argv == [
        "/opt/uv",
        "pip",
        "list",
        "--format=json",
        "--quiet",
        "--python",
        "/env/bin/python",
    ]
    assert record.finished and record.exit_code == 0
    assert record.output_tail() == ["Using Python 3.11 environment", "[]"]


def test_uv_run_blocking_records_a_failure_and_reraises(log):
    uv = Uv(uv_executable="/opt/uv")

    def fake_run_blocking(self, command, args, wait_for_s=30.0, **envvars):
        self.process = _fake_qprocess(2)
        raise VE.VirtualEnvironmentError("Process finished but with error code 2")

    with mock.patch.object(VE.Process, "run_blocking", fake_run_blocking):
        with pytest.raises(VE.VirtualEnvironmentError):
            uv.version()
    (record,) = log.records()
    assert record.exit_code == 2
    assert record.output_tail() == ["Process finished but with error code 2"]


def test_uv_run_blocking_failure_before_start(log):
    """No QProcess at all (it never started): the exit code is unknown."""
    uv = Uv(uv_executable="/opt/uv")
    with mock.patch.object(
        VE.Process, "run_blocking", side_effect=VE.VirtualEnvironmentError("boom")
    ):
        with pytest.raises(VE.VirtualEnvironmentError):
            uv.version()
    (record,) = log.records()
    assert record.finished and record.exit_code is None


def test_uv_run_records_async_command(log):
    """`uv pip install` (async) is recorded, its streamed output kept, and
    finished with the exit code when the process ends."""
    uv = Uv(uv_executable="/opt/uv", venv_path="/env/bin/python")
    qprocess = _fake_qprocess(0)

    def fake_run(self, command, args, **envvars):
        self.process = qprocess

    with mock.patch.object(VE.Process, "run", fake_run):
        process = uv.install(["cowsay"], upgrade=True)
    record = process.command_record
    assert log.records() == [record]
    assert record.display(windows=False) == (
        "uv pip install --upgrade --python /env/bin/python cowsay"
    )
    assert not record.finished
    process.output.emit("Resolved 1 package\nInstalled 1 package")
    process.finished.emit()
    assert record.finished and record.exit_code == 0
    assert record.output_tail() == ["Resolved 1 package", "Installed 1 package"]


def test_uv_run_record_finishes_before_the_callers_finished_slot(log):
    """The record is complete by the time the caller's `finished` slot runs
    (the package dialog starts the next command from it)."""
    uv = Uv(uv_executable="/opt/uv")
    seen = []

    def fake_run(self, command, args, **envvars):
        self.process = _fake_qprocess(1)

    def finished():
        seen.append(log.records()[0].exit_code)

    with mock.patch.object(VE.Process, "run", fake_run):
        process = uv.uninstall("cowsay", slots=VE.Process.Slots(finished=finished))
    process.finished.emit()
    assert seen == [1]


def test_uv_run_crashed_process_has_no_exit_code(log):
    uv = Uv(uv_executable="/opt/uv")

    def fake_run(self, command, args, **envvars):
        self.process = _fake_qprocess(9, normal=False)

    with mock.patch.object(VE.Process, "run", fake_run):
        process = uv.uninstall("cowsay")
    process.finished.emit()
    assert process.command_record.finished
    assert process.command_record.exit_code is None


def test_uv_run_subprocess_records_and_returns_output(log):
    """run_subprocess (plain subprocess, safe off the Qt thread) is how the
    environment is first created; it's recorded too."""
    uv = Uv(uv_executable="/opt/uv")
    completed = mock.Mock(returncode=0, stdout=b"Creating venv", stderr=b"done")
    with mock.patch.object(VE.subprocess, "run", return_value=completed) as run:
        ok, output = uv.run_subprocess("venv", "--python", "3.11", "/env")
    assert ok is True
    assert "Creating venv" in output and "done" in output
    args, kwargs = run.call_args
    assert args[0] == ["/opt/uv", "venv", "--python", "3.11", "/env"]
    (record,) = log.records()
    assert record.exit_code == 0
    assert record.output_tail()[0] == "Creating venv"


def test_uv_run_subprocess_failure(log):
    uv = Uv(uv_executable="/opt/uv")
    completed = mock.Mock(returncode=2, stdout=b"", stderr=b"error: no")
    with mock.patch.object(VE.subprocess, "run", return_value=completed):
        ok, output = uv.run_subprocess("venv", "/env")
    assert ok is False
    assert "error: no" in output
    assert log.records()[0].exit_code == 2


def test_uv_run_subprocess_cannot_start(log):
    """If uv can't even start (e.g. deleted since it was found), say so
    rather than crash."""
    uv = Uv(uv_executable="/opt/uv")
    with mock.patch.object(VE.subprocess, "run", side_effect=OSError("gone")):
        ok, output = uv.run_subprocess("venv", "/env")
    assert ok is False
    assert "gone" in output
    record = log.records()[0]
    assert record.finished and record.exit_code is None


def test_uv_script_command(log):
    """script_command records `uv run --python <venv> --script <file>` for the
    Run pane to launch; the caller finishes it."""
    uv = Uv(uv_executable="/opt/uv", venv_path="/env/bin/python")
    record = uv.script_command("/work/hello.py", cwd="/work")
    assert record.argv == [
        "/opt/uv",
        "run",
        "--python",
        "/env/bin/python",
        "--script",
        "/work/hello.py",
    ]
    assert record.cwd == "/work"
    assert record.note == "Its output is in the Run pane."
    assert not record.finished
    assert log.records() == [record]
