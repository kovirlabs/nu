# -*- coding: utf-8 -*-
"""
Tests for keeping Nu running when a plugin has an error.
"""

import logging
import sys
import textwrap
import uuid
from unittest import mock

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import mu.app
from mu import settings
from mu.modes.base import BaseMode
from mu.plugin import Host, PluginError, errors, loader
from mu.plugin.errors import GUARDED_MODE_METHODS, PluginErrorHandler
from mu.plugin.loader import PluginRecord

PLUGIN_MODULE = textwrap.dedent(
    """
    from mu.plugin import Mode, ModePlugin, PluginError

    class BuggyMode(Mode):
        name = "Buggy"
        short_name = "{short_name}"

        def activate(self):
            raise RuntimeError("activate broke")

        def api(self):
            raise ValueError("no api")

        def actions(self):
            return [{{"name": "run", "display_name": "Go",
                     "description": "", "handler": self.go,
                     "shortcut": None}}]

        def go(self, event=None):
            helper()

        def expected(self):
            raise PluginError("Plug in your board", "Use a USB cable.")

    def helper():
        raise ZeroDivisionError("division by zero")

    class BuggyPlugin(ModePlugin):
        name = "Buggy"
        api_version = "0.1"
        mode = BuggyMode
    """
)


@pytest.fixture
def host():
    return Host(mock.MagicMock(), mock.MagicMock())


@pytest.fixture
def plugin_module(tmp_path):
    """Import a real plugin module from a file, as the drop-in loader does."""
    name = "buggy_" + uuid.uuid4().hex[:8]
    path = tmp_path / (name + ".py")
    path.write_text(PLUGIN_MODULE.format(short_name=name))
    module = loader._import_dropin(name, str(path))
    yield module
    sys.modules.pop(name, None)


@pytest.fixture
def loaded(host, plugin_module):
    """The buggy plugin loaded into `host`, with a record giving its id."""
    plugin = plugin_module.BuggyPlugin()
    assert host.load_plugin(plugin)
    host.plugin_records = [
        PluginRecord("buggy", "folder", "buggy.py", loader.LOADED, plugin=plugin)
    ]
    (mode,) = host._modes_of(plugin)
    return plugin, mode


def raise_and_get_tb(func, *args):
    try:
        func(*args)
    except BaseException as ex:
        return type(ex), ex, ex.__traceback__
    raise AssertionError("didn't raise")


# --- PluginError ---


def test_plugin_error():
    error = PluginError("Plug in your board", "Use a USB cable.")
    assert str(error) == "Plug in your board"
    assert error.message == "Plug in your board"
    assert error.information == "Use a USB cable."
    assert PluginError("x").information is None


# --- guarding plugin modes ---


def test_plugin_modes_are_guarded_core_modes_are_not(host, loaded):
    plugin, mode = loaded

    class CoreMode(BaseMode):
        short_name = "core"

    core = host.register_mode(CoreMode)
    assert mode.activate.__wrapped__.__func__ is type(mode).activate
    assert not hasattr(core.activate, "__wrapped__")


def test_guarded_methods_report_and_fall_back(host, loaded):
    plugin, mode = loaded
    with mock.patch.object(host._error_handler, "report") as report:
        assert mode.activate() is None
        assert mode.api() == []
    assert [c.kwargs["where"] for c in report.call_args_list] == [
        "activate",
        "api",
    ]
    reported_plugin, exc, tb = report.call_args_list[0].args
    assert reported_plugin is plugin
    assert str(exc) == "activate broke"
    assert tb is exc.__traceback__


def test_guarded_methods_pass_results_through(host, loaded):
    plugin, mode = loaded
    (action,) = mode.actions()
    assert action["display_name"] == "Go"


@pytest.mark.parametrize("name, fallback", list(GUARDED_MODE_METHODS.items()))
def test_every_guarded_method_has_a_safe_fallback(host, name, fallback):
    """
    Each method the core calls falls back to a harmless value, and missing
    methods (e.g. remove_fs) are left alone.
    """

    class Plugin_:
        name = "p"

    mode = mock.MagicMock()
    getattr(mode, name).side_effect = RuntimeError("broken")
    handler = PluginErrorHandler(host)
    with (
        mock.patch.object(handler, "report"),
        mock.patch.object(BaseMode, "workspace_dir", return_value="/ws"),
    ):
        handler.guard_mode(mode, Plugin_())
        result = getattr(mode, name)()
    expected = {list: [], None: None}.get(fallback, "/ws")
    assert result == expected


def test_guard_skips_missing_methods(host):
    mode = BaseMode(None, None)  # has no find_devices / remove_* methods
    PluginErrorHandler(host).guard_mode(mode, mock.MagicMock())
    assert not hasattr(mode, "remove_fs")
    assert hasattr(mode.activate, "__wrapped__")


def test_guard_catches_system_exit_but_not_ctrl_c(host):
    handler = PluginErrorHandler(host)
    mode = mock.MagicMock()
    mode.activate.side_effect = SystemExit(1)
    mode.stop.side_effect = KeyboardInterrupt
    with mock.patch.object(handler, "report") as report:
        handler.guard_mode(mode, mock.MagicMock())
        mode.activate()
        with pytest.raises(KeyboardInterrupt):
            mode.stop()
    report.assert_called_once()


# --- working out whose code failed ---


def test_owner_finds_plugin_module_code(host, loaded):
    plugin, mode = loaded
    exc_type, exc, tb = raise_and_get_tb(mode.go)
    assert host._error_handler.owner(tb) is plugin


def test_owner_finds_inherited_core_code_run_for_a_plugin_mode(host, loaded):
    """
    Core MicroPythonMode/BaseMode code running on a plugin's mode counts as
    the plugin's (e.g. its inherited REPL handling).
    """
    plugin, mode = loaded
    mode.view.current_tab = None
    with mock.patch("os.makedirs", side_effect=OSError("read-only")):
        exc_type, exc, tb = raise_and_get_tb(lambda: mode.assets_dir("images"))
    assert exc_type is OSError
    assert host._error_handler.owner(tb) is plugin


def test_owner_ignores_core_code(host, loaded):
    def core():
        raise ValueError("core bug")

    # Pretend this test module is core: only "tests" frames are involved.
    exc_type, exc, tb = raise_and_get_tb(core)
    assert host._error_handler.owner(tb) is None


def test_owner_with_no_plugins(host):
    exc_type, exc, tb = raise_and_get_tb(lambda: 1 / 0)
    assert host._error_handler.owner(tb) is None


def test_handle_uncaught(host, loaded):
    plugin, mode = loaded
    handler = host._error_handler
    exc_info = raise_and_get_tb(mode.go)
    with mock.patch.object(handler, "report") as report:
        assert handler.handle_uncaught(*exc_info) is True
        assert handler.handle_uncaught(*raise_and_get_tb(lambda: 1 / 0)) is False
        assert handler.handle_uncaught(KeyboardInterrupt, None, exc_info[2]) is False
        assert handler.handle_uncaught(ZeroDivisionError, None, exc_info[2]) is True
    assert report.call_args_list[0].args == (plugin, exc_info[1], exc_info[2])
    assert isinstance(report.call_args_list[1].args[1], ZeroDivisionError)


def test_handle_uncaught_survives_its_own_errors(host, caplog):
    handler = host._error_handler
    with mock.patch.object(handler, "owner", side_effect=RuntimeError("oops")):
        with caplog.at_level(logging.ERROR):
            assert handler.handle_uncaught(ValueError, ValueError(), None) is False
    assert "Couldn't work out where an error came from" in caplog.text


# --- telling the learner ---


@pytest.fixture
def clock():
    now = [100.0]

    def tick():
        return now[0]

    tick.now = now
    return tick


@pytest.fixture
def handler(host, clock, loaded):
    plugin, mode = loaded
    handler = PluginErrorHandler(host, clock=clock)
    return handler, plugin


def test_expected_error_shows_its_message(host, handler, caplog):
    handler, plugin = handler
    with caplog.at_level(logging.INFO):
        handler.report(plugin, PluginError("Plug in your board", "Use a cable."))
    host._view.show_message.assert_called_once_with(
        "Plug in your board", "Use a cable.", "Information"
    )
    assert handler.error_count(plugin) == 0  # not a bug in the plugin
    assert "Plugin Buggy: Plug in your board" in caplog.text


def test_expected_error_while_a_dialog_is_open_goes_to_status_bar(host, handler):
    handler, plugin = handler
    handler._dialog_open = True
    handler.report(plugin, PluginError("Plug in your board"))
    host._view.show_message.assert_not_called()
    host._editor.show_status_message.assert_called_once_with("Plug in your board", 5)


def test_unexpected_error_dialog(host, handler, caplog):
    handler, plugin = handler
    exc_type, exc, tb = raise_and_get_tb(lambda: 1 / 0)
    with caplog.at_level(logging.ERROR):
        handler.report(plugin, exc, tb, where="go")
    (call,) = host._view.show_message.call_args_list
    message, information, icon = call.args
    assert message == "The Buggy plugin had a problem and stopped what it was doing."
    assert "ZeroDivisionError: division by zero" in information
    assert "Nu is still running" in information
    assert icon == "Warning"
    assert handler.error_count(plugin) == 1
    assert "Plugin Buggy failed in go()" in caplog.text
    assert "Traceback" in caplog.text


def test_repeat_errors_are_rate_limited_and_logged_briefly(
    host, handler, clock, caplog
):
    """
    Within DIALOG_INTERVAL further errors go to the status bar, and an error
    already logged in full gets a one-line log entry.
    """
    handler, plugin = handler
    error = ValueError("same")
    handler.report(plugin, error)
    caplog.clear()
    clock.now[0] += handler.DIALOG_INTERVAL - 1
    with caplog.at_level(logging.ERROR):
        handler.report(plugin, error)
    assert host._view.show_message.call_count == 1
    host._editor.show_status_message.assert_called_once_with(
        "The Buggy plugin had another problem (see the log).", 5
    )
    assert "Plugin Buggy failed again: ValueError: same (error #2)" in caplog.text
    assert "Traceback" not in caplog.text


def test_errors_while_a_dialog_is_open_go_to_status_bar(host, handler):
    """
    A modal dialog runs a nested event loop; a timer failing meanwhile must
    not open dialog after dialog.
    """
    handler, plugin = handler

    def show_message(*args):
        handler.report(plugin, ValueError("again, from a timer"))

    host._view.show_message.side_effect = show_message
    handler.report(plugin, ValueError("first"))
    assert host._view.show_message.call_count == 1
    host._editor.show_status_message.assert_called_once()
    assert handler._dialog_open is False


@pytest.mark.parametrize("answer, disabled", [(True, ["buggy"]), (False, [])])
def test_offers_to_switch_off_a_plugin_that_keeps_failing(
    host, handler, clock, answer, disabled
):
    handler, plugin = handler
    store = settings.UserSettings()
    host._view.show_confirmation.return_value = 1024 if answer else 4194304
    with mock.patch.object(settings, "settings", store):
        for _ in range(handler.SWITCH_OFF_AFTER):
            clock.now[0] += handler.DIALOG_INTERVAL
            handler.report(plugin, ValueError("broken"))
        # Never asked twice.
        clock.now[0] += handler.DIALOG_INTERVAL
        handler.report(plugin, ValueError("broken"))
    assert host._view.show_message.call_count == handler.SWITCH_OFF_AFTER
    (call,) = host._view.show_confirmation.call_args_list
    assert call.args[0] == "The Buggy plugin keeps having problems."
    assert call.args[2] == "Question"
    assert sorted(store.get("disabled_plugins", [])) == disabled


def test_no_switch_off_offer_without_a_plugin_id(host, handler, clock):
    handler, plugin = handler
    host.plugin_records = []
    for _ in range(handler.SWITCH_OFF_AFTER):
        clock.now[0] += handler.DIALOG_INTERVAL
        handler.report(plugin, ValueError("broken"))
    host._view.show_confirmation.assert_not_called()
    assert host._view.show_message.call_count == handler.SWITCH_OFF_AFTER


def test_report_never_raises(host, handler, caplog):
    handler, plugin = handler
    host._view.show_message.side_effect = RuntimeError("no window")
    with caplog.at_level(logging.ERROR):
        handler.report(plugin, ValueError("broken"))
    assert "Failed to report an error in plugin" in caplog.text
    assert handler._dialog_open is False


# --- the excepthook hand-off ---


def test_module_handle_uncaught_without_a_handler():
    assert errors.handle_uncaught(ValueError, ValueError(), None) is False


def test_module_handle_uncaught_uses_installed_handler():
    active = mock.MagicMock()
    active.handle_uncaught.return_value = True
    errors.install(active)
    assert errors.handle_uncaught(ValueError, "exc", "tb") is True
    active.handle_uncaught.assert_called_once_with(ValueError, "exc", "tb")


def test_module_handle_uncaught_survives_a_broken_handler(caplog):
    active = mock.MagicMock()
    active.handle_uncaught.side_effect = RuntimeError("oops")
    errors.install(active)
    with caplog.at_level(logging.ERROR):
        assert errors.handle_uncaught(ValueError, ValueError(), None) is False
    assert "Plugin error handling failed" in caplog.text


def test_excepthook_lets_nu_carry_on_after_a_plugin_error():
    with (
        mock.patch.object(errors, "handle_uncaught", return_value=True) as handle,
        mock.patch("sys.exit") as exit_,
    ):
        mu.app.excepthook(ValueError, ValueError("x"), None)
    handle.assert_called_once()
    exit_.assert_not_called()


def test_setup_modes_installs_the_hosts_handler():
    with mock.patch("mu.app.load_plugins", return_value=[]):
        modes = mu.app.setup_modes(mock.MagicMock(), mock.MagicMock())
    assert errors._active is modes["python"].host._error_handler


def test_a_failing_plugin_button_does_not_crash_nu(host, loaded, monkeypatch):
    """
    End to end through Qt: a plugin's handler raising inside the event loop
    reaches app.excepthook, is reported, and Nu doesn't exit.
    """
    plugin, mode = loaded
    errors.install(host._error_handler)
    monkeypatch.setattr(sys, "excepthook", mu.app.excepthook)
    exit_ = mock.MagicMock()
    monkeypatch.setattr(sys, "exit", exit_)
    with mock.patch.object(host._error_handler, "report") as report:
        QTimer.singleShot(0, mode.go)
        for _ in range(5):
            QApplication.processEvents()
    exit_.assert_not_called()
    reported_plugin, exc, tb = report.call_args.args
    assert reported_plugin is plugin
    assert isinstance(exc, ZeroDivisionError)
