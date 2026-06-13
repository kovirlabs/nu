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


def test_find_uv_not_found():
    """No MU_UV and nothing on PATH raises UvNotFound."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(VE.shutil, "which", return_value=None):
            with pytest.raises(VE.UvNotFound):
                VE.find_uv()


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
    assert args[1] == ["pip", "list", "--format=json", "--python", "/tmp/env"]


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


def test_uv_uninstall_builds_command():
    """uninstall runs `uv pip uninstall` for the given packages."""
    uv = Uv(uv_executable="uv")
    with mock.patch.object(VE.Process, "run") as run:
        uv.uninstall(["requests"])
    args, _ = run.call_args
    assert args[1] == ["pip", "uninstall", "requests"]
