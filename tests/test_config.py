"""
Tests for mu.config, and for the test session's isolation from the real Nu
data and workspace folders that it relies on (see the root conftest.py).
"""

import importlib
import os

import platformdirs

import conftest
import mu.config
from mu import settings
from mu.plugin import loader
from mu.virtual_environment import venv


def reloaded_config(monkeypatch, **environ):
    """mu.config as it would be with `environ` (then put back as it was)."""
    for name in ("MU_DATA_DIR", "MU_HOME_DIR"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    try:
        return vars(importlib.reload(mu.config)).copy()
    finally:
        monkeypatch.undo()
        importlib.reload(mu.config)


def test_data_and_home_directories_default_to_the_platform_ones(monkeypatch):
    config = reloaded_config(monkeypatch)
    assert config["DATA_DIR"] == platformdirs.user_data_dir(
        appname="mu", appauthor="python"
    )
    assert config["HOME_DIRECTORY"] == os.path.expanduser("~")
    assert config["VENV_DIR"] == os.path.join(config["DATA_DIR"], "mu_venv")


def test_data_and_home_directories_from_the_environment(monkeypatch, tmp_path):
    data, home = str(tmp_path / "data"), str(tmp_path / "home")
    config = reloaded_config(monkeypatch, MU_DATA_DIR=data, MU_HOME_DIR=home)
    assert config["DATA_DIR"] == data
    assert config["HOME_DIRECTORY"] == home
    assert config["VENV_DIR"] == os.path.join(data, "mu_venv")


def test_empty_environment_variables_are_ignored(monkeypatch):
    config = reloaded_config(monkeypatch, MU_DATA_DIR="", MU_HOME_DIR="")
    assert config["HOME_DIRECTORY"] == os.path.expanduser("~")


def inside(path, folder):
    path, folder = os.path.abspath(path), os.path.abspath(folder)
    return os.path.commonpath([path, folder]) == folder


def test_the_test_session_never_uses_the_real_folders():
    """
    Everything Nu would write to (its data folder, the workspace, the
    settings files, the learner environment's venv.json, the plugins folder)
    lies in the session's temporary folder, set before `mu` was imported,
    and not in the developer's real Nu data or workspace.
    """
    real_data = platformdirs.user_data_dir(appname="mu", appauthor="python")
    real_workspace = os.path.join(conftest.REAL_HOME, "mu_code")
    root = conftest.SESSION_ROOT
    paths = [
        mu.config.DATA_DIR,
        mu.config.VENV_DIR,
        mu.config.HOME_DIRECTORY,
        settings.UserSettings.DEFAULTS["workspace"],
        settings.settings.DEFAULTS["workspace"],
        venv.settings.filepath,
        venv.path,
    ]
    for path in paths:
        assert inside(path, root), path
        assert not inside(path, real_data), path
        assert not inside(path, real_workspace), path
    # Each test gets its own plugins folder (the temp_plugins_dir fixture).
    assert not inside(loader.DROPIN_DIR, real_data)


def test_log_dir_follows_data_dir():
    """
    With MU_DATA_DIR set (as it is for the test session) the log goes there
    too, never to the real log folder.
    """
    import mu.logic

    assert mu.logic.LOG_DIR == os.path.join(os.environ["MU_DATA_DIR"], "logs")
    assert mu.logic.LOG_FILE.startswith(mu.logic.LOG_DIR)
