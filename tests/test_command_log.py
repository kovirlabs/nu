"""
Tests for the GUI-free log of the commands Nu runs for the learner
(mu/command_log.py).
"""

import datetime
import logging
import threading
from unittest import mock

import pytest

from mu import command_log as CL


UV = "/opt/nu/app_packages/bin/uv"


@pytest.fixture
def log():
    return CL.CommandLog(max_records=3)


#
# quote_command / program_name
#
def test_quote_command_posix():
    argv = ["uv", "run", "--script", "/home/a b/hello.py"]
    assert CL.quote_command(argv, windows=False) == (
        "uv run --script '/home/a b/hello.py'"
    )


def test_quote_command_windows():
    argv = ["uv", "run", "--script", r"C:\Users\a b\hello.py"]
    assert CL.quote_command(argv, windows=True) == (
        r'uv run --script "C:\Users\a b\hello.py"'
    )


def test_quote_command_defaults_to_this_platform():
    with mock.patch.object(CL.sys, "platform", "win32"):
        assert CL.quote_command(["a b"]) == '"a b"'
    with mock.patch.object(CL.sys, "platform", "linux"):
        assert CL.quote_command(["a b"]) == "'a b'"


@pytest.mark.parametrize(
    "path, name",
    [
        ("/opt/nu/bin/uv", "uv"),
        (r"C:\Program Files\Nu\uv.exe", "uv"),
        (r"C:\Program Files\Nu\UV.EXE", "UV"),
        ("uv", "uv"),
    ],
)
def test_program_name(path, name):
    assert CL.program_name(path) == name


#
# CommandRecord
#
def test_record_display_shows_uv_as_typed(log):
    """The learner sees `uv …`, not the absolute path of Nu's own copy."""
    record = log.start([UV, "pip", "install", "cowsay"])
    assert record.display(windows=False) == "uv pip install cowsay"
    assert record.full_command(windows=False) == UV + " pip install cowsay"
    assert record.program == UV


def test_record_display_quotes_arguments(log):
    record = log.start([UV, "run", "--script", "/home/a b/hello.py"])
    assert record.display(windows=False) == "uv run --script '/home/a b/hello.py'"


def test_record_starts_running(log):
    before = datetime.datetime.now()
    record = log.start([UV, "--version"], cwd="/work", note="A note.")
    assert record.argv == [UV, "--version"]
    assert record.cwd == "/work"
    assert record.note == "A note."
    assert record.exit_code is None
    assert record.finished is False
    assert record.output_tail() == []
    assert before <= record.started <= datetime.datetime.now()


def test_record_argv_is_a_copy(log):
    argv = [UV, "venv"]
    record = log.start(argv)
    argv.append("changed")
    assert record.argv == [UV, "venv"]


def test_record_finish_with_output(log):
    record = log.start([UV, "pip", "list"])
    record.finish(0, "line one\n\n  line two  \n")
    assert record.finished is True
    assert record.exit_code == 0
    assert record.output_tail() == ["line one", "  line two"]


def test_record_add_output_keeps_a_bounded_tail(log):
    record = log.start([UV, "pip", "install", "x"])
    for i in range(CL.TAIL_LINES + 5):
        record.add_output("line %d" % i)
    tail = record.output_tail()
    assert len(tail) == CL.TAIL_LINES
    assert tail[-1] == "line %d" % (CL.TAIL_LINES + 4)
    assert tail[0] == "line 5"


def test_record_add_output_splits_lines_and_truncates(log):
    record = log.start([UV, "pip", "list"])
    record.add_output("a\r\nb\n" + "x" * (CL.MAX_LINE_LENGTH + 10))
    tail = record.output_tail()
    assert tail[:2] == ["a", "b"]
    assert len(tail[2]) == CL.MAX_LINE_LENGTH + 1
    assert tail[2].endswith("…")


def test_record_finish_twice_keeps_first(log):
    record = log.start([UV, "venv"])
    record.finish(0)
    record.finish(3, "late")
    assert record.exit_code == 0
    assert record.output_tail() == []


def test_record_finish_without_exit_code(log):
    """A process that couldn't report an exit code still counts as finished."""
    record = log.start([UV, "venv"])
    record.finish(None)
    assert record.finished is True
    assert record.exit_code is None


def test_record_status_text(log):
    record = log.start([UV, "venv"])
    assert record.status() == "still running"
    record.finish(0)
    assert record.status() == "finished OK (exit code 0)"
    failed = log.start([UV, "venv"])
    failed.finish(2)
    assert failed.status() == "failed (exit code 2)"
    unknown = log.start([UV, "venv"])
    unknown.finish(None)
    assert unknown.status() == "finished"


#
# CommandLog
#
def test_log_is_bounded_oldest_first(log):
    records = [log.start([UV, str(i)]) for i in range(5)]
    assert log.records() == records[2:]


def test_log_clear(log):
    log.start([UV, "venv"])
    log.clear()
    assert log.records() == []


def test_log_start_and_finish_go_to_the_log_file(log, caplog):
    caplog.set_level(logging.INFO, logger="mu.command_log")
    record = log.start([UV, "pip", "install", "cowsay"], cwd="/work")
    record.finish(1, "error: nope")
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "uv pip install cowsay" in m and UV in m and "/work" in m for m in messages
    )
    assert any("exit code 1" in m and "error: nope" in m for m in messages)
    assert all(r.levelno == logging.INFO for r in caplog.records)


def test_log_render_empty(log):
    assert log.render() == "Nu hasn't run any uv commands yet."


def test_log_render(log):
    first = log.start([UV, "pip", "install", "cowsay"], cwd="/work")
    first.started = datetime.datetime(2026, 11, 8, 14, 2, 31)
    first.finish(0, "Installed 1 package")
    second = log.start([UV, "run", "--script", "/w/hello.py"], note="In the pane.")
    second.started = datetime.datetime(2026, 11, 8, 14, 3, 0)
    with mock.patch.object(CL.sys, "platform", "linux"):
        text = log.render()
    assert text == (
        "$ uv pip install cowsay\n"
        "  14:02:31 · in /work · finished OK (exit code 0)\n"
        "  | Installed 1 package\n"
        "\n"
        "$ uv run --script /w/hello.py\n"
        "  14:03:00 · still running\n"
        "  In the pane."
    )


def test_log_is_thread_safe(log):
    """Records can be started from the venv-creation worker thread."""
    big = CL.CommandLog(max_records=1000)

    def worker():
        for _ in range(100):
            big.start([UV, "venv"]).finish(0, "ok")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(big.records()) == 400


def test_module_singleton():
    assert isinstance(CL.command_log, CL.CommandLog)
