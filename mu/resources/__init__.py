"""
Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

Based upon work done for Puppy IDE by Dan Pope, Nicholas Tollervey and Damien
George.

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

from importlib.resources import files
from PyQt6.QtGui import QPixmap, QIcon, QMovie
from PyQt6.QtCore import QDir
import os


def resource_filename(subpath):
    """Return the absolute filesystem path of a resource in this package."""
    return str(files(__name__).joinpath(subpath))


def resource_bytes(subpath):
    """Return the (binary) contents of a resource in this package."""
    return files(__name__).joinpath(subpath).read_bytes()


#: The core's own images.
IMAGES_DIR = resource_filename("images")
#: Folders of images contributed by plugins (see `register_image_dir`),
#: searched after the core's, in the order they were registered.
_plugin_image_dirs = []

# The following lines add the images and css directories to the search path.
QDir.addSearchPath("images", IMAGES_DIR)
QDir.addSearchPath("css", resource_filename("css"))


def path(name, resource_dir="images/", ext=""):
    """Return the filename for the referenced image."""
    return resource_filename(resource_dir + name + ext)


def _image_names(directory):
    """The names of the images in `directory`: each file name without its
    extension. Hidden files (e.g. .DS_Store) don't count."""
    return {
        os.path.splitext(entry)[0]
        for entry in os.listdir(directory)
        if not entry.startswith(".")
    }


def plugin_image_dirs():
    """The image folders plugins have registered, in search order (a copy)."""
    return list(_plugin_image_dirs)


def register_image_dir(directory):
    """
    Make the images in `directory` (a str or os.PathLike) available by name
    to `load_icon`, `load_pixmap`, `load_movie` and the theme stylesheets'
    "images:" URLs. They are searched after the core's images and any folders
    registered before.

    An image is known by its file name without the extension, so a mode's
    action `name` (which is also its icon and toolbar slot) picks up
    `name.svg` or `name.png`. Every name must be new: if the folder has an
    image named like one the core or another plugin already provides, a
    ValueError says which, and nothing is registered. Registering the same
    folder again does nothing.
    """
    directory = os.path.abspath(os.fspath(directory))
    if directory in _plugin_image_dirs:
        return
    if not os.path.isdir(directory):
        raise ValueError("{} is not a folder".format(directory))
    names = _image_names(directory)
    clashes = []
    for existing in [IMAGES_DIR] + _plugin_image_dirs:
        for name in sorted(names & _image_names(existing)):
            clashes.append("{!r} (already in {})".format(name, existing))
    if clashes:
        raise ValueError(
            "Images in {} have the same names as images Nu already has: {}. "
            "Rename them.".format(directory, ", ".join(clashes))
        )
    _plugin_image_dirs.append(directory)
    QDir.addSearchPath("images", directory)


def unregister_image_dir(directory):
    """Stop using the images in `directory` (if it was registered)."""
    directory = os.path.abspath(os.fspath(directory))
    if directory in _plugin_image_dirs:
        _plugin_image_dirs.remove(directory)
        QDir.setSearchPaths("images", [IMAGES_DIR] + _plugin_image_dirs)


def image_path(name, ext=""):
    """
    The path of the image `name` + `ext`: in the core's images if it's there,
    otherwise in the first plugin folder that has it. With no `ext`, a file
    called `name.<anything>` counts, and Qt works out the format from the
    extensionless path. An image nobody has gets the core's path, so Qt
    reports it missing as usual.
    """
    filename = name + ext
    for directory in [IMAGES_DIR] + _plugin_image_dirs:
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
        if not ext and name in _image_names(directory):
            return candidate
    return os.path.join(IMAGES_DIR, filename)


def load_icon(name):
    """Load an icon from the core's (or a plugin's) images."""
    svg_path = image_path(name, ext=".svg")
    if os.path.exists(svg_path):
        svg_icon = QIcon(svg_path)
        if svg_icon:
            return svg_icon
    return QIcon(image_path(name))


def load_pixmap(name, size=None):
    """Load a pixmap from the core's (or a plugin's) images."""
    if size is not None:
        icon = load_icon(name)
        return icon.pixmap(size)
    return QPixmap(image_path(name))


def load_movie(name):
    """Load an animated GIF from the core's (or a plugin's) images."""
    return QMovie(image_path(name))


def load_stylesheet(name):
    """Load a CSS stylesheet from the resources directory."""
    return resource_bytes("css/" + name).decode("utf8")


def load_font_data(name):
    """
    Load the (binary) content of a font as bytes
    """
    return resource_bytes("fonts/" + name)
