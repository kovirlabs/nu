# -*- coding: utf-8 -*-
"""
Tests for the micro:bit's files (nu_microbit.files): listing, copying each
way and deleting, against a fake board with an in-memory file system, as
the flash tests fake the board.
"""

import errno
import os

import pytest

from nu_microbit import files
from nu_microbit.flash import FlashError


class FakeRecord:
    def __init__(self, argv, note):
        self.argv = argv
        self.note = note
        self.finished = None

    def finish(self, code, output=None):
        self.finished = (code, output)


class FakeBoard:
    """A micro:bit's flat file system behind mpremote's transport API."""

    def __init__(self, port, board_files=None, fail=None, fail_on=None):
        self.port = port
        self.files = dict(board_files or {})
        self.fail = fail
        self.fail_on = fail_on
        self.calls = []
        self.closed = False

    def _maybe_fail(self, name):
        if self.fail is not None and self.fail_on == name:
            raise self.fail

    def enter_raw_repl(self, soft_reset=True):
        self.calls.append(("enter_raw_repl", soft_reset))
        self._maybe_fail("enter_raw_repl")

    def exit_raw_repl(self):
        self.calls.append(("exit_raw_repl",))
        self._maybe_fail("exit_raw_repl")

    def exec(self, code):
        self.calls.append(("exec", code))
        self._maybe_fail("exec")
        assert code == files.LIST_CODE
        listing = [(name, len(data)) for name, data in self.files.items()]
        return (repr(listing) + "\r\n").encode("utf-8")

    def fs_readfile(self, name):
        self.calls.append(("fs_readfile", name))
        self._maybe_fail("fs_readfile")
        return bytearray(self.files[name])

    def fs_writefile(self, name, data, progress_callback=None):
        self.calls.append(("fs_writefile", name))
        self._maybe_fail("fs_writefile")
        progress_callback(len(data) // 2, len(data))
        progress_callback(len(data), len(data))
        self.files[name] = bytes(data)

    def fs_rmfile(self, name):
        self.calls.append(("fs_rmfile", name))
        self._maybe_fail("fs_rmfile")
        del self.files[name]

    def close(self):
        self.closed = True
        self._maybe_fail("close")


@pytest.fixture
def board():
    return FakeBoard("COM3", {"main.py": b"print(1)\n", "data.txt": b"x" * 2000})


def make_job(board, tmp_path, action=files.LIST, port="COM3", **kwargs):
    status, records = [], []

    def log_command(argv, note):
        record = FakeRecord(argv, note)
        records.append(record)
        return record

    io = files.FilesIO(
        transport=lambda port: board,
        find_serial_port=lambda: "COM7",
    )
    job = files.FilesJob(
        action=action,
        local_dir=str(tmp_path),
        status=status.append,
        log_command=log_command,
        port=port,
        io=io,
        **kwargs,
    )
    return job, status, records


def test_list(board, tmp_path):
    job, status, records = make_job(board, tmp_path)
    assert job.run() is True
    assert job.files == [
        files.BoardFile("data.txt", 2000),
        files.BoardFile("main.py", 9),
    ]
    assert job.done_message == "Your micro:bit has 2 files."
    assert status == ["Connecting to the micro:bit…"]
    # Like mpremote: soft reset on entering the raw REPL; tidied up after.
    assert board.calls[0] == ("enter_raw_repl", True)
    assert board.calls[-1] == ("exit_raw_repl",)
    assert board.closed
    (record,) = records
    assert record.argv == ["mpremote", "connect", "COM3", "fs", "ls"]
    assert record.note == files.NOTE
    assert record.finished == (0, "   2000 data.txt\n      9 main.py")


def test_list_finds_the_port(board, tmp_path):
    job, _, records = make_job(board, tmp_path, port=None)
    assert job.run() is True
    assert job.port == "COM7"
    assert records[0].argv[2] == "COM7"


def test_no_microbit(board, tmp_path):
    job, _, records = make_job(board, tmp_path, port=None)
    job.io.find_serial_port = lambda: None
    assert job.run() is False
    assert job.error.message == "Could not find an attached BBC micro:bit."
    assert records == []


def test_get(board, tmp_path):
    job, status, records = make_job(
        board, tmp_path, action=files.GET, names=["main.py", "data.txt"]
    )
    assert job.run() is True
    assert (tmp_path / "main.py").read_bytes() == b"print(1)\n"
    assert (tmp_path / "data.txt").read_bytes() == b"x" * 2000
    assert [r.argv[4:] for r in records] == [
        ["cp", ":main.py", str(tmp_path / "main.py")],
        ["cp", ":data.txt", str(tmp_path / "data.txt")],
        ["ls"],
    ]
    assert all(r.finished[0] == 0 for r in records)
    assert job.done_message == "Copied main.py and data.txt to your computer."
    assert "Copying main.py to your computer…" in status


def test_put(board, tmp_path):
    (tmp_path / "hello.py").write_bytes(b"display.scroll('hi')\n")
    job, status, records = make_job(
        board, tmp_path, action=files.PUT, paths=[str(tmp_path / "hello.py")]
    )
    assert job.run() is True
    assert board.files["hello.py"] == b"display.scroll('hi')\n"
    assert records[0].argv[4:] == ["cp", str(tmp_path / "hello.py"), ":hello.py"]
    assert "hello.py" in [f.name for f in job.files]
    assert job.done_message == "Copied hello.py onto the micro:bit."
    assert "Copying hello.py onto the micro:bit… 100%" in status


def test_delete(board, tmp_path):
    job, _, records = make_job(
        board, tmp_path, action=files.DELETE, names=["main.py", "data.txt"]
    )
    assert job.run() is True
    assert board.files == {}
    assert [r.argv[4:] for r in records][:2] == [
        ["rm", ":main.py"],
        ["rm", ":data.txt"],
    ]
    assert job.files == []
    assert job.done_message == "Deleted main.py and data.txt from the micro:bit."


def test_board_full(board, tmp_path):
    (tmp_path / "big.py").write_bytes(b"x" * 10)
    board.fail, board.fail_on = OSError(errno.ENOSPC, "No space"), "fs_writefile"
    job, _, records = make_job(
        board, tmp_path, action=files.PUT, paths=[str(tmp_path / "big.py")]
    )
    assert job.run() is False
    assert job.error.message == "There isn't room on the micro:bit."
    assert records[0].finished[0] == 1
    assert board.closed


@pytest.mark.parametrize("fail_on", ["exec", "fs_readfile", "fs_rmfile"])
def test_board_problem(board, tmp_path, fail_on):
    board.fail, board.fail_on = RuntimeError("could not enter raw repl"), fail_on
    action = {"exec": files.LIST, "fs_readfile": files.GET, "fs_rmfile": files.DELETE}
    job, _, records = make_job(
        board, tmp_path, action=action[fail_on], names=["main.py"]
    )
    assert job.run() is False
    assert job.error.message == "Nu couldn't work with the micro:bit's files."
    assert "could not enter raw repl" in job.error.information
    assert records[-1].finished[0] == 1


def test_cant_write_on_the_computer(board, tmp_path):
    def write_file(path, data):
        raise PermissionError("read-only folder")

    job, _, _ = make_job(board, tmp_path, action=files.GET, names=["main.py"])
    job.io.write_file = write_file
    assert job.run() is False
    assert job.error.message == "Nu couldn't write that file on your computer."


def test_serial_permission(board, tmp_path):
    job, _, _ = make_job(board, tmp_path)

    def transport(port):
        raise PermissionError("Permission denied: '/dev/ttyACM0'")

    job.io.transport = transport
    assert job.run() is False
    assert "isn't allowed" in job.error.message
    assert "dialout" in job.error.information


def test_closing_problems_are_only_logged(board, tmp_path):
    board.fail, board.fail_on = OSError("gone"), "exit_raw_repl"
    job, _, _ = make_job(board, tmp_path)
    assert job.run() is True
    board.fail_on = "close"
    job, _, _ = make_job(board, tmp_path)
    assert job.run() is True


def test_cancelled_between_files(board, tmp_path):
    job, _, _ = make_job(board, tmp_path, action=files.DELETE, names=["main.py"])
    job.cancel()
    assert job.run() is False
    assert job.error.message == "Stopped."
    assert "main.py" in board.files


def test_names():
    assert files._names(["a.py"]) == "a.py"
    assert files._names(["a.py", "b.py"]) == "a.py and b.py"
    assert files._names(["a", "b", "c"]) == "3 files"


def test_local_files(tmp_path):
    (tmp_path / "b.py").write_text("")
    (tmp_path / "A.txt").write_text("")
    (tmp_path / ".hidden").write_text("")
    (tmp_path / "folder").mkdir()
    assert files.local_files(str(tmp_path)) == ["A.txt", "b.py"]
    assert files.local_files(str(tmp_path / "missing")) == []


def test_files_io_defaults(tmp_path):
    io = files.FilesIO()
    path = str(tmp_path / "x.bin")
    io.write_file(path, b"\x00\x01")
    assert io.read_file(path) == b"\x00\x01"


def test_list_code_runs_on_a_microbit_like_os(tmp_path):
    """
    LIST_CODE with micro:bit's flat os (listdir + size), and with a
    MicroPython that has os.stat and folders (which are left out).
    """
    import types

    def run(os_module):
        output = []
        exec(
            files.LIST_CODE.replace("import os\n", ""),
            {"os": os_module, "print": output.append},
        )
        return eval(output[0])

    microbit_os = types.SimpleNamespace(
        listdir=lambda: ["main.py", "log.txt"],
        size=lambda name: {"main.py": 12, "log.txt": 40}[name],
    )
    assert run(microbit_os) == [("main.py", 12), ("log.txt", 40)]

    def stat(name):
        if name == "lib":
            return (0x4000, 0, 0, 0, 0, 0, 0)
        return (0x8000, 0, 0, 0, 0, 0, 7)

    other_os = types.SimpleNamespace(listdir=lambda: ["boot.py", "lib"], stat=stat)
    assert run(other_os) == [("boot.py", 7)]


def test_flash_error_is_shared():
    """Flash and Files report problems the same way."""
    assert files.FlashError is FlashError
    assert os.path.basename(files.__file__) == "files.py"
