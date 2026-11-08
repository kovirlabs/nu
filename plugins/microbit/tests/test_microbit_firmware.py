# -*- coding: utf-8 -*-
"""
Tests for nu_microbit.firmware: the pinned MicroPython releases and getting a
checked copy of one. Downloads are faked (a fake `urlopen`, and one real
download from a local HTTP server); nothing here touches the internet.
"""

import hashlib
import http.server
import os
import threading
import urllib.error
from unittest import mock

import pytest

from nu_microbit import firmware

CONTENT = b":10000000FAKEHEX\n" * 1000


def fake_firmware(content=CONTENT, url="https://example.org/dl/micropython-x.hex"):
    return firmware.Firmware(
        board_version=2,
        version="2.9.9",
        url=url,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


class FakeResponse:
    def __init__(self, content, headers=None, fail_after=None):
        self.content = content
        self.headers = headers if headers is not None else {}
        self.position = 0
        self.fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        if self.fail_after is not None and self.position >= self.fail_after:
            raise TimeoutError("timed out")
        chunk = self.content[self.position : self.position + size]
        self.position += len(chunk)
        return chunk


def test_pins_are_the_official_releases():
    """
    V1 from bbcmicrobit/micropython, V2 from the Micro:bit Educational
    Foundation's repository, each with a SHA-256 to check the download.
    """
    v1, v2 = firmware.FIRMWARE[1], firmware.FIRMWARE[2]
    assert v1.url.startswith("https://github.com/bbcmicrobit/micropython/releases/")
    assert v2.url.startswith(
        "https://github.com/microbit-foundation/micropython-microbit-v2/releases/"
    )
    assert (v1.version, v2.version) == ("1.1.1", "2.1.2")
    assert v1.filename == "micropython-microbit-v1.1.1.hex"
    assert v2.filename == "micropython-microbit-v2.1.2.hex"
    for pin in (v1, v2):
        assert len(pin.sha256) == 64
        assert pin.version in pin.url
        assert pin.size > 100_000


def test_nothing_vendored():
    """The firmware is fetched, never shipped in the package."""
    if os.path.isdir(firmware.BUNDLED_DIR):  # pragma: no cover (installers)
        assert not [n for n in os.listdir(firmware.BUNDLED_DIR) if n.endswith(".hex")]


def test_local_copy_cached(tmp_path):
    pin = fake_firmware()
    (tmp_path / pin.filename).write_bytes(CONTENT)
    assert firmware.local_copy(pin, str(tmp_path)) == str(tmp_path / pin.filename)


def test_local_copy_bad_cache_is_removed(tmp_path):
    pin = fake_firmware()
    (tmp_path / pin.filename).write_bytes(b"truncated")
    assert firmware.local_copy(pin, str(tmp_path)) is None
    assert not (tmp_path / pin.filename).exists()


def test_local_copy_bad_cache_that_cant_be_removed(tmp_path):
    pin = fake_firmware()
    (tmp_path / pin.filename).write_bytes(b"truncated")
    with mock.patch("nu_microbit.firmware.os.remove", side_effect=OSError):
        assert firmware.local_copy(pin, str(tmp_path)) is None


def test_local_copy_bundled(tmp_path, monkeypatch):
    """An installer can ship the files in the package's firmware folder."""
    pin = fake_firmware()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / pin.filename).write_bytes(CONTENT)
    monkeypatch.setattr(firmware, "BUNDLED_DIR", str(bundled))
    cache = tmp_path / "cache"
    assert firmware.local_copy(pin, str(cache)) == str(bundled / pin.filename)


def test_local_copy_none(tmp_path):
    assert firmware.local_copy(fake_firmware(), str(tmp_path)) is None


def test_download(tmp_path):
    pin = fake_firmware()
    seen = []
    urlopen = mock.MagicMock(
        return_value=FakeResponse(CONTENT, {"Content-Length": str(len(CONTENT))})
    )
    path = firmware.download(
        pin,
        str(tmp_path / "cache"),
        progress=lambda d, t: seen.append((d, t)),
        urlopen=urlopen,
    )
    assert path == str(tmp_path / "cache" / pin.filename)
    with open(path, "rb") as f:
        assert f.read() == CONTENT
    assert not os.path.exists(path + ".part")
    urlopen.assert_called_once_with(pin.url, timeout=firmware.DOWNLOAD_TIMEOUT)
    assert seen[-1] == (len(CONTENT), len(CONTENT))
    assert [d for d, _ in seen] == sorted(d for d, _ in seen)


def test_download_without_content_length_uses_the_pinned_size(tmp_path):
    pin = fake_firmware()
    seen = []
    firmware.download(
        pin,
        str(tmp_path),
        progress=lambda d, t: seen.append(t),
        urlopen=lambda url, timeout: FakeResponse(CONTENT),
    )
    assert set(seen) == {pin.size}


def test_download_wrong_checksum(tmp_path):
    pin = fake_firmware()
    with pytest.raises(firmware.FirmwareUnavailable) as ex:
        firmware.download(
            pin, str(tmp_path), urlopen=lambda url, timeout: FakeResponse(b"evil")
        )
    assert "isn't the right file" in ex.value.message
    assert pin.url in ex.value.information
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("no network"), TimeoutError("slow"), OSError("disk")],
)
def test_download_offline(tmp_path, error):
    """
    Offline, the learner is told which file to get, from where, and which
    folder to put it in.
    """
    pin = fake_firmware()

    def urlopen(url, timeout):
        raise error

    with pytest.raises(firmware.FirmwareUnavailable) as ex:
        firmware.download(pin, str(tmp_path), urlopen=urlopen)
    assert "V2" in ex.value.message
    for text in (pin.filename, pin.url, str(tmp_path)):
        assert text in ex.value.information


def test_download_interrupted_leaves_nothing(tmp_path):
    pin = fake_firmware()
    with pytest.raises(firmware.FirmwareUnavailable):
        firmware.download(
            pin,
            str(tmp_path),
            urlopen=lambda url, timeout: FakeResponse(CONTENT, fail_after=1),
        )
    assert os.listdir(tmp_path) == []


def test_download_cancelled(tmp_path):
    pin = fake_firmware()
    with pytest.raises(firmware.FirmwareUnavailable) as ex:
        firmware.download(
            pin,
            str(tmp_path),
            urlopen=lambda url, timeout: FakeResponse(CONTENT),
            cancelled=lambda: True,
        )
    assert ex.value.message == "Stopped."
    assert os.listdir(tmp_path) == []


def test_download_from_a_real_http_server(tmp_path):
    """
    The real urllib path, against a local HTTP server: the bytes arrive, are
    checked and kept.
    """
    served = tmp_path / "served"
    served.mkdir()
    (served / "micropython-x.hex").write_bytes(CONTENT)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(served), **kwargs)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:{}/micropython-x.hex".format(server.server_port)
        path = firmware.download(fake_firmware(url=url), str(tmp_path / "cache"))
    finally:
        server.shutdown()
        server.server_close()
    with open(path, "rb") as f:
        assert f.read() == CONTENT
