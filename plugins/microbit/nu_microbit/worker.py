"""
Running a flash job off Nu's GUI thread. The job (`flash.FlashJob`) blocks on
the serial port, the drive and the network, so it runs on a QThread; what it
reports comes back to the GUI thread as Qt signals.

Copyright (c) 2026 the Nu contributors (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class FlashWorker(QObject):
    """
    Runs `job` (a `flash.FlashJob`) when `run` is called, on whichever
    thread the worker lives on. Its status lines are emitted as `status`;
    then `succeeded(message)` or `failed(message, information)`, then
    `finished`.
    """

    status = pyqtSignal(str)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, job):
        super().__init__()
        self.job = job
        job.status = self.status.emit

    def run(self):
        try:
            if self.job.run():
                self.succeeded.emit(self.job.done_message)
            else:
                self.failed.emit(self.job.error.message, self.job.error.information)
        finally:
            self.finished.emit()


def start(job, on_status, on_succeeded, on_failed, on_finished):
    """
    Run `job` on a new QThread, connecting the worker's signals to the given
    callables (bound methods of a QObject on the GUI thread, so they're
    called there). Returns `(thread, worker)`; keep both referenced until
    `on_finished` is called, after the thread has stopped.
    """
    thread = QThread()
    worker = FlashWorker(job)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.status.connect(on_status)
    worker.succeeded.connect(on_succeeded)
    worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    thread.finished.connect(on_finished)
    thread.start()
    return thread, worker
