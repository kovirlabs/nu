"""
The public plugin API for Nu.

Plugins import everything they need from `mu.plugin` -- never from
`mu.modes`, `mu.logic` or `mu.interface`, which can change between releases
without notice. What's exported here is versioned by PLUGIN_API_VERSION. See
docs/plugins.md.

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

from ..modes.base import BaseMode as Mode, MicroPythonMode
from .base import PLUGIN_API_VERSION, Plugin, ModePlugin, check_compatible
from .errors import PluginError
from .host import Host, PluginSettings

__all__ = [
    "PLUGIN_API_VERSION",
    "Plugin",
    "ModePlugin",
    "Mode",
    "MicroPythonMode",
    "Host",
    "PluginSettings",
    "PluginError",
    "check_compatible",
]
