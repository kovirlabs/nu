# -*- coding: utf-8 -*-
"""
Tests for the resources sub-module.
"""

import os
import re
import shutil
from unittest import mock

import pytest
from PyQt6.QtCore import QDir, QSize
from PyQt6.QtGui import QIcon, QPixmap, QMovie

import mu.resources


def test_path():
    """
    Ensure the resource_filename function is called with the expected args and
    the path function under test returns its result.
    """
    with mock.patch("mu.resources.resource_filename", return_value="bar") as r:
        assert mu.resources.path("foo") == "bar"
        r.assert_called_once_with("images/foo")


def test_load_icon():
    """
    Check the load_icon function returns the expected QIcon object.
    """
    result = mu.resources.load_icon("icon")
    assert isinstance(result, QIcon)


def test_load_pixmap():
    """
    Check the load_pixmap function returns the expected QPixmap object.
    """
    result = mu.resources.load_pixmap("icon")
    assert isinstance(result, QPixmap)


def test_load_movie():
    """
    Check the load_movie function returns the expected QMovie object.
    """
    result = mu.resources.load_movie("splash_screen")
    assert isinstance(result, QMovie)


def test_stylesheet():
    """
    Ensure the resource_bytes function is called with the expected args and
    the load_stylesheet function returns its (decoded) result.
    """
    with mock.patch("mu.resources.resource_bytes", return_value=b"foo") as rs:
        assert "foo" == mu.resources.load_stylesheet("foo")
        rs.assert_called_once_with("css/foo")


def test_load_font_data():
    """
    Ensure font data can be loaded
    """
    with mock.patch("mu.resources.resource_bytes", return_value=b"foo") as rs:
        assert b"foo" == mu.resources.load_font_data("foo")
        rs.assert_called_once_with("fonts/foo")


def test_all_images_load_without_qt_warnings(qtapp):
    """
    Every bundled image loads, and Qt has nothing to complain about while
    loading it. (python.svg carried an Adobe XMP JPEG thumbnail that Qt6's SVG
    reader reports as "QSvgHandler: Image filename is empty" every time the
    mode selector or Python mode icon is drawn.)
    """
    from PyQt6.QtCore import qInstallMessageHandler
    from PyQt6.QtGui import QPixmap

    images_dir = mu.resources.path("", resource_dir="images/")
    warnings = []

    def handler(mode, context, message):
        warnings.append((current, message))

    previous = qInstallMessageHandler(handler)
    try:
        for current in sorted(os.listdir(images_dir)):
            if not current.endswith((".png", ".svg", ".gif", ".jpg")):
                continue  # Not an image Qt loads.
            pixmap = QPixmap(os.path.join(images_dir, current))
            assert not pixmap.isNull(), current
    finally:
        qInstallMessageHandler(previous)
    assert warnings == []


#: Images in mu/resources/images that nothing in mu/ names, and why they stay.
UNREFERENCED_IMAGES = {}


def _image_stems():
    images_dir = mu.resources.path("", resource_dir="images/")
    return {
        name.rsplit(".", 1)[0]
        for name in os.listdir(images_dir)
        if not name.startswith(".")
    }


def test_every_image_is_used_or_allowed():
    """
    Every image in mu/resources/images is named somewhere in Nu's source or
    stylesheets, or is on UNREFERENCED_IMAGES with a reason, so icons of
    removed features don't pile up again. An image is known by its file name
    without the extension (an action's `name` doubles as its icon), and it
    counts as named where that stem appears quoted, as a file name or as an
    "images:" URL. The generated API stubs in mu/modes/api don't count.
    """
    mu_dir = os.path.dirname(mu.__file__)
    skip = {
        os.path.join(mu_dir, "resources", "images"),
        os.path.join(mu_dir, "modes", "api"),
    }
    sources = []
    for folder, subfolders, files in os.walk(mu_dir):
        if folder in skip:
            subfolders[:] = []
            continue
        for name in files:
            if name.endswith((".py", ".css")):
                with open(os.path.join(folder, name), encoding="utf8") as f:
                    sources.append(f.read())
    text = "\n".join(sources)
    unused = [
        stem
        for stem in sorted(_image_stems())
        if stem not in UNREFERENCED_IMAGES
        and not re.search(r"""["':/]{}["'.]""".format(re.escape(stem)), text)
    ]
    assert unused == []


def test_unreferenced_images_allow_list_is_current():
    """Every image allowed to go unnamed still exists."""
    assert set(UNREFERENCED_IMAGES) <= _image_stems()


@pytest.fixture
def plugin_images(tmp_path):
    """
    A folder of plugin images ("rocket.png", "rocket.svg" and "badge.png"),
    unregistered again after the test.
    """
    core_png = mu.resources.path("checked", ext=".png")  # any real PNG
    directory = tmp_path / "images"
    directory.mkdir()
    for name in ("rocket.png", "badge.png"):
        shutil.copy(core_png, directory / name)
    shutil.copy(mu.resources.path("run", ext=".svg"), directory / "rocket.svg")
    yield directory
    mu.resources.unregister_image_dir(directory)


def test_image_path_prefers_the_core_images():
    """
    Core images are found in the core's images folder, with or without an
    extension (Qt works out the format of an extensionless path).
    """
    core = mu.resources.resource_filename("images")
    assert mu.resources.image_path("run", ".svg") == os.path.join(core, "run.svg")
    assert mu.resources.image_path("python") == os.path.join(core, "python")
    assert mu.resources.image_path("language.svg") == os.path.join(core, "language.svg")


def test_image_path_unknown_image_is_a_core_path():
    """
    An image nobody has resolves to where the core would keep it, as before,
    so Qt reports it missing in the usual way.
    """
    core = mu.resources.resource_filename("images")
    assert mu.resources.image_path("no-such-image", ".svg") == os.path.join(
        core, "no-such-image.svg"
    )


def test_register_image_dir_adds_plugin_images(plugin_images):
    """
    Once a plugin's folder is registered, its images load by name, through
    every loader and through the "images:" search path the theme CSS uses.
    """
    core = mu.resources.resource_filename("images")
    assert mu.resources.image_path("rocket") == os.path.join(core, "rocket")
    mu.resources.register_image_dir(plugin_images)
    expected = os.path.join(str(plugin_images), "rocket")
    assert mu.resources.image_path("rocket") == expected
    assert mu.resources.image_path("rocket", ".svg") == expected + ".svg"
    assert not mu.resources.load_icon("rocket").isNull()
    assert not mu.resources.load_icon("badge").isNull()
    assert not mu.resources.load_pixmap("badge").isNull()
    assert not mu.resources.load_pixmap("badge", size=QSize(16, 16)).isNull()
    assert str(plugin_images) in QDir.searchPaths("images")
    assert not QPixmap("images:badge.png").isNull()


def test_register_image_dir_accepts_paths_and_strings(plugin_images):
    """
    A str or os.PathLike works, and registering the same folder twice is
    harmless.
    """
    mu.resources.register_image_dir(str(plugin_images))
    mu.resources.register_image_dir(plugin_images)
    assert mu.resources.plugin_image_dirs() == [str(plugin_images)]


def test_register_image_dir_refuses_a_missing_folder(tmp_path):
    with pytest.raises(ValueError, match="not a folder"):
        mu.resources.register_image_dir(tmp_path / "nope")


def test_register_image_dir_refuses_a_clash_with_the_core(tmp_path):
    """
    A plugin can't ship an image with the same name as a core one (whatever
    the extension): the name would be ambiguous, so registering fails loudly
    and nothing is added.
    """
    directory = tmp_path / "images"
    directory.mkdir()
    (directory / "run.png").write_bytes(b"")
    (directory / "fine.png").write_bytes(b"")
    with pytest.raises(ValueError, match="'run'"):
        mu.resources.register_image_dir(directory)
    assert mu.resources.plugin_image_dirs() == []
    assert str(directory) not in QDir.searchPaths("images")


def test_register_image_dir_refuses_a_clash_with_another_plugin(
    plugin_images, tmp_path
):
    mu.resources.register_image_dir(plugin_images)
    other = tmp_path / "other"
    other.mkdir()
    (other / "badge.svg").write_bytes(b"")
    with pytest.raises(ValueError, match="'badge'.*" + re.escape(str(plugin_images))):
        mu.resources.register_image_dir(other)
    assert mu.resources.plugin_image_dirs() == [str(plugin_images)]


def test_register_image_dir_ignores_hidden_files(tmp_path):
    """
    Dot files (e.g. macOS's .DS_Store) aren't images and can't clash.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()
        (directory / ".DS_Store").write_bytes(b"")
    try:
        mu.resources.register_image_dir(first)
        mu.resources.register_image_dir(second)
    finally:
        mu.resources.unregister_image_dir(first)
        mu.resources.unregister_image_dir(second)


def test_unregister_image_dir(plugin_images):
    """
    Unregistering removes the folder from every lookup; unregistering one
    that isn't registered does nothing.
    """
    mu.resources.register_image_dir(plugin_images)
    mu.resources.unregister_image_dir(plugin_images)
    mu.resources.unregister_image_dir(plugin_images)
    assert mu.resources.plugin_image_dirs() == []
    assert str(plugin_images) not in QDir.searchPaths("images")
    assert QDir.searchPaths("images") == [mu.resources.resource_filename("images")]
