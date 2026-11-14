# -*- coding: utf-8 -*-
"""
Tests for the micro:bit Files pane (the widget) and how the mode drives it:
opening and closing it, the jobs it starts, and the questions it asks.
"""

import os
from unittest import mock

import pytest

from PyQt6.QtCore import QItemSelectionModel

from nu_microbit import MicrobitMode, files
from nu_microbit.files import BoardFile
from nu_microbit.files_pane import FilesPane, _size

from test_microbit_files import FakeBoard
from test_microbit_plugin import wait_until


@pytest.fixture
def folder(tmp_path):
    folder = tmp_path / "mu_code" / "microbit"
    folder.mkdir(parents=True)
    (folder / "hello.py").write_text("print('hi')\n")
    (folder / "game.py").write_text("")
    return folder


@pytest.fixture
def pane(folder):
    return FilesPane(str(folder))


def select(widget, *rows):
    widget.clearSelection()
    for row in rows:
        widget.setCurrentRow(row, QItemSelectionModel.SelectionFlag.Select)


# --- the widget ---


def test_size():
    assert _size(120) == "120 bytes"
    assert _size(3482) == "3.4 KB"


def test_lists_the_local_folder(pane, folder):
    items = [pane.local_list.item(i) for i in range(pane.local_list.count())]
    assert [i.text() for i in items] == ["game.py", "hello.py"]
    assert items[1].data(256) == os.path.join(str(folder), "hello.py")
    assert pane.local_label.toolTip() == str(folder)
    # Nothing selected: only Refresh works.
    assert not pane.get_button.isEnabled()
    assert not pane.put_button.isEnabled()
    assert not pane.delete_button.isEnabled()
    assert not pane.open_button.isEnabled()
    assert pane.refresh_button.isEnabled()


def test_shows_the_board_files(pane):
    assert pane.board_files is None
    pane.show_board_files([BoardFile("main.py", 12), BoardFile("log.txt", 2048)])
    assert pane.board_files == [BoardFile("main.py", 12), BoardFile("log.txt", 2048)]
    assert pane.board_list.item(1).toolTip() == "2.0 KB"
    assert pane.board_label.text() == "On your micro:bit"
    pane.show_board_files([])
    assert pane.board_label.text() == "On your micro:bit (no files)"


def test_buttons_follow_the_selection(pane):
    pane.show_board_files([BoardFile("main.py", 12)])
    select(pane.board_list, 0)
    assert pane.get_button.isEnabled() and pane.delete_button.isEnabled()
    assert not pane.put_button.isEnabled()
    select(pane.local_list, 0)
    assert pane.put_button.isEnabled() and pane.open_button.isEnabled()
    pane.set_busy(True, "Talking…")
    assert pane.message.text() == "Talking…"
    assert not pane.get_button.isEnabled()
    assert not pane.put_button.isEnabled()
    assert not pane.refresh_button.isEnabled()
    assert pane.open_button.isEnabled()  # opening a local file needs no board
    pane.set_busy(False)
    assert pane.get_button.isEnabled()
    assert pane.message.text() == "Talking…"


def test_requests(pane, folder):
    pane.show_board_files([BoardFile("a.py", 1), BoardFile("b.py", 1)])
    got, put, deleted, opened, refreshed = [], [], [], [], []
    pane.get_requested.connect(got.append)
    pane.put_requested.connect(put.append)
    pane.delete_requested.connect(deleted.append)
    pane.open_requested.connect(opened.append)
    pane.refresh_requested.connect(lambda: refreshed.append(True))
    select(pane.board_list, 0, 1)
    pane.get_button.click()
    pane.delete_button.click()
    select(pane.local_list, 1)
    pane.put_button.click()
    pane.open_button.click()
    pane.refresh_button.click()
    assert got == [["a.py", "b.py"]]
    assert deleted == [["a.py", "b.py"]]
    hello = os.path.join(str(folder), "hello.py")
    assert put == [[hello]]
    assert opened == [hello]
    assert refreshed == [True]
    # Double-clicking: a board file is copied, a local one opened.
    pane.board_list.itemDoubleClicked.emit(pane.board_list.item(0))
    pane.local_list.itemDoubleClicked.emit(pane.local_list.item(1))
    assert got[-1] == ["a.py", "b.py"]  # the selection
    assert opened[-1] == hello


def test_no_requests_while_busy(pane):
    pane.show_board_files([BoardFile("a.py", 1)])
    select(pane.board_list, 0)
    select(pane.local_list, 0)
    asked = []
    for signal in (pane.get_requested, pane.put_requested, pane.delete_requested):
        signal.connect(asked.append)
    pane.refresh_requested.connect(lambda: asked.append("refresh"))
    pane.set_busy(True)
    pane.get_selected()
    pane.put_selected()
    pane.delete_selected()
    pane.refresh()
    assert asked == []


def test_refresh_rereads_the_folder(pane, folder):
    (folder / "new.py").write_text("")
    pane.refresh()
    assert "new.py" in [
        pane.local_list.item(i).text() for i in range(pane.local_list.count())
    ]


# --- the mode ---


@pytest.fixture
def host(tmp_path):
    host = mock.MagicMock()
    host.workspace_dir.return_value = str(tmp_path / "mu_code")
    host.current_device = None
    host.confirm.return_value = True
    return host


@pytest.fixture
def mm(host, folder):
    mode = MicrobitMode(mock.MagicMock(), mock.MagicMock())
    mode.host = host
    mode.view.button_bar.slots = {}
    mode.active = True
    return mode


@pytest.fixture
def started(mm):
    """Patch the worker so jobs are handed over without a thread."""
    with mock.patch("nu_microbit.mode.worker.start") as start:
        start.return_value = (mock.MagicMock(), mock.MagicMock())
        yield start


def test_open_files_lists_the_board(mm, host, started):
    mm.repl = True
    mm.plotter = True
    mm.connection = mock.MagicMock()
    mm.set_buttons = mock.MagicMock()
    mm.toggle_files()
    pane = mm.files_pane
    assert isinstance(pane, FilesPane)
    host.add_pane.assert_called_once_with(pane, "micro:bit Files")
    assert mm.files_handle is host.add_pane.return_value
    # The REPL and plotter let go of the port, and stay off.
    assert (mm.repl, mm.plotter) == (False, False)
    host.show_status.assert_called_once_with(
        "Closed the REPL so Nu can use the micro:bit's connection."
    )
    mm.set_buttons.assert_any_call(repl=False, plotter=False)
    job = started.call_args[0][0]
    assert isinstance(job, files.FilesJob)
    assert job.action == files.LIST
    assert job.local_dir == mm.workspace_dir()
    assert job.log_command is host.log_command
    assert pane.busy
    assert started.call_args[0][1:] == (
        mm.on_files_status,
        mm.on_files_succeeded,
        mm.on_files_failed,
        mm.on_files_finished,
    )


def test_close_files(mm, host, started):
    mm.set_buttons = mock.MagicMock()
    mm.toggle_files()
    handle = mm.files_handle
    mm.on_files_finished()
    mm.toggle_files()
    host.remove_pane.assert_called_once_with(handle)
    assert mm.files_pane is None and mm.files_handle is None
    mm.set_buttons.assert_called_with(repl=True, plotter=True)


def test_open_files_while_busy(mm, host, started):
    mm.flash_thread = mock.MagicMock()
    mm.open_files()
    assert mm.files_pane is None
    host.show_status.assert_called_once_with("Nu is busy with the micro:bit…")
    started.assert_not_called()


def test_open_files_twice(mm, host, started):
    mm.open_files()
    mm.open_files()
    host.add_pane.assert_called_once()


def test_job_uses_the_selected_microbit(mm, host, started):
    from mu.plugin import Device

    host.current_device = Device(
        0x0D28, 0x0204, "COM3", "99040001", "ARM", "BBC micro:bit", "microbit"
    )
    mm.open_files()
    assert started.call_args[0][0].port == "COM3"


def test_files_reports(mm, host, started):
    mm.open_files()
    pane = mm.files_pane
    mm.on_files_status("Connecting…")
    assert pane.message.text() == "Connecting…"
    mm.files_job.files = [BoardFile("main.py", 3)]
    mm.on_files_succeeded("Your micro:bit has 1 files.")
    assert pane.board_files == [BoardFile("main.py", 3)]
    assert pane.message.text().startswith("Your micro:bit has 1 files.")
    assert "reset button" in pane.message.text()
    mm.on_files_failed("Broken.", "Because.")
    assert pane.message.text() == "Broken."
    host.show_message.assert_called_once_with("Broken.", "Because.")
    mm.set_buttons = mock.MagicMock()
    mm.on_files_finished()
    assert not pane.busy
    assert mm.files_thread is None and mm.files_job is None
    mm.set_buttons.assert_called_once_with(
        **{"microbit-flash": True, "microbit-files": True}
    )


def test_files_reports_after_the_pane_closed(mm, host):
    mm.on_files_succeeded("x")
    mm.on_files_failed("Broken.", "Because.")
    host.show_message.assert_called_once_with("Broken.", "Because.")
    mm.active = False
    mm.set_buttons = mock.MagicMock()
    mm.on_files_finished()
    mm.set_buttons.assert_not_called()


def test_copy_to_computer_asks_before_replacing(mm, host, started, folder):
    mm.open_files()
    started.reset_mock()
    mm.on_files_finished()
    host.confirm.return_value = False
    mm.copy_to_computer(["hello.py"])
    assert "Replace hello.py on your computer?" == host.confirm.call_args[0][0]
    started.assert_not_called()
    host.confirm.return_value = True
    mm.copy_to_computer(["hello.py", "new.py"])
    job = started.call_args[0][0]
    assert (job.action, job.names) == (files.GET, ["hello.py", "new.py"])


def test_copy_to_microbit_asks_before_replacing(mm, host, started, folder):
    mm.open_files()
    mm.on_files_finished()
    mm.files_pane.show_board_files([BoardFile("hello.py", 3)])
    started.reset_mock()
    host.confirm.reset_mock()
    path = str(folder / "game.py")
    mm.copy_to_microbit([path])
    host.confirm.assert_not_called()
    assert started.call_args[0][0].paths == [path]
    mm.on_files_finished()
    host.confirm.return_value = False
    mm.copy_to_microbit([str(folder / "hello.py")])
    assert host.confirm.call_args[0][0] == "Replace hello.py on the micro:bit?"


def test_delete_asks_first(mm, host, started):
    mm.open_files()
    mm.on_files_finished()
    started.reset_mock()
    host.confirm.return_value = False
    mm.delete_from_microbit(["main.py"])
    assert "Delete main.py from the micro:bit?" == host.confirm.call_args[0][0]
    started.assert_not_called()
    host.confirm.return_value = True
    mm.delete_from_microbit(["main.py"])
    assert started.call_args[0][0].action == files.DELETE


def test_one_job_at_a_time(mm, host, started):
    mm.files_thread = mock.MagicMock()
    mm.run_files_job(files.LIST)
    started.assert_not_called()
    host.show_status.assert_called_with("Nu is busy with the micro:bit…")
    mm.flash()
    host.show_status.assert_called_with("Nu is busy with the micro:bit's files…")


def test_flash_refreshes_an_open_files_pane(mm, host, started):
    mm.open_files()
    mm.on_files_finished()
    started.reset_mock()
    mm.shift_held = mock.MagicMock(return_value=False)
    host.current_text.return_value = "print(1)\n"
    host.current_path.return_value = None
    host.data_dir.return_value = "/data/microbit"
    mm.flash()
    assert mm.files_pane.busy
    assert mm.files_pane.message.text() == "Flashing…"
    mm.set_buttons = mock.MagicMock()
    mm.on_flash_finished()
    # The REPL and plotter stay off; the pane lists the board again.
    mm.set_buttons.assert_any_call(**{"microbit-flash": True, "microbit-files": True})
    for call in mm.set_buttons.call_args_list:
        assert "repl" not in call.kwargs
    assert started.call_args[0][0].action == files.LIST


def test_open_a_local_file(mm, host, started, folder):
    mm.open_files()
    mm.files_pane.open_requested.emit(str(folder / "hello.py"))
    host.open_file.assert_called_once_with(str(folder / "hello.py"))


def test_deactivate_forgets_the_pane(mm, started):
    mm.open_files()
    mm.deactivate()
    assert mm.files_pane is None and mm.files_handle is None


def test_stop_cancels_a_files_job(mm):
    job, thread = mock.MagicMock(), mock.MagicMock()
    mm.files_job, mm.files_thread = job, thread
    mm.stop()
    job.cancel.assert_called_once_with()
    thread.quit.assert_called_once_with()


def test_files_io_is_the_real_one(mm):
    assert mm.files_io().transport is files.mpremote_transport


def test_files_end_to_end_on_a_worker_thread(mm, host, folder):
    """The real worker thread and job, with a fake board: the pane fills in."""
    board = FakeBoard("COM3", {"main.py": b"print(1)\n"})
    mm.files_io = lambda: files.FilesIO(
        transport=lambda port: board, find_serial_port=lambda: "COM3"
    )
    mm.set_buttons = mock.MagicMock()
    mm.open_files()
    assert wait_until(lambda: mm.files_thread is None)
    assert mm.files_pane.board_files == [BoardFile("main.py", 9)]
    assert not mm.files_pane.busy
    # Copy main.py to the computer, through the pane's button.
    select(mm.files_pane.board_list, 0)
    mm.files_pane.get_button.click()
    assert wait_until(lambda: mm.files_thread is None)
    assert (folder / "main.py").read_bytes() == b"print(1)\n"
    assert "main.py" in [
        mm.files_pane.local_list.item(i).text()
        for i in range(mm.files_pane.local_list.count())
    ]
