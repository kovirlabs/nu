"""
Finding and loading plugins: installed packages and the drop-in folder.

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

import importlib.metadata
import importlib.util
import inspect
import logging
import os
import sys
from dataclasses import dataclass, field

from .. import config, settings
from .base import Plugin, check_compatible

logger = logging.getLogger(__name__)

#: The entry point group installed plugins advertise themselves in.
ENTRY_POINT_GROUP = "mu.plugins"
#: Where local, unpackaged plugins are dropped.
DROPIN_DIR = os.path.join(config.DATA_DIR, "plugins")
#: The settings key holding the ids of plugins the user has switched off.
DISABLED_SETTING = "disabled_plugins"

# Statuses recorded for each discovered plugin.
LOADED = "loaded"
DISABLED = "disabled"
SKIPPED = "skipped"


class PluginLoadError(Exception):
    pass


@dataclass
class PluginSource:
    """
    A plugin that has been found but not yet imported.

    `id` is the stable name used to enable/disable it: the entry point name,
    or the module name in the drop-in folder. `origin` says where it came from
    for logs and the (future) Plugins tab. Calling `load()` imports it and
    returns a Plugin instance, or raises.
    """

    id: str
    kind: str  # "package" or "folder"
    origin: str
    load: object = field(repr=False)


@dataclass
class PluginRecord:
    """What happened to one discovered plugin."""

    id: str
    kind: str
    origin: str
    status: str  # LOADED, DISABLED or SKIPPED
    reason: str = ""
    plugin: object = None


def _instantiate(obj, what):
    """
    Turn whatever an entry point or drop-in module offers into a Plugin
    instance: a Plugin subclass is instantiated, an instance is used as is,
    and any other callable is treated as a factory.
    """
    if isinstance(obj, type):
        if issubclass(obj, Plugin):
            return obj()
    elif isinstance(obj, Plugin):
        return obj
    elif callable(obj):
        result = obj()
        if isinstance(result, Plugin):
            return result
    raise PluginLoadError("{} is not a mu.plugin.Plugin".format(what))


def entry_point_sources(group=ENTRY_POINT_GROUP):
    """
    Plugins installed as packages in the environment Nu runs from, found
    through their `mu.plugins` entry points.
    """
    sources = []
    for entry_point in importlib.metadata.entry_points(group=group):
        dist = entry_point.dist
        origin = "{} {}".format(dist.name, dist.version) if dist else entry_point.value

        def load(entry_point=entry_point):
            return _instantiate(entry_point.load(), entry_point.value)

        sources.append(PluginSource(entry_point.name, "package", origin, load))
    return sources


def _dropin_plugin_object(module):
    """
    The plugin a drop-in module offers: its `PLUGIN` attribute if it has one,
    otherwise the single Plugin subclass defined in it.
    """
    if hasattr(module, "PLUGIN"):
        return module.PLUGIN
    defined = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, Plugin) and obj.__module__ == module.__name__
    ]
    if len(defined) != 1:
        raise PluginLoadError(
            "{} must define exactly one Plugin subclass, or set PLUGIN "
            "(found {})".format(module.__name__, len(defined))
        )
    return defined[0]


def _import_dropin(name, path):
    """
    Import a drop-in module or package under its own name. Refuse a name
    that is already importable, so a drop-in can never shadow another module
    (e.g. a stray `json.py` in the folder).
    """
    if name in sys.modules or importlib.util.find_spec(name) is not None:
        raise PluginLoadError(
            "{!r} clashes with an installed module; rename it".format(name)
        )
    if os.path.isdir(path):
        init = os.path.join(path, "__init__.py")
        spec = importlib.util.spec_from_file_location(
            name, init, submodule_search_locations=[path]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)  # don't leave a half-imported module
        raise
    return module


def dropin_sources(dirpath=None):
    """
    Plugins dropped into `dirpath`: each `name.py` file or `name/` package
    (with an `__init__.py`) is one plugin, with id `name`. The folder is
    created if it doesn't exist, so it's there for learners to find.
    Defaults to DROPIN_DIR.
    """
    if dirpath is None:
        dirpath = DROPIN_DIR
    try:
        os.makedirs(dirpath, exist_ok=True)
        entries = sorted(os.listdir(dirpath))
    except OSError:
        logger.exception("Can't read the plugins folder %s", dirpath)
        return []
    sources = []
    for entry in entries:
        path = os.path.join(dirpath, entry)
        if entry.startswith((".", "_")):
            continue
        if os.path.isdir(path):
            if not os.path.isfile(os.path.join(path, "__init__.py")):
                continue
            name = entry
        elif entry.endswith(".py"):
            name = entry[:-3]
        else:
            continue
        if not name.isidentifier():
            logger.warning("Ignoring %s: not a valid Python module name", path)
            continue

        def load(name=name, path=path):
            module = _import_dropin(name, path)
            return _instantiate(_dropin_plugin_object(module), name)

        sources.append(PluginSource(name, "folder", path, load))
    return sources


def discover(dropin_dir=None):
    """
    Every plugin Nu can see: installed packages first, then the drop-in
    folder. Nothing is imported yet.
    """
    try:
        sources = entry_point_sources()
    except Exception:
        logger.exception("Can't read installed plugin entry points")
        sources = []
    return sources + dropin_sources(dropin_dir)


def disabled_plugins(store=None):
    """The ids of the plugins the user has switched off."""
    store = settings.settings if store is None else store
    return set(store.get(DISABLED_SETTING, []))


def set_plugin_enabled(plugin_id, enabled, store=None):
    """Switch a plugin on or off; takes effect the next time Nu starts."""
    store = settings.settings if store is None else store
    disabled = disabled_plugins(store)
    if enabled:
        disabled.discard(plugin_id)
    else:
        disabled.add(plugin_id)
    store[DISABLED_SETTING] = sorted(disabled)


def load_plugins(host, sources=None, store=None):
    """
    Load every discovered, enabled plugin into `host` and return a
    PluginRecord for each one found.

    This never raises. A plugin that is switched off, shares an id with one
    already found, fails to import, targets an incompatible API version or
    fails in `register` is recorded (and logged) as skipped, and Nu carries
    on without it.
    """
    if sources is None:
        sources = discover()
    disabled = disabled_plugins(store)
    records = []
    seen = set()
    for source in sources:
        record = PluginRecord(source.id, source.kind, source.origin, SKIPPED)
        records.append(record)
        if source.id in seen:
            record.reason = "another plugin is already called {!r}".format(source.id)
            logger.warning("Skipping plugin %s (%s): %s", *_describe(record))
            continue
        seen.add(source.id)
        if source.id in disabled:
            record.status = DISABLED
            logger.info("Plugin %s (%s) is switched off", source.id, source.origin)
            continue
        try:
            plugin = source.load()
        except KeyboardInterrupt:
            raise
        except BaseException as ex:  # incl. SystemExit from a plugin's import
            record.reason = "it failed to import: {}".format(ex)
            logger.exception("Skipping plugin %s (%s)", source.id, source.origin)
            continue
        if plugin.name == Plugin.name:
            plugin.name = source.id  # unnamed: use its id in logs and the UI
        reason = check_compatible(getattr(plugin, "api_version", None))
        if reason:
            record.reason = reason
            logger.warning("Skipping plugin %s (%s): %s", *_describe(record))
            continue
        if host.load_plugin(plugin):
            record.status = LOADED
            record.plugin = plugin
        else:
            record.reason = "it failed to register (see the log)"
    return records


def _describe(record):
    return record.id, record.origin, record.reason
