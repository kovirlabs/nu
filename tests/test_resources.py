# -*- coding: utf-8 -*-
"""
Tests for the resources sub-module.
"""

import os
import mu.resources
from unittest import mock
from PyQt6.QtGui import QIcon, QPixmap, QMovie


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
                continue  # e.g. the splash screen's GIMP source (.xcf)
            pixmap = QPixmap(os.path.join(images_dir, current))
            assert not pixmap.isNull(), current
    finally:
        qInstallMessageHandler(previous)
    assert warnings == []
