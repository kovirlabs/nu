from unittest import mock

import pytest
import os
import random
from PyQt6.QtWidgets import QApplication

from mu import settings

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
    os.environ["MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT"] = "_" + str(
        random.randint(0, 100000000)
    )
    yield
    os.environ.pop("MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT", "")


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
