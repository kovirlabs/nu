"""
BBC micro:bit for Nu: a plugin adding the micro:bit mode.

Copyright (c) 2015-2021 Nicholas H.Tollervey and others (see the AUTHORS file).
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

import os

from mu.plugin import ModePlugin

from .mode import MicrobitMode


class MicrobitPlugin(ModePlugin):
    name = _("BBC micro:bit")
    description = _(
        "Adds BBC micro:bit mode, for writing MicroPython and flashing it "
        "onto a micro:bit."
    )
    api_version = "0.5"
    mode = MicrobitMode
    # The mode and Flash button icons (microbit, microbit-flash). "repl" and
    # "plotter" are Nu's own.
    images = os.path.join(os.path.dirname(__file__), "images")


__all__ = ["MicrobitPlugin", "MicrobitMode"]
