"""
Shared fixtures for Nu's tests and the bundled plugins' tests.

Before anything imports `mu`, the whole session is pointed at a throwaway
folder (see `_isolate_session`), so a test run never reads or writes the
developer's real Nu data (settings, session, venv.json, plugins folder) or
workspace (~/mu_code), even through module-level objects created at import
time, such as `mu.virtual_environment.venv`, which registers its settings to
be saved at exit.
"""

import atexit
import os
import random
import shutil
import sys
import tempfile
import threading
from unittest import mock


def _isolate_session():
    """
    Point Nu's data folder and home folder, and IPython's (the REPL tests
    start a real IPython shell), at a new temporary folder (removed at exit),
    and give the single-instance lock a name of its own so tests
    never clash with a Nu that's running. Returns the folder.
    """
    root = tempfile.mkdtemp(prefix="nu-tests-")
    folders = (
        ("MU_DATA_DIR", "data"),
        ("MU_HOME_DIR", "home"),
        ("IPYTHONDIR", "ipython"),
    )
    for name, folder in folders:
        os.environ[name] = os.path.join(root, folder)
        os.mkdir(os.environ[name])
    os.environ["MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT"] = "_session_{}".format(
        random.randint(0, 100000000)
    )
    # Registered before mu's own atexit saves, so it runs after them.
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    return root


# The real folders, for the test that checks they aren't used.
REAL_HOME = os.path.expanduser("~")
SESSION_ROOT = _isolate_session()

import pytest  # noqa: E402
from PyQt6.QtCore import QCoreApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from mu import settings  # noqa: E402

# Keep global reference to avoid being garbage collected
_qapp_instance = None


@pytest.fixture(scope="session", autouse=True)
def qtapp():
    app = QApplication.instance()
    if app is None:
        global _qapp_instance
        _qapp_instance = QApplication([])
        return _qapp_instance
    else:
        return app


@pytest.fixture(scope="session", autouse=True)
def disable_autosave():
    """Ensure that no settings are autosaved as part of a test"""
    with mock.patch.object(settings.SettingsBase, "register_for_autosave") as register:
        yield register


@pytest.fixture(autouse=True)
def temp_shared_mem_app_name():
    """Make multi-instance execution blocking shared memory app name unique for tests"""
    session_name = os.environ["MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT"]
    os.environ["MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT"] = "_" + str(
        random.randint(0, 100000000)
    )
    yield
    os.environ["MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT"] = session_name


@pytest.fixture(autouse=True)
def temp_plugins_dir(tmp_path, monkeypatch):
    """Never discover (or create) the real drop-in plugins folder in tests"""
    from mu.plugin import loader

    monkeypatch.setattr(loader, "DROPIN_DIR", str(tmp_path / "plugins"))


@pytest.fixture(autouse=True)
def no_plugin_error_handler(monkeypatch):
    """Don't let one test's plugin error handler leak into another"""
    from mu.plugin import errors

    monkeypatch.setattr(errors, "_active", None)


@pytest.fixture(autouse=True)
def no_plugin_images():
    """Don't let one test's plugin images leak into another"""
    from mu import resources

    yield
    for directory in resources.plugin_image_dirs():
        resources.unregister_image_dir(directory)


def _refuse_to_quit(*args, **kwargs):
    raise AssertionError(
        "A test asked the QApplication to quit. With no event loop running, "
        "that makes every later QEventLoop.exec() return at once; patch "
        "QCoreApplication.exit (or quit) in the test instead."
    )


@pytest.fixture(autouse=True)
def no_application_quit(monkeypatch):
    """Fail a test that would leave the QApplication quitting for the rest"""
    monkeypatch.setattr(QCoreApplication, "exit", staticmethod(_refuse_to_quit))
    monkeypatch.setattr(QCoreApplication, "quit", staticmethod(_refuse_to_quit))


@pytest.fixture(autouse=True)
def restore_exception_hooks():
    """Undo a test's `mu.app.setup_exception_handler()` (or other hooks)"""
    import mu.app

    saved = (
        sys.excepthook,
        threading.excepthook,
        mu.app._previous_thread_excepthook,
    )
    yield
    (
        sys.excepthook,
        threading.excepthook,
        mu.app._previous_thread_excepthook,
    ) = saved
