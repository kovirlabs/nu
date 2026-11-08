"""
MicroPython for the micro:bit: which release Nu uses, and getting a checked
copy of it. GUI-free (it runs on the flash worker's thread).

Nu never vendors the firmware (shipping a frozen copy is what got the old
micro:bit mode dropped). Each board version's official release is pinned
here by URL and SHA-256; the first time it's needed it's downloaded into
Nu's data folder and checked, and after that the checked copy is used, so
Flash works offline from then on. An installer can bundle the files in this
package's `firmware/` folder instead (Phase 6c).

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

import hashlib
import logging
import os
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: Where an installer may bundle the firmware files (empty in a checkout).
BUNDLED_DIR = os.path.join(os.path.dirname(__file__), "firmware")
#: Seconds to wait for the download server.
DOWNLOAD_TIMEOUT = 30
CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class Firmware:
    """One pinned MicroPython release for one micro:bit version."""

    board_version: int
    version: str
    url: str
    sha256: str
    size: int

    @property
    def filename(self):
        return self.url.rsplit("/", 1)[-1]


#: The pinned releases (checked 2026-11; see TODO.md Phase 6a to update them).
#: V2: v2.1.2 is the newest release (GitHub's "latest" badge was left on
#: v2.1.1; 2.1.2 only improves `neopixel`).
FIRMWARE = {
    1: Firmware(
        board_version=1,
        version="1.1.1",
        url=(
            "https://github.com/bbcmicrobit/micropython/releases/download/"
            "v1.1.1/micropython-microbit-v1.1.1.hex"
        ),
        sha256="d3686e669677d456ece9d206a44b8acbe73ddf73e1a3211ff89b93972b953152",
        size=635792,
    ),
    2: Firmware(
        board_version=2,
        version="2.1.2",
        url=(
            "https://github.com/microbit-foundation/micropython-microbit-v2/"
            "releases/download/v2.1.2/micropython-microbit-v2.1.2.hex"
        ),
        sha256="66fae07b71777e9e3a6b5122a27930b24cc0be5002ab9a67e92494c54a1645ef",
        size=1239726,
    ),
}


class FirmwareUnavailable(Exception):
    """
    Nu can't get a good copy of the firmware. `message` and `information`
    are for the learner.
    """

    def __init__(self, message, information=""):
        super().__init__(message)
        self.message = message
        self.information = information


def sha256_of(path):
    """The SHA-256 of the file at `path`, as hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as hex_file:
        for chunk in iter(lambda: hex_file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_good_copy(path, firmware):
    """True if `path` is a file whose contents are exactly `firmware`'s."""
    try:
        return sha256_of(path) == firmware.sha256
    except OSError:
        return False


def local_copy(firmware, cache_dir):
    """
    The path of a checked copy of `firmware` already on this computer (in
    `cache_dir`, then bundled with Nu), or None. A cached copy that fails the
    check is deleted, so it's downloaded again.
    """
    cached = os.path.join(cache_dir, firmware.filename)
    if os.path.exists(cached):
        if is_good_copy(cached, firmware):
            return cached
        logger.warning("Removing %s: its SHA-256 doesn't match the pin", cached)
        try:
            os.remove(cached)
        except OSError:
            logger.exception("Couldn't remove %s", cached)
    bundled = os.path.join(BUNDLED_DIR, firmware.filename)
    if is_good_copy(bundled, firmware):
        return bundled
    return None


def offline_help(firmware, cache_dir, error):
    """The learner-facing problem when the firmware can't be downloaded."""
    return FirmwareUnavailable(
        _("Nu couldn't download MicroPython for the micro:bit V{}.").format(
            firmware.board_version
        ),
        _(
            "To put MicroPython on your micro:bit, Nu needs the file {file}, "
            "and it couldn't download it ({error}).\n\n"
            "If this computer isn't on the internet, download the file on "
            "one that is, from:\n{url}\n\n"
            "then copy it into this folder and press Flash again:\n{folder}"
        ).format(
            file=firmware.filename,
            error=error,
            url=firmware.url,
            folder=cache_dir,
        ),
    )


def download(firmware, cache_dir, progress=None, urlopen=None, cancelled=None):
    """
    Download `firmware` into `cache_dir`, check its SHA-256 and return its
    path. `progress(done, total)` is called as bytes arrive; `cancelled()`
    returning True stops it. Raises `FirmwareUnavailable` if it can't.
    """
    urlopen = urlopen or urllib.request.urlopen
    os.makedirs(cache_dir, exist_ok=True)
    final = os.path.join(cache_dir, firmware.filename)
    partial = final + ".part"
    try:
        with urlopen(firmware.url, timeout=DOWNLOAD_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length") or firmware.size)
            done = 0
            with open(partial, "wb") as out:
                while True:
                    if cancelled and cancelled():
                        raise FirmwareUnavailable(_("Stopped."))
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except FirmwareUnavailable:
        _remove(partial)
        raise
    except Exception as ex:  # URLError, timeouts, a full disk...
        logger.warning("Downloading %s failed: %r", firmware.url, ex)
        _remove(partial)
        raise offline_help(firmware, cache_dir, ex) from ex
    if not is_good_copy(partial, firmware):
        _remove(partial)
        raise FirmwareUnavailable(
            _("The MicroPython Nu downloaded isn't the right file."),
            _(
                "Its checksum doesn't match the one Nu expects, so Nu won't "
                "put it on your micro:bit. Try again later; if it keeps "
                "happening, the download may have been changed or "
                "intercepted. The file is:\n{}"
            ).format(firmware.url),
        )
    os.replace(partial, final)
    return final


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
