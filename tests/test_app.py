# -*- coding: utf-8 -*-
"""
Tests for the app script.
"""

import logging
import sys
import os.path
import pytest
import subprocess
import threading
import time

from unittest import mock
import mu.app
from mu.app import (
    crash_details,
    show_crash_dialog,
    excepthook,
    run,
    setup_logging,
    setup_exception_handler,
    thread_excepthook,
    AnimatedSplash,
    StartupWorker,
    vlogger,
    check_only_running_once,
    _shared_memory,
)
from mu.debugger.config import DEBUGGER_PORT

from mu.interface.themes import NIGHT_STYLE, DAY_STYLE, CONTRAST_STYLE
from mu.logic import LOG_FILE, LOG_DIR, ENCODING
from mu.resources import load_movie
from mu import mu_debug
from mu import __version__ as mu_version
from mu.virtual_environment import VirtualEnvironment as VE, SplashLogHandler
from PyQt6.QtCore import Qt


class DumSig:
    """
    Fake signal for mocking purposes

    Only supports a signal callback
    """

    def __init__(self):
        """
        Setup the signal
        """

        # Setup a fallback handled
        @self.connect
        def default(*args):
            # ... and throw an exception because it still exists
            raise Exception("No signal handler connected")

    def connect(self, func):
        """
        Set the callback function
        """
        self.func = func
        return func

    def emit(self, *args):
        """
        Proxy the callback function
        """
        self.func(*args)


def test_animated_splash_init():
    """
    Ensure the AnimatedSplash class uses the passed in animation.
    """
    test_animation = load_movie("splash_screen")
    test_animation.frameChanged = mock.MagicMock()
    test_animation.start = mock.MagicMock()
    asplash = AnimatedSplash(test_animation)
    assert asplash.animation == test_animation
    asplash.animation.frameChanged.connect.assert_called_once_with(asplash.set_frame)
    asplash.animation.start.assert_called_once_with()


def test_animated_splash_set_frame():
    """
    Ensure the splash screen's pixmap is updated with the animation's current
    pixmap.
    """
    test_animation = load_movie("splash_screen")
    test_animation.frameChanged = mock.MagicMock()
    test_animation.start = mock.MagicMock()
    asplash = AnimatedSplash(test_animation)
    asplash.setPixmap = mock.MagicMock()
    asplash.setMask = mock.MagicMock()
    test_animation.currentPixmap = mock.MagicMock()
    asplash.set_frame()
    asplash.animation.currentPixmap.assert_called_once_with()
    pixmap = asplash.animation.currentPixmap()
    asplash.setPixmap.assert_called_once_with(pixmap)
    asplash.setMask.assert_called_once_with(pixmap.mask())


def test_animated_splash_draw_log():
    """
    Ensure the scrolling updates from the log handler are sliced properly and
    the expected text is shown in the right place on the splash screen.
    """
    test_animation = load_movie("splash_screen")
    asplash = AnimatedSplash(test_animation)
    asplash.log = [
        "1st line of the log",
        "2nd line of the log",
        "3rd line of the log",
        "4th line of the log",
        "5th line of the log",
    ]
    asplash.showMessage = mock.MagicMock()
    msg = "A new line of the log"
    expected = asplash.log[-3:]
    expected.append(msg)
    expected = "\n".join(expected)
    asplash.draw_log(msg)
    asplash.showMessage.assert_called_once_with(
        expected, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
    )


def test_animated_splash_failed():
    """
    When instructed to transition to a failed state, ensure the correct image
    is displayed along with the correct message.
    """
    test_animation = load_movie("splash_screen")
    asplash = AnimatedSplash(test_animation)
    asplash.setPixmap = mock.MagicMock()
    asplash.draw_text = mock.MagicMock()
    error = (
        "Something went boom!\n"
        "This is an error message...\n"
        "In real life, this would include a stack trace.\n"
        "It will also include details about the exception.\n"
    )
    with mock.patch("mu.app.load_pixmap") as load_pix:
        asplash.failed(error)
        load_pix.assert_called_once_with("splash_fail.png")
    asplash.draw_text.assert_called_once_with(
        error
        + "\nThis screen will close in a few seconds. "
        + "Then a crash report tool will open in your browser."
    )
    assert asplash.setPixmap.call_count == 1


def test_worker_run():
    """
    Ensure the finished signal is called when the tasks called in the run
    method are completed.
    """
    w = StartupWorker()
    slh = SplashLogHandler(w.display_text)
    vlogger.addHandler(slh)
    w.finished = mock.MagicMock()
    with mock.patch("mu.app.venv.ensure_and_create") as mock_ensure:
        w.run()
        assert mock_ensure.call_count == 1
        w.finished.emit.assert_called_once_with()
    # Ensure the splash related logger handler has been removed.
    while vlogger.hasHandlers() and vlogger.handlers:
        handler = vlogger.handlers[0]
        assert not isinstance(handler, SplashLogHandler)


def test_worker_fail():
    """
    Ensure that exceptions encountered during Mu's start-up are handled in the
    expected manner.
    """
    w = StartupWorker()
    w.finished = mock.MagicMock()
    w.failed = mock.MagicMock()
    mock_ensure = mock.MagicMock()
    ex = RuntimeError("Boom")
    mock_ensure.side_effect = ex
    with pytest.raises(RuntimeError):
        with (
            mock.patch("mu.app.venv.ensure_and_create", mock_ensure),
            mock.patch("mu.app.time") as mock_time,
        ):
            w.run()
    assert mock_ensure.call_count == 1
    assert w.failed.emit.call_count == 1
    mock_time.sleep.assert_called_once_with(7)
    w.finished.emit.assert_called_once_with()


def test_setup_logging_without_envvar():
    """
    Ensure that logging is set up in some way.

    Resetting the MU_LOG_TO_STDOUT env var should mean stdout logging is disabled
    """
    os.environ.pop("MU_LOG_TO_STDOUT", "")
    with (
        mock.patch("mu.app.TimedRotatingFileHandler") as log_conf,
        mock.patch("mu.app.os.path.exists", return_value=False),
        mock.patch("mu.app.logging") as logging,
        mock.patch("mu.app.os.makedirs", return_value=None) as mkdir,
    ):
        setup_logging()
        mkdir.assert_called_once_with(LOG_DIR, exist_ok=True)
        log_conf.assert_called_once_with(
            LOG_FILE,
            when="midnight",
            backupCount=5,
            delay=0,
            encoding=ENCODING,
        )
        logging.getLogger.assert_called_once_with()


def test_setup_logging_with_envvar():
    """
    Ensure that logging is set up in some way.

    Setting the MU_LOG_TO_STDOUT env var ensures that stdout logging
    will be enabled
    """
    os.environ["MU_LOG_TO_STDOUT"] = "1"
    with (
        mock.patch("mu.app.TimedRotatingFileHandler") as log_conf,
        mock.patch("mu.app.os.path.exists", return_value=False),
        mock.patch("mu.app.logging") as logging,
        mock.patch("mu.app.os.makedirs", return_value=None) as mkdir,
    ):
        setup_logging()
        mkdir.assert_called_once_with(LOG_DIR, exist_ok=True)
        log_conf.assert_called_once_with(
            LOG_FILE,
            when="midnight",
            backupCount=5,
            delay=0,
            encoding=ENCODING,
        )
        logging.getLogger.assert_called_once_with()
        # clear this to avoid interfering with other tests
        os.environ.pop("MU_LOG_TO_STDOUT", "")


def test_setup_except_hook(monkeypatch):
    """
    confirm that setup_exception_handler() is setting up the global exception hook
    """
    saved = sys.excepthook
    previous = mock.MagicMock()
    monkeypatch.setattr(threading, "excepthook", previous)
    monkeypatch.setattr(mu.app, "_previous_thread_excepthook", None)
    setup_exception_handler()
    assert sys.excepthook == excepthook
    assert threading.excepthook is thread_excepthook
    assert mu.app._previous_thread_excepthook is previous
    # Setting up again never chains the hook to itself.
    setup_exception_handler()
    assert mu.app._previous_thread_excepthook is previous
    sys.excepthook = saved


def thread_error(exc_type=ValueError, message="BANG", thread_name="worker"):
    """The argument threading.excepthook gets for an error in a thread."""
    try:
        raise exc_type(message)
    except BaseException as ex:
        exc = ex
    thread = mock.MagicMock()
    thread.name = thread_name
    return mock.MagicMock(
        exc_type=exc_type,
        exc_value=exc,
        exc_traceback=exc.__traceback__,
        thread=thread,
    )


def test_thread_excepthook_logs_core_errors(monkeypatch, caplog):
    """
    An error in a thread that isn't a plugin's goes to Nu's log (with its
    traceback) and then to the previous hook, which prints it as before.
    """
    previous = mock.MagicMock()
    monkeypatch.setattr(mu.app, "_previous_thread_excepthook", previous)
    args = thread_error()
    with (
        mock.patch.object(mu.app.plugin_errors, "handle_uncaught", return_value=False),
        caplog.at_level(logging.ERROR),
    ):
        thread_excepthook(args)
    assert "Unhandled error in thread worker" in caplog.text
    assert "ValueError: BANG" in caplog.text
    previous.assert_called_once_with(args)


def test_thread_excepthook_plugin_errors(monkeypatch, caplog):
    """A plugin's error is reported by the plugin error handler instead."""
    previous = mock.MagicMock()
    monkeypatch.setattr(mu.app, "_previous_thread_excepthook", previous)
    args = thread_error()
    with (
        mock.patch.object(
            mu.app.plugin_errors, "handle_uncaught", return_value=True
        ) as handle,
        caplog.at_level(logging.ERROR),
    ):
        thread_excepthook(args)
    handle.assert_called_once_with(args.exc_type, args.exc_value, args.exc_traceback)
    previous.assert_not_called()
    assert caplog.text == ""


def test_thread_excepthook_system_exit(monkeypatch, caplog):
    """sys.exit() in a thread just ends the thread, as it always has."""
    previous = mock.MagicMock()
    monkeypatch.setattr(mu.app, "_previous_thread_excepthook", previous)
    args = thread_error(SystemExit, 0)
    with (
        mock.patch.object(mu.app.plugin_errors, "handle_uncaught") as handle,
        caplog.at_level(logging.ERROR),
    ):
        thread_excepthook(args)
    handle.assert_not_called()
    previous.assert_called_once_with(args)
    assert caplog.text == ""


def test_thread_excepthook_without_a_previous_hook(monkeypatch):
    """Before setup, the hook falls back to Python's own."""
    monkeypatch.setattr(mu.app, "_previous_thread_excepthook", None)
    original = mock.MagicMock()
    monkeypatch.setattr(threading, "__excepthook__", original)
    args = thread_error()
    args.thread = None
    with mock.patch.object(mu.app.plugin_errors, "handle_uncaught", return_value=False):
        thread_excepthook(args)
    original.assert_called_once_with(args)


def test_run():
    """
    Ensure the run function sets things up in the expected way.

    Why check this?

    We need to know if something fundamental has inadvertently changed and
    these tests highlight such a case.

    Testing the call_count and mock_calls allows us to measure the expected
    number of instantiations and method calls.
    """

    class Win(mock.MagicMock):
        load_theme = DumSig()
        icon = "icon"

    window = Win()

    with (
        mock.patch("mu.app.setup_logging") as set_log,
        mock.patch("mu.app.QApplication") as qa,
        mock.patch("mu.app.AnimatedSplash") as qsp,
        mock.patch("mu.app.Editor") as ed,
        mock.patch("mu.app.load_movie"),
        mock.patch("mu.app.Window", window) as win,
        mock.patch("sys.argv", ["mu"]),
        mock.patch("sys.exit") as ex,
        mock.patch("mu.app.QEventLoop") as mock_event_loop,
        mock.patch("mu.app.QThread"),
        mock.patch("mu.app.StartupWorker") as mock_worker,
        mock.patch("mu.app.setup_exception_handler") as mock_set_except,
    ):
        run()
        assert set_log.call_count == 1
        # foo.call_count is instantiating the class
        assert qa.call_count == 1
        # foo.mock_calls are method calls on the object. Under Qt6 high-DPI
        # scaling is always on, so the two AA_*HighDpi* setAttribute calls that
        # Qt5 needed are gone (was 9 with them, now 7).
        assert len(qa.mock_calls) == 7
        assert qsp.call_count == 1
        assert len(qsp.mock_calls) == 4
        assert ed.call_count == 1
        assert len(ed.mock_calls) == 4
        assert win.call_count == 1
        assert len(win.mock_calls) == 6
        assert ex.call_count == 1
        assert mock_event_loop.call_count == 1
        assert mock_worker.call_count == 1
        assert mock_set_except.call_count == 1
        window.load_theme.emit("day")
        qa.assert_has_calls([mock.call().setStyleSheet(DAY_STYLE)])
        window.load_theme.emit("night")
        qa.assert_has_calls([mock.call().setStyleSheet(NIGHT_STYLE)])
        window.load_theme.emit("contrast")
        qa.assert_has_calls([mock.call().setStyleSheet(CONTRAST_STYLE)])


@pytest.mark.skip("Possibly hanging...")
def test_close_splash_screen():
    """
    Test that the splash screen is closed.
    """

    # Create a dummy window
    class Win(mock.MagicMock):
        load_theme = DumSig()
        icon = "icon"

    window = Win()

    # Create a dummy timer class
    class DummyTimer:
        def __init__(self):
            self.callback = lambda x: None
            self.stop = lambda: None
            self.setSingleShot = lambda x: None

            def set_callback(fun):
                self.callback = fun

            class Object(object):
                pass

            self.timeout = Object()
            self.timeout.connect = set_callback

        def start(self, t):
            # Just call the callback immediately
            self.callback()

    # Mock Splash screen
    splash = mock.MagicMock()

    # Mock QTimer, QApplication, Window, Editor, sys.exit
    with (
        mock.patch("mu.app.Window", window),
        mock.patch("mu.app.QApplication"),
        mock.patch("sys.exit"),
        mock.patch("mu.app.Editor"),
        mock.patch("mu.app.AnimatedSplash", return_value=splash),
        mock.patch.object(VE, "ensure_and_create"),
    ):
        run()
        assert splash.close.call_count == 1


def test_excepthook():
    """
    Test that custom excepthook logs the error, shows the crash details
    (without sending them anywhere) and calls sys.exit.
    """
    ex = Exception("BANG")
    exc_args = (type(ex), ex, ex.__traceback__)

    with (
        mock.patch("mu.app.logging.error") as error,
        mock.patch("mu.app.sys.exit") as exit,
        mock.patch("mu.app.show_crash_dialog") as show,
    ):
        excepthook(*exc_args)
        error.assert_called_once_with("Unrecoverable error", exc_info=exc_args)
        exit.assert_called_once_with(1)
        (details,) = show.call_args.args
        assert "Exception: BANG" in details


def test_excepthook_alamo():
    """
    If showing the crash details itself encounters an error, then ensure this
    is logged before exiting.
    """
    ex = Exception("BANG")
    exc_args = (type(ex), ex, ex.__traceback__)

    with (
        mock.patch("mu.app.logging.error") as error,
        mock.patch("mu.app.sys.exit") as exit,
        mock.patch("mu.app.show_crash_dialog", side_effect=RuntimeError("DIALOG BANG")),
    ):
        excepthook(*exc_args)
        assert error.call_count == 2
        assert error.call_args.args == ("Failed to show the crash details",)
        exit.assert_called_once_with(1)


def test_excepthook_keyboard_interrupt():
    """
    Ctrl-C exits quietly, without the crash dialog.
    """
    with (
        mock.patch("mu.app.logging.error"),
        mock.patch("mu.app.sys.exit") as exit,
        mock.patch("mu.app.show_crash_dialog") as show,
    ):
        excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    exit.assert_called_once_with(0)
    show.assert_not_called()


def test_crash_details():
    try:
        raise ValueError("BANG")
    except ValueError as ex:
        details = crash_details(type(ex), ex, ex.__traceback__)
    lines = details.splitlines()
    assert lines[0] == "Nu {}".format(mu_version)
    assert lines[1].startswith("Python ")
    assert lines[2] == "Log file: {}".format(LOG_FILE)
    assert "Traceback (most recent call last):" in details
    assert details.endswith("ValueError: BANG")


def test_show_crash_dialog(monkeypatch):
    monkeypatch.delenv("MU_SUPPRESS_CRASH_REPORT_FORM", raising=False)
    with mock.patch("mu.app.CrashDialog") as dialog:
        show_crash_dialog("details")
    dialog.assert_called_once_with("details")
    dialog.return_value.exec.assert_called_once_with()


def test_show_crash_dialog_suppressed(monkeypatch):
    monkeypatch.setenv("MU_SUPPRESS_CRASH_REPORT_FORM", "1")
    with mock.patch("mu.app.CrashDialog") as dialog:
        show_crash_dialog("details")
    dialog.assert_not_called()


def test_show_crash_dialog_before_qapplication(monkeypatch):
    """
    A crash before the QApplication exists can't show a dialog; the details
    are still logged and printed by the excepthook.
    """
    monkeypatch.delenv("MU_SUPPRESS_CRASH_REPORT_FORM", raising=False)
    with (
        mock.patch("mu.app.QApplication.instance", return_value=None),
        mock.patch("mu.app.CrashDialog") as dialog,
    ):
        show_crash_dialog("details")
    dialog.assert_not_called()


def test_debug():
    """
    Ensure the debugger is run with the expected arguments given the filename
    and other arguments passed in via sys.argv.
    """
    args = ("foo", "bar", "baz")
    filename = "foo.py"
    # The path keeps its case: it's what the learner sees in tracebacks.
    expected_filename = os.path.abspath(filename)
    mock_runner = mock.MagicMock(return_value=1)
    with mock.patch("mu.debugger.runner.run", mock_runner):
        assert mu_debug.debug(filename, *args) == 1
        mock_runner.assert_called_once_with(
            "localhost", DEBUGGER_PORT, expected_filename, args
        )


def test_debug_no_args():
    """
    If the debugger is accidentally started with no filename and/or associated
    args, then emit a friendly message to indicate the problem.
    """
    expected_msg = "Debugger requires a Python script filename to run."
    mock_print = mock.MagicMock()
    with mock.patch("builtins.print", mock_print):
        assert mu_debug.debug() == 2
        mock_print.assert_called_once_with(expected_msg)


def test_only_running_once():
    """
    If we are the first to acquire the application lock we should succeed
    """
    setup_exception_handler()
    check_only_running_once()
    _shared_memory.release()
    assert True


def test_running_twice():
    # try chaining instead of timing based stuff

    # Comment on the original test says:
    #
    #   It's important that the two competing processes are not part of the same
    #   process tree; otherwise the second attempt to acquire the mutex will
    #   succeed (which we don't want to happen for our purposes)
    #
    # However, on macOS it always seems to have the same parent process id and group
    # process id and this test seems to work on all platforms on CI.
    #
    cmd2 = "".join(
        (
            "-c",
            "from mu import app;",
            "app.setup_exception_handler();",
            "app.check_only_running_once()",
            # should throw an exception and exit with code 2 if it's already running
        )
    )

    cmd1 = "".join(
        (
            "-c",
            "import subprocess;",
            "import sys;",
            "from mu import app;",
            "app.setup_exception_handler();",
            "app.check_only_running_once();",
            # launch child process that will try to 'launch' the app again:
            'child2 = subprocess.run([sys.executable, "{0}"]);'.format(cmd2),
            # clean up and exit returning child process result code (which should be 2
            # if this 'already running' code is working)
            "app._shared_memory.release();",
            "exit(child2.returncode)",
        )
    )

    # Nobody answers the second launch (the first never listens), so it
    # would say so in a message box: suppressed, as nobody's there to close it.
    env = dict(os.environ, MU_SUPPRESS_CRASH_REPORT_FORM="1")
    child1 = subprocess.run([sys.executable, cmd1], env=env)
    print("child 1 return code: {}".format(child1.returncode))
    assert child1.returncode == 2


def test_running_twice_after_exception():
    """
    If we run, throw an exception and then run again we should succeed.
    """
    # call test that causes app to throw an exception by running it twice
    test_running_twice()
    # test that we can still run after exception thrown
    test_only_running_once()


def test_running_twice_after_generic_exception():
    """
    If we run and the app throws an exception, the exception handler
    should clean up shared memory sentinel and running again should succeed.
    """
    #
    # check_only_running_once() acquires shared memory block
    # raise uncaught exception to trigger exception handler
    # (subprocess should exit with exit code)
    # check to see if can run app again
    #

    # set show browser on crash suppression env for test
    os.environ["MU_SUPPRESS_CRASH_REPORT_FORM"] = "1"
    cmd1 = "".join(
        (
            "-c",
            "import os;",
            "from mu import app;",
            "print('process 1 id: {}'.format(os.getpid()));",
            "app.setup_exception_handler();",
            "app.check_only_running_once();"
            "raise RuntimeError('intentional test exception')",
            # Intentionally do not manually release shared memory here.
            # Test is testing that exception handler does this.
        )
    )

    child1 = subprocess.run([sys.executable, cmd1])
    assert child1.returncode == 1
    # confirm exception handler cleared shared memory and we can still run
    test_only_running_once()
    # clear browser launch suppression env flag
    os.environ.pop("MU_SUPPRESS_CRASH_REPORT_FORM", "")


def test_running_again_hands_over():
    """
    When Nu is already running, a second launch hands its files to it and
    exits quietly.
    """
    error = mu.app.MutexError("MUTEX: Nu is already running with pid 5", 5)
    with (
        mock.patch.object(mu.app._shared_memory, "acquire", side_effect=error),
        mock.patch("mu.app.tell_running_instance", return_value=True) as tell,
        mock.patch("mu.app.QMessageBox") as box,
        pytest.raises(SystemExit) as exit_info,
    ):
        check_only_running_once(["a.py"])
    assert exit_info.value.code == 2
    tell.assert_called_once_with(["a.py"], 5)
    box.information.assert_not_called()


def test_running_again_no_answer(monkeypatch):
    """
    If the running Nu doesn't answer, the second launch says so (rather than
    silently doing nothing) before it exits.
    """
    monkeypatch.delenv("MU_SUPPRESS_CRASH_REPORT_FORM", raising=False)
    error = mu.app.MutexError("MUTEX: Nu is already running with pid 5", 5)
    with (
        mock.patch.object(mu.app._shared_memory, "acquire", side_effect=error),
        mock.patch("mu.app.tell_running_instance", return_value=False),
        mock.patch("mu.app.QMessageBox") as box,
        pytest.raises(SystemExit),
    ):
        check_only_running_once()
    box.information.assert_called_once()
    assert "already running" in box.information.call_args[0][2]


def test_running_again_no_answer_suppressed(monkeypatch):
    monkeypatch.setenv("MU_SUPPRESS_CRASH_REPORT_FORM", "1")
    error = mu.app.MutexError("MUTEX: Nu is already running with pid 5", 5)
    with (
        mock.patch.object(mu.app._shared_memory, "acquire", side_effect=error),
        mock.patch("mu.app.tell_running_instance", return_value=False),
        mock.patch("mu.app.QMessageBox") as box,
        pytest.raises(SystemExit),
    ):
        check_only_running_once()
    box.information.assert_not_called()


def test_instance_server_name_without_user():
    with mock.patch("mu.app.getpass.getuser", side_effect=KeyError("USER")):
        name = mu.app.instance_server_name()
    assert name == mu.app._shared_memory.name + "-user-open"


def test_tell_running_instance_nobody_listening():
    """With no Nu listening, the hand-over fails (so the caller says so)."""
    assert mu.app.tell_running_instance(["a.py"]) is False


def _talk_to_server(server, script, until=lambda: False):
    """
    Run `script` in another process (as a second launch would) while this
    one handles the server's events, until it finishes and (if given)
    `until()` is true, or 10 seconds after it finishes.
    """
    from PyQt6.QtCore import QCoreApplication

    # Each test gets a fresh lock name in the environment, but this process
    # took its own at import: give the other process this one's.
    suffix = mu.app._shared_memory.name[len(mu.app.SharedMemoryMutex.NAME) :]
    env = dict(os.environ, MU_TEST_SUPPORT_RANDOM_APP_NAME_EXT=suffix)
    child = subprocess.Popen([sys.executable, "-c", script], env=env)
    deadline = time.monotonic() + 30
    while child.poll() is None and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    deadline = time.monotonic() + 10
    while True:
        QCoreApplication.processEvents()
        if until() or time.monotonic() > deadline:
            break
        time.sleep(0.01)
    return child.wait(timeout=5)


def test_listen_for_other_instances(tmp_path):
    """
    A second launch brings the running Nu's window to the front and opens
    the files it was given.
    """
    window = mock.MagicMock()
    editor = mock.MagicMock()
    server = mu.app.listen_for_other_instances(window, editor)
    try:
        assert server.isListening()
        target = str(tmp_path / "game.py")
        script = (
            "import sys; from mu import app; "
            "sys.exit(0 if app.tell_running_instance([{!r}]) else 1)"
        ).format(target)
        opened = lambda: editor.direct_load.called  # noqa: E731
        assert _talk_to_server(server, script, until=opened) == 0
    finally:
        server.close()
    window.bring_to_front.assert_called_once_with()
    editor.direct_load.assert_called_once_with(target)


def test_listen_for_other_instances_garbled():
    """A message that isn't a list of paths is ignored."""
    window = mock.MagicMock()
    editor = mock.MagicMock()
    server = mu.app.listen_for_other_instances(window, editor)
    try:
        script = (
            "from PyQt6.QtNetwork import QLocalSocket; from mu import app; "
            "s = QLocalSocket(); s.connectToServer(app.instance_server_name()); "
            "s.waitForConnected(2000); s.write(b'{nope'); "
            "s.waitForBytesWritten(2000); s.disconnectFromServer()"
        )
        # Nothing to wait for (it's ignored), so give it a moment.
        start = time.monotonic()
        waited = lambda: time.monotonic() - start > 1  # noqa: E731
        assert _talk_to_server(server, script, until=waited) == 0
    finally:
        server.close()
    window.bring_to_front.assert_not_called()
    editor.direct_load.assert_not_called()


def test_listen_for_other_instances_cannot_listen():
    with mock.patch("mu.app.QLocalServer.listen", return_value=False):
        server = mu.app.listen_for_other_instances(mock.MagicMock(), mock.MagicMock())
    assert not server.isListening()
