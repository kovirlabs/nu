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
import re
import sys
import traceback
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
#: The settings key holding the ids of plugins Nu's error handler switched
#: off (with the learner's OK) because they kept failing.
SWITCHED_OFF_SETTING = "plugins_switched_off_after_errors"
#: The plugin packages that ship with Nu (nu-editor depends on them, and the
#: installers include them). Their kind is "bundled" rather than "package".
BUNDLED_DISTRIBUTIONS = frozenset({"nu-circuitpython", "nu-pygamezero"})
#: What the bundled plugins call themselves (their Plugin.name), so the
#: Plugins tab can name one that's switched off, and so isn't imported.
BUNDLED_NAMES = {"nu-circuitpython": "CircuitPython", "nu-pygamezero": "Pygame Zero"}

# Statuses recorded for each discovered plugin.
LOADED = "loaded"
DISABLED = "disabled"
SKIPPED = "skipped"

# Why a plugin was skipped (PluginRecord.problem).
DUPLICATE = "duplicate"
IMPORT_FAILED = "import-failed"
INCOMPATIBLE = "incompatible"
REGISTER_FAILED = "register-failed"


class PluginLoadError(Exception):
    pass


@dataclass
class PluginSource:
    """
    A plugin that has been found but not yet imported.

    `id` is the stable name used to enable/disable it: the entry point name,
    or the module name in the drop-in folder. `kind` is "bundled" (ships with
    Nu), "package" (another installed package) or "folder" (the drop-in
    folder); `origin` says where exactly, for logs and the Plugins tab.
    `name` and `description` are what the package says about itself (its
    distribution name, or a bundled plugin's own name, and its summary), if
    anything: what the Plugins tab shows for a plugin that isn't imported.
    Calling `load()` imports it and returns a Plugin instance, or raises.
    """

    id: str
    kind: str  # "bundled", "package" or "folder"
    origin: str
    load: object = field(repr=False)
    description: str = ""
    name: str = ""


@dataclass
class PluginRecord:
    """
    What happened to one discovered plugin.

    A skipped plugin has a `reason` (one line, for the log), a `problem`
    saying which kind of failure it was (DUPLICATE, IMPORT_FAILED,
    INCOMPATIBLE or REGISTER_FAILED) and, when there is one, the traceback in
    `detail`. `name` and `description` are the plugin's own once it's loaded;
    until then the package's (see PluginSource), or the id for a name.
    """

    id: str
    kind: str
    origin: str
    status: str  # LOADED, DISABLED or SKIPPED
    reason: str = ""
    plugin: object = None
    problem: str = ""
    detail: str = ""
    name: str = ""
    description: str = ""


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
        kind = "package"
        name = description = ""
        if dist:
            origin = "{} {}".format(dist.name, dist.version)
            dist_name = _normalise(dist.name)
            if dist_name in BUNDLED_DISTRIBUTIONS:
                kind = "bundled"
                name = _(BUNDLED_NAMES[dist_name])
            else:
                name = _metadata(dist, "Name")
            description = _metadata(dist, "Summary")
        else:
            origin = entry_point.value

        def load(entry_point=entry_point):
            return _instantiate(entry_point.load(), entry_point.value)

        sources.append(
            PluginSource(entry_point.name, kind, origin, load, description, name)
        )
    return sources


def _normalise(dist_name):
    """A distribution name as PEP 503 compares them."""
    return re.sub(r"[-_.]+", "-", dist_name).lower()


def _metadata(dist, key):
    """A one-line field (such as "Name" or "Summary") a package declares, or
    "". Reading it doesn't import the package."""
    value = dist.metadata.get(key)
    return value.strip() if isinstance(value, str) else ""


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


def switched_off_after_errors(store=None):
    """
    The ids of the plugins Nu switched off, with the learner's OK, because
    they kept having errors (see mu.plugin.errors).
    """
    store = settings.settings if store is None else store
    return set(store.get(SWITCHED_OFF_SETTING, []))


def set_plugin_enabled(plugin_id, enabled, store=None, after_errors=False):
    """
    Switch a plugin on or off; takes effect the next time Nu starts. The
    settings are saved straight away, so the change survives Nu crashing.

    `after_errors` marks a plugin switched off because it kept failing, so
    the Plugins tab can say so. Any other change clears the mark.
    """
    store = settings.settings if store is None else store
    disabled = disabled_plugins(store)
    if enabled:
        disabled.discard(plugin_id)
    else:
        disabled.add(plugin_id)
    store[DISABLED_SETTING] = sorted(disabled)
    marked = switched_off_after_errors(store)
    if after_errors and not enabled:
        marked.add(plugin_id)
    else:
        marked.discard(plugin_id)
    if marked or SWITCHED_OFF_SETTING in store:
        store[SWITCHED_OFF_SETTING] = sorted(marked)
    _save(store)


def _save(store):
    save = getattr(store, "save", None)
    if save is not None:
        save()


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
        record = PluginRecord(
            source.id,
            source.kind,
            source.origin,
            SKIPPED,
            name=source.name or source.id,
            description=source.description,
        )
        records.append(record)
        if source.id in seen:
            record.problem = DUPLICATE
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
            record.problem = IMPORT_FAILED
            record.reason = "it failed to import: {}".format(
                "".join(traceback.format_exception_only(ex)).strip()
            )
            record.detail = _plugin_traceback(ex)
            logger.exception("Skipping plugin %s (%s)", source.id, source.origin)
            continue
        if plugin.name == Plugin.name:
            plugin.name = source.id  # unnamed: use its id in logs and the UI
        record.name = plugin.name
        record.description = getattr(plugin, "description", "") or record.description
        reason = check_compatible(getattr(plugin, "api_version", None))
        if reason:
            record.problem = INCOMPATIBLE
            record.reason = reason
            logger.warning("Skipping plugin %s (%s): %s", *_describe(record))
            continue
        if host.load_plugin(plugin):
            record.status = LOADED
            record.plugin = plugin
        else:
            record.problem = REGISTER_FAILED
            record.reason = "it failed to register (see the log)"
    return records


#: Where importlib's own code is, to leave it out of a plugin's traceback.
_IMPORTLIB_DIR = os.path.dirname(importlib.util.__file__) + os.sep


def _is_loading_frame(frame):
    """Is `frame` Nu's loader or Python's import machinery, not a plugin?"""
    return (
        frame.filename == __file__
        or frame.filename.startswith("<frozen importlib")
        or frame.filename.startswith(_IMPORTLIB_DIR)
    )


def _plugin_traceback(ex):
    """
    The traceback of a plugin that failed to import, starting at the
    plugin's own code: the frames of Nu's loader and importlib above it say
    nothing to the plugin's author. If the error is in those frames, the
    whole traceback is kept.
    """
    exception = traceback.TracebackException.from_exception(ex)
    frames = list(exception.stack)
    while frames and _is_loading_frame(frames[0]):
        frames.pop(0)
    if frames:
        exception.stack = traceback.StackSummary.from_list(frames)
    return "".join(exception.format())


def describe(records, store=None, modes_of=None):
    """
    What the Plugins tab shows: a dict per record, in the same order, with
    the record's facts plus `enabled` (whether it will load at the next
    start, from the settings), `switched_off_after_errors`, `can_switch`
    (False for a duplicate id, which is switched with the first plugin of
    that id) and `modes` (from `modes_of(plugin)`; [] if it isn't loaded).
    """
    disabled = disabled_plugins(store)
    after_errors = switched_off_after_errors(store)
    rows = []
    seen = set()
    for record in records:
        modes = []
        if record.plugin is not None and modes_of is not None:
            modes = list(modes_of(record.plugin))
        rows.append(
            {
                "id": record.id,
                "name": record.name or record.id,
                "description": record.description,
                "kind": record.kind,
                "origin": record.origin,
                "status": record.status,
                "problem": record.problem,
                "reason": record.reason,
                "detail": record.detail,
                "enabled": record.id not in disabled,
                "switched_off_after_errors": record.id in after_errors,
                "can_switch": record.id not in seen,
                "modes": modes,
            }
        )
        seen.add(record.id)
    return rows


def _describe(record):
    return record.id, record.origin, record.reason
