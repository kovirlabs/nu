#
# Download wheels corresponding to the baseline modes
#
import os
import sys
import glob
import logging
import json
import platform
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile

from .. import __version__ as mu_version


class WheelsError(Exception):
    def __init__(self, message):
        self.message = message


class WheelsDownloadError(WheelsError):
    pass


class WheelsBuildError(WheelsError):
    pass


logger = logging.getLogger(__name__)

WHEELS_DIRPATH = os.path.dirname(__file__)
ZIP_FILEPATH = os.path.join(WHEELS_DIRPATH, mu_version + ".zip")
#
# The bundled CPython for the learner's environment (see `download_python`):
# a python-build-standalone "install_only" archive plus a pip wheel to seed the
# venv with. Kept in a subdirectory so `remove_dist_files` (which clears
# top-level *.gz/*.whl) leaves it alone.
#
PYTHON_DIRPATH = os.path.join(WHEELS_DIRPATH, "python")

#
# List of base packages to support modes
# The first element should be the importable name (so "serial" rather than "pyserial")
# The second element is passed to `pip download|install`
# Any additional elements are passed to `pip` for specific purposes
#
mode_packages = [
    # pygame backs pgzero. The old `pygame<2.1.3` cap was a macOS 10.x
    # workaround (mu-editor/mu#2423); it's obsolete now that we target
    # macOS 11+ and Python 3.11–3.14, and it actively breaks modern builds —
    # pygame <2.1.3 ships no wheels for Python 3.12+, so `pip download` would
    # fall back to building from sdist (and fail). Require a pygame new enough
    # to have wheels across the supported Python range.
    ("pgzero", ("pgzero>=1.2.1", "pygame>=2.6")),
    # The version of ipykernel here should match the one used by qtconsole as
    # specified in pyproject.toml. Mirrored from [project].dependencies.
    ("ipykernel", ("ipykernel>=6.29",)),
]


def os_compatibility_flags():
    """
    Determine additional `pip download` flags required to maximise
    compatibility with older versions of the current operating system.

    If downloading wheels with these flags fails, then we should consider it
    an issue to be resolved before doing a Mu release.
    """
    extra_flags = []
    # For macOS the oldest supported version follows PyQt6's baseline (macOS
    # 11 Big Sur for the 6.x wheels).
    if sys.platform == "darwin":
        # Target macOS 11+ for the *runner's* architecture (arm64 on the Apple
        # Silicon CI runners, x86_64 on Intel). The wheel arch must match the
        # app the installer bundles, or the baseline wheels won't load.
        extra_flags.extend(
            [
                "--platform=macosx_11_0_%s" % platform.machine(),
                "--only-binary=:all:",
            ]
        )
    # At the moment there aren't any additional flags for Windows or Linux
    return extra_flags


def compact(text):
    """Remove double line spaces and anything else which might help"""
    return "\n".join(line for line in text.splitlines() if line.strip())


def remove_dist_files(dirpath, logger):
    #
    # Clear the directory of any existing wheels and source distributions
    # (this is especially important because there may have been wheels
    # left over from a test with a different Python version)
    #
    logger.info("Removing wheel/sdist files from %s", dirpath)
    rm_files = (
        glob.glob(os.path.join(dirpath, "*.whl"))
        + glob.glob(os.path.join(dirpath, "*.gz"))
        + glob.glob(os.path.join(dirpath, "*.zip"))
    )
    for rm_filepath in rm_files:
        logger.debug("Removing existing wheel/sdist %s", rm_filepath)
        os.remove(rm_filepath)


def pip_download(dirpath, logger, additional_flags=[]):
    for name, pip_identifiers, *extra_flags in mode_packages:
        logger.info(
            "Running pip download for %s / %s / %s / %s",
            name,
            pip_identifiers,
            extra_flags,
            additional_flags,
        )
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--disable-pip-version-check",
                "download",
                "--destination-directory",
                dirpath,
                "--find-links",
                dirpath,
                *pip_identifiers,
            ]
            + extra_flags
            + additional_flags,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        logger.debug(compact(process.stdout.decode("utf-8")))

        #
        # If any wheel fails to download, remove any files already downloaded
        # (to ensure the download is triggered again) and raise an exception
        # NB Probably not necessary now that we're using a temp directory
        #
        if process.returncode != 0:
            # NB wrap pip_identifiers in a tuple: it is itself a tuple, and
            # `"%s" % some_tuple` would otherwise try to map each element to a
            # placeholder and raise TypeError, masking the real download error.
            raise WheelsDownloadError(
                "Pip was unable to download %s" % (pip_identifiers,)
            )


def convert_sdists_to_wheels(dirpath, logger):
    #
    # Convert any sdists to wheels
    #
    for filepath in glob.glob(os.path.join(dirpath, "*")):
        if filepath.endswith(("gz", ".zip")):
            logger.info("Building wheel for %s", filepath)
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--wheel-dir",
                    dirpath,
                    filepath,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.debug(compact(process.stdout.decode("utf-8")))
            if process.returncode != 0:
                logger.warning("Unable to build a wheel for %s", filepath)
            else:
                os.remove(filepath)


def zip_wheels(zip_filepath, dirpath, logger=logger):
    """Zip all the wheels into an archive"""
    logger.info("Building zip %s from wheels in %s", zip_filepath, dirpath)
    with zipfile.ZipFile(zip_filepath, "w") as z:
        for filepath in glob.glob(os.path.join(dirpath, "*.whl")):
            filename = os.path.basename(filepath)
            logger.debug("Adding %s to zip", filename)
            z.write(filepath, filename)


def download(zip_filepath=ZIP_FILEPATH, logger=logger, os_old_compat=False):
    """Download from PyPI, convert to wheels, and zip up

    To make all the libraries available for Mu modes (eg pygame zero, Flask etc.)
    we `pip download` them to a temporary location and then pack them into a
    zip file which is tagged with the current Mu version number

    We allow `logger` to be overridden because output from the
    virtual_environment module logger goes to the splash screen, while
    output from this module's logger doesn't

    Additional pip download flags to maximise wheel compatibility with old
    operating systems can be included using the `os_old_compat` parameter.
    """
    logger.info("Downloading wheels to %s", zip_filepath)
    extra_pip_flags = os_compatibility_flags() if os_old_compat else []

    #
    # Remove any leftover files from the place where the zip file
    # will be -- usually the `wheels` package folder
    #
    remove_dist_files(os.path.dirname(zip_filepath), logger)

    with tempfile.TemporaryDirectory() as temp_dirpath:
        pip_download(temp_dirpath, logger, extra_pip_flags)
        convert_sdists_to_wheels(temp_dirpath, logger)
        zip_wheels(zip_filepath, temp_dirpath, logger)


def _uv_executable():
    """Locate a `uv` binary for the packaging step (the `uv` wheel, else PATH)."""
    try:
        from uv import find_uv_bin

        return find_uv_bin()
    except Exception:
        return shutil.which("uv")


def download_python(dirpath=PYTHON_DIRPATH, logger=logger):
    """Fetch a relocatable CPython (and a pip wheel) to bundle in installers

    At first launch Mu builds the learner's environment with `uv venv`. In a
    packaged app the running interpreter can't be used as its base (Briefcase's
    `sys.executable` is a launcher stub uv can't inspect), and asking uv for a
    bare version may need a download. So the installer carries the
    python-build-standalone build uv itself would install for this platform and
    the running X.Y, which Mu extracts once and points `uv venv` at (see
    `bundled_python_archive` and `VirtualEnvironment.ensure_bundled_python`).
    The pip wheel lets `uv venv --seed` run with `--no-index`.
    """
    uv = _uv_executable()
    if not uv:
        raise WheelsDownloadError("uv is needed to locate a CPython download")
    version = "%d.%d" % sys.version_info[:2]
    process = subprocess.run(
        [uv, "python", "list", version, "--only-downloads", "--output-format", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        raise WheelsDownloadError(
            "uv could not list Python downloads:\n%s"
            % compact(process.stderr.decode("utf-8", errors="replace"))
        )
    downloads = [
        d
        for d in json.loads(process.stdout)
        if d.get("implementation") == "cpython"
        and d.get("variant", "default") == "default"
        and d.get("url")
    ]
    if not downloads:
        raise WheelsDownloadError("No CPython %s download for this platform" % version)
    url = downloads[0]["url"]

    if os.path.isdir(dirpath):
        shutil.rmtree(dirpath)
    os.makedirs(dirpath)
    filename = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path))
    logger.info("Downloading %s", url)
    # The download host rejects urllib's default User-Agent (HTTP 403).
    request = urllib.request.Request(url, headers={"User-Agent": "nu-editor-build"})
    with (
        urllib.request.urlopen(request) as response,
        open(os.path.join(dirpath, filename), "wb") as f,
    ):
        shutil.copyfileobj(response, f)

    logger.info("Downloading the pip wheel used to seed the venv")
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "download",
            "--only-binary=:all:",
            "--no-deps",
            "--destination-directory",
            dirpath,
            "pip",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    logger.debug(compact(process.stdout.decode("utf-8")))
    if process.returncode != 0:
        raise WheelsDownloadError("Pip was unable to download pip")


def bundled_python_archive(dirpath=PYTHON_DIRPATH):
    """Return the bundled CPython archive matching this Python's X.Y, or None

    None means "not an installer build" (e.g. a dev checkout), in which case
    the caller lets uv resolve an interpreter by version instead.
    """
    pattern = "cpython-%d.%d.*.tar.gz" % sys.version_info[:2]
    matches = sorted(glob.glob(os.path.join(dirpath, pattern)))
    return matches[-1] if matches else None
