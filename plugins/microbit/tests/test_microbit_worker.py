# -*- coding: utf-8 -*-
"""
Tests for nu_microbit.worker: a flash job runs on its own thread and reports
back to the GUI thread through signals.
"""

import threading
import time

from PyQt6.QtCore import QCoreApplication, QObject

from nu_microbit import worker
from nu_microbit.flash import FlashError


class FakeJob:
    def __init__(self, ok=True, statuses=("one", "two")):
        self.ok = ok
        self.statuses = statuses
        self.status = None
        self.done_message = "Done!"
        self.error = FlashError("Broken.", "Because.")
        self.thread = None

    def run(self):
        self.thread = threading.current_thread()
        for text in self.statuses:
            self.status(text)
        return self.ok


def test_run_succeeds():
    job = FakeJob()
    flash_worker = worker.FlashWorker(job)
    seen = []
    flash_worker.status.connect(lambda t: seen.append(("status", t)))
    flash_worker.succeeded.connect(lambda m: seen.append(("ok", m)))
    flash_worker.failed.connect(lambda m, i: seen.append(("failed", m, i)))
    flash_worker.finished.connect(lambda: seen.append(("finished",)))
    flash_worker.run()
    assert seen == [
        ("status", "one"),
        ("status", "two"),
        ("ok", "Done!"),
        ("finished",),
    ]


def test_run_fails():
    flash_worker = worker.FlashWorker(FakeJob(ok=False, statuses=()))
    seen = []
    flash_worker.failed.connect(lambda m, i: seen.append((m, i)))
    flash_worker.finished.connect(lambda: seen.append("finished"))
    flash_worker.run()
    assert seen == [("Broken.", "Because."), "finished"]


def test_run_finishes_even_if_the_job_raises():
    job = FakeJob()
    job.run = lambda: 1 / 0
    flash_worker = worker.FlashWorker(job)
    seen = []
    flash_worker.finished.connect(lambda: seen.append("finished"))
    try:
        flash_worker.run()
    except ZeroDivisionError:
        pass
    assert seen == ["finished"]


class Receiver(QObject):
    """Lives on the GUI thread, like the mode."""

    def __init__(self):
        super().__init__()
        self.seen = []
        self.threads = set()

    def _note(self, *item):
        self.threads.add(threading.current_thread())
        self.seen.append(item)

    def on_status(self, text):
        self._note("status", text)

    def on_succeeded(self, message):
        self._note("ok", message)

    def on_failed(self, message, information):
        self._note("failed", message)

    def on_finished(self):
        self._note("finished")


def test_start_runs_the_job_on_another_thread_and_reports_on_this_one():
    receiver = Receiver()
    job = FakeJob()
    thread, flash_worker = worker.start(
        job,
        receiver.on_status,
        receiver.on_succeeded,
        receiver.on_failed,
        receiver.on_finished,
    )
    # Pump events by hand: a QEventLoop can return at once if an earlier
    # test asked the application to quit.
    deadline = time.monotonic() + 5
    while ("finished",) not in receiver.seen and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert thread.wait(2000)
    assert receiver.seen == [
        ("status", "one"),
        ("status", "two"),
        ("ok", "Done!"),
        ("finished",),
    ]
    assert job.thread is not threading.main_thread()
    assert receiver.threads == {threading.main_thread()}
    assert thread.isFinished()
