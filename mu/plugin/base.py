"""
The plugin base classes and API versioning for Nu.

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

#: The version of the plugin API this core provides, as "MAJOR.MINOR".
#: While MAJOR is 0 the API is still settling, so every MINOR bump may break
#: plugins; from 1.0 a MINOR bump only adds to the API.
PLUGIN_API_VERSION = "0.1"


def _parse_version(version):
    """
    Turn a "MAJOR.MINOR" string into a (major, minor) tuple of ints, or raise
    ValueError if it isn't one.
    """
    if not isinstance(version, str):
        raise ValueError(version)
    parts = version.split(".")
    if len(parts) != 2:
        raise ValueError(version)
    return int(parts[0]), int(parts[1])


def check_compatible(api_version, core_version=PLUGIN_API_VERSION):
    """
    Return None if a plugin targeting `api_version` can run on a core
    providing `core_version`, otherwise a short reason why it can't.

    A plugin is compatible when it targets the same MAJOR version and a MINOR
    version no newer than the core's. While MAJOR is 0 the MINOR versions must
    match exactly, since 0.x releases are allowed to break the API.
    """
    try:
        major, minor = _parse_version(api_version)
    except ValueError:
        return "it declares no valid api_version (got {!r})".format(api_version)
    core_major, core_minor = _parse_version(core_version)
    if major != core_major or (major == 0 and minor != core_minor):
        return "it targets plugin API {}, but this Nu provides {}".format(
            api_version, core_version
        )
    if minor > core_minor:
        return "it needs plugin API {}, newer than this Nu's {}".format(
            api_version, core_version
        )
    return None


class Plugin:
    """
    Base class for a Nu plugin.

    Subclasses set `name` and `api_version`, then do all their wiring in
    `register`, using only the `Host` they are given.
    """

    #: Human readable name, used in logs and (later) the Plugins tab.
    name = "UNNAMED PLUGIN"
    #: The PLUGIN_API_VERSION this plugin was written against. Required.
    api_version = None

    def register(self, host):
        """
        Called once when the plugin is loaded. Use `host` to register modes
        and anything else the plugin contributes.
        """
        pass

    def unregister(self, host):
        """
        Called when the plugin is unloaded. Modes registered through `host`
        are removed automatically; undo anything else here.
        """
        pass


class ModePlugin(Plugin):
    """
    A plugin whose only job is to contribute modes.

    Set `mode` to a single Mode subclass, or `modes` to several, and they are
    registered for you.
    """

    #: A single Mode subclass to register.
    mode = None
    #: Several Mode subclasses to register (after `mode`, if both are set).
    modes = ()

    def register(self, host):
        mode_classes = ([self.mode] if self.mode else []) + list(self.modes)
        for mode_class in mode_classes:
            host.register_mode(mode_class)
