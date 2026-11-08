"""
The plugin environment: where the plugins a learner adds from the Plugins tab
live (see docs/plugins.md, "Adding a plugin").

In the installers Nu runs from an environment nobody can install into, so a
plugin added from PyPI (or from a wheel file) goes into a virtual environment
of its own, `DATA_DIR/plugin-env`, made with Nu's own Python. At startup its
site-packages goes on `sys.path` *after* Nu's own entries, before plugins are
discovered, so its plugins are found like any installed package's while Nu's
own packages (PyQt6 above all) always win.

This module has no GUI: the Plugins tab drives a `PluginJob` and shows its
output. Every uv command goes through `mu.virtual_environment.Uv`, so it's in
"What Nu Ran" and the log.

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

import importlib
import importlib.metadata
import json
import logging
import os
import shutil
import site
import sys
import sysconfig
import urllib.error
import urllib.parse
import urllib.request

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import (
    InvalidWheelFilename,
    canonicalize_name,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version

from .. import __version__ as nu_version
from .. import config
from ..virtual_environment import (
    Process,
    Uv,
    environment_interpreter,
    is_within,
    pyvenv_version,
)
from ..command_log import quote_command
from ..wheels import learner_env_requirements

logger = logging.getLogger(__name__)

#: The plugin environment's folder, in Nu's data folder.
ENV_DIRNAME = "plugin-env"
#: What the learner added to it (and its Python), next to it.
MANIFEST_NAME = "plugin-env.json"
#: The list of packages Nu already has, passed to uv as `--excludes`.
EXCLUDES_NAME = "nu-provides.txt"
#: The entry point group plugins advertise themselves in (as in loader.py).
ENTRY_POINT_GROUP = "mu.plugins"
#: Nu's own distribution names: always excluded, and a plugin's requirement
#: on one is checked against Nu's version, in case Nu runs without its own
#: package metadata (as in the installers).
NU_DISTRIBUTIONS = frozenset({"nu-editor", "mu-editor"})
#: Where PyPI describes a package.
PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"

# PluginEnvironment.status()
MISSING = "missing"  # no plugin environment yet
READY = "ready"  # it's there, and made with Nu's Python
PYTHON_CHANGED = "python-changed"  # made with another Python: reinstall


def python_version():
    """The X.Y version of the Python Nu runs on (e.g. "3.11")."""
    return "{}.{}".format(*sys.version_info[:2])


def nu_python():
    """
    The Python to make the plugin environment with: Nu's own, so a plugin's
    compiled code matches the process that imports it. That's
    `sys.executable`, unless Nu runs from an app's launcher (as Briefcase
    installers can), in which case the interpreter in Nu's Python's prefix,
    or failing that just its X.Y version for uv to find.
    """
    name = os.path.basename(sys.executable or "").lower()
    if name.startswith("python"):
        return sys.executable
    version = python_version()
    for folder in (sys.base_prefix, os.path.join(sys.base_prefix, "bin")):
        for candidate in (
            "python" + version,
            "python3",
            "python",
            "python.exe",
        ):
            path = os.path.join(folder, candidate)
            if os.path.isfile(path):
                return path
    return version


def _short(version):
    """ "3.11.15" -> "3.11"; None stays None."""
    if not version:
        return None
    return ".".join(str(version).split(".")[:2])


class PluginInputError(ValueError):
    """What the learner typed or picked can't be installed (the message says
    why, for them)."""


def parse_requirement(text):
    """
    The `packaging` Requirement for a plugin name the learner typed (e.g.
    "nu-microbit" or "nu-microbit>=0.2"). Only a plain PEP 508 requirement
    is accepted: no URLs, paths, options (anything starting with "-") or
    markers, so nothing else can sneak into uv's arguments. Raises
    PluginInputError with a sentence for the learner.
    """
    text = (text or "").strip()
    if not text:
        raise PluginInputError(_("Type the name of the plugin's package."))
    if text.startswith("-"):
        raise PluginInputError(_("“{text}” isn't a package name.").format(text=text))
    try:
        requirement = Requirement(text)
    except InvalidRequirement:
        raise PluginInputError(
            _(
                "“{text}” isn't a package name. A name is letters, digits, "
                "-, _ and . (for example nu-microbit)."
            ).format(text=text)
        )
    if requirement.url or requirement.marker:
        raise PluginInputError(
            _(
                "Type just the package's name (for example nu-microbit). To "
                "add a plugin from a file, use “Add from a file…”."
            )
        )
    return requirement


def wheel_name(path):
    """
    The (canonical name, version) of the wheel file at `path`, from its file
    name. Raises PluginInputError if it isn't a wheel file that exists.
    """
    if not path or not os.path.isfile(path):
        raise PluginInputError(_("Nu can't find the file {path}.").format(path=path))
    try:
        name, version, _build, _tags = parse_wheel_filename(os.path.basename(path))
    except InvalidWheelFilename:
        raise PluginInputError(
            _(
                "{file} isn't a wheel file. A plugin's file ends in .whl and "
                "has the package's name and version in it."
            ).format(file=os.path.basename(path))
        )
    return str(name), str(version)


def fetch_pypi_info(name, urlopen=None, timeout=10):
    """
    What PyPI says about the package `name`: a dict with its "name",
    "version" (the latest), "summary", "author" and "homepage" (each "" if it
    doesn't say). Returns None if PyPI has no such package. Raises OSError
    (urllib's errors are OSErrors) if PyPI can't be reached. It blocks:
    call it off the GUI thread.
    """
    urlopen = urllib.request.urlopen if urlopen is None else urlopen
    url = PYPI_JSON_URL.format(name=urllib.parse.quote(str(name)))
    try:
        with urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return None
        raise
    except ValueError as ex:  # not JSON
        raise OSError("PyPI sent something Nu can't read: {}".format(ex))
    info = data.get("info") or {}
    urls = info.get("project_urls") or {}
    homepage = info.get("home_page") or ""
    for key in ("Homepage", "homepage", "Home", "Source", "Repository"):
        if not homepage and urls.get(key):
            homepage = urls[key]
    author = info.get("author") or info.get("author_email") or ""
    author = author or info.get("maintainer") or info.get("maintainer_email") or ""
    return {
        "name": info.get("name") or str(name),
        "version": info.get("version") or "",
        "summary": (info.get("summary") or "").strip(),
        "author": author.strip(),
        "homepage": homepage.strip(),
    }


class PluginEnvironment:
    """
    The plugin environment at `<data_dir>/plugin-env`, and its manifest
    `<data_dir>/plugin-env.json`:

        {"python": "3.11",
         "plugins": [{"name": "nu-microbit", "requirement": "nu-microbit"},
                     {"name": "nu-example", "wheel": "/path/to/the.whl"}]}

    "python" is the X.Y it was made with; "plugins" what the learner added
    (as they typed it, or the wheel file), so it can be made again.
    """

    def __init__(self, data_dir=None):
        data_dir = config.DATA_DIR if data_dir is None else data_dir
        self.path = os.path.join(data_dir, ENV_DIRNAME)
        self.manifest_path = os.path.join(data_dir, MANIFEST_NAME)
        #: Whether add_to_sys_path put it on sys.path this session.
        self.on_sys_path = False

    # --- where things are ---

    @property
    def interpreter(self):
        """The plugin environment's Python (whether or not it exists yet)."""
        return environment_interpreter(self.path)

    def site_packages(self):
        """The plugin environment's site-packages folder."""
        return sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": self.path, "platbase": self.path}
        )

    @property
    def excludes_path(self):
        """The file listing what Nu already has, for uv's `--excludes`."""
        return os.path.join(self.path, EXCLUDES_NAME)

    def exists(self):
        """Has the plugin environment been made?"""
        return os.path.isfile(self.interpreter)

    # --- the manifest ---

    def manifest(self):
        """The manifest (see the class), or an empty one."""
        try:
            with open(self.manifest_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError):
            logger.exception("Can't read %s; starting it again", self.manifest_path)
            data = {}
        if not isinstance(data, dict):
            data = {}
        plugins = data.get("plugins")
        if not isinstance(plugins, list):
            plugins = []
        plugins = [p for p in plugins if isinstance(p, dict) and p.get("name")]
        return {"python": data.get("python"), "plugins": plugins}

    def _write_manifest(self, data):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def added(self):
        """The plugins the learner added, as manifest entries."""
        return self.manifest()["plugins"]

    def record_python(self):
        """Note the Python the environment has just been made with."""
        data = self.manifest()
        data["python"] = python_version()
        self._write_manifest(data)

    def record_added(self, name, requirement=None, wheel=None):
        """Remember that the learner added the plugin package `name`."""
        data = self.manifest()
        key = canonicalize_name(name)
        entry = {"name": str(key)}
        if wheel:
            entry["wheel"] = wheel
        else:
            entry["requirement"] = requirement or str(key)
        plugins = [p for p in data["plugins"] if canonicalize_name(p["name"]) != key]
        plugins.append(entry)
        data["plugins"] = plugins
        self._write_manifest(data)

    def record_removed(self, name):
        """Forget the plugin package `name`."""
        data = self.manifest()
        key = canonicalize_name(name)
        data["plugins"] = [
            p for p in data["plugins"] if canonicalize_name(p["name"]) != key
        ]
        self._write_manifest(data)

    def installed_from_file(self, name):
        """Was the plugin package `name` added from a wheel file?"""
        key = canonicalize_name(name)
        return any(
            canonicalize_name(p["name"]) == key and p.get("wheel") for p in self.added()
        )

    # --- at startup ---

    def python(self):
        """The X.Y of the Python the environment was made with, or None."""
        return _short(pyvenv_version(self.path)) or _short(self.manifest()["python"])

    def status(self):
        """MISSING, READY or PYTHON_CHANGED (made with another Python)."""
        if not self.exists():
            return MISSING
        made_with = self.python()
        if made_with and made_with != python_version():
            return PYTHON_CHANGED
        return READY

    def add_to_sys_path(self):
        """
        Put the plugin environment's site-packages on `sys.path`, after Nu's
        own entries (with `site.addsitedir`, so `.pth` files work), if it was
        made with Nu's Python. Call it before discovering plugins. Returns
        `status()`.
        """
        status = self.status()
        if status == READY:
            directory = self.site_packages()
            if directory not in sys.path:
                site.addsitedir(directory)
                importlib.invalidate_caches()
            self.on_sys_path = True
            logger.info("Plugins added by the learner are in %s", directory)
        elif status == PYTHON_CHANGED:
            logger.warning(
                "Not loading the plugins in %s: they were installed for Python "
                "%s and Nu now runs on Python %s. Reinstall them from the "
                "Plugins tab.",
                self.path,
                self.python(),
                python_version(),
            )
        return status

    # --- what's in it ---

    def distribution(self, name):
        """The installed distribution `name` in the plugin environment, or
        None. Reading it doesn't import it."""
        importlib.invalidate_caches()
        key = canonicalize_name(name)
        for dist in importlib.metadata.distributions(path=[self.site_packages()]):
            dist_name = dist.metadata["Name"]
            if dist_name and canonicalize_name(dist_name) == key:
                return dist
        return None

    def contains(self, dist):
        """Is the distribution `dist` installed in the plugin environment?"""
        try:
            location = str(dist.locate_file(""))
        except Exception:  # an odd Distribution; it isn't ours
            return False
        return bool(location) and is_within(location, self.site_packages())

    def nu_distributions(self):
        """
        Every distribution Nu's own process can see, outside the plugin
        environment, as {canonical name: version}: what the plugin
        environment must not get a second copy of.
        """
        found = {}
        for dist in importlib.metadata.distributions():
            name = dist.metadata["Name"]
            if not name or self.contains(dist):
                continue
            found.setdefault(str(canonicalize_name(name)), dist.version)
        return found

    def write_excludes(self):
        """
        Write the `--excludes` file: one line per package Nu already has (and
        Nu itself), so uv leaves them out of the plugin environment. Returns
        its path.
        """
        names = set(self.nu_distributions()) | NU_DISTRIBUTIONS
        os.makedirs(self.path, exist_ok=True)
        with open(self.excludes_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(names)) + "\n")
        return self.excludes_path

    def problems_with(self, dist, provided=None):
        """
        Why the newly installed distribution `dist` can't be used as a plugin
        (a list of sentences for the learner; [] if it can): it has no
        `mu.plugins` entry point, or it needs a version of a package Nu
        already has (`provided`, from `nu_distributions`) that Nu doesn't have.
        """
        problems = []
        if not any(ep.group == ENTRY_POINT_GROUP for ep in dist.entry_points):
            problems.append(
                _(
                    "{name} isn't a Nu plugin: it doesn't say it adds anything to Nu."
                ).format(name=dist.metadata["Name"])
            )
        provided = self.nu_distributions() if provided is None else provided
        for text in dist.requires or []:
            try:
                requirement = Requirement(text)
            except InvalidRequirement:
                continue
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue  # an extra, or not on this platform
            key = str(canonicalize_name(requirement.name))
            if key in NU_DISTRIBUTIONS:
                have = provided.get(key, nu_version)
            elif key in provided:
                have = provided[key]
            else:
                continue  # it's in the plugin environment
            try:
                ok = requirement.specifier.contains(Version(have), prereleases=True)
            except InvalidVersion:
                ok = True  # can't tell; let it try
            if not ok:
                problems.append(
                    _("It needs {requirement}, but Nu has {name} {version}.").format(
                        requirement=text.split(";")[0].strip(), name=key, version=have
                    )
                )
        return problems


class PluginJob:
    """
    One change to the plugin environment the Plugins tab asks for (add,
    update, remove, reinstall everything): a series of steps, some of them uv
    commands run asynchronously through `Uv` (so they're in "What Nu Ran"),
    whose output and progress go to `output(text)`. `finished(job)` is called
    at the end; then `succeeded` says whether it worked, `messages` what to
    tell the learner, and `changed` whether anything changes at the next
    start.

    `uv` makes the Uv for the plugin environment (`uv(venv_path)`),
    `learner_uv()` the one for the learner's environment (None if there's
    none to install into).
    """

    def __init__(self, environment, uv=Uv, learner_uv=None):
        self.env = environment
        self._uv = uv
        self._learner_uv = learner_uv
        self.steps = []
        self.messages = []
        self.succeeded = True
        self.changed = False
        self.process = None  # the running uv command (keep it referenced)
        self.output = None
        self._finished = None
        self.done = False
        #: Text the dialog shows before starting: what Nu will run.
        self.preview = []

    # --- running ---

    def start(self, output, finished):
        """Run the steps, reporting to `output(text)`; then `finished(self)`."""
        self.output = output
        self._finished = finished
        self._next()

    def _next(self):
        if not self.steps:
            self.done = True
            self._finished(self)
            return
        step = self.steps.pop(0)
        try:
            step()
        except Exception as ex:
            logger.exception("A plugin change failed")
            self.steps = []
            self._fail(_("Something went wrong: {error}").format(error=ex))
            self._next()

    def _fail(self, message):
        self.succeeded = False
        self.messages.append(message)
        self.output(message)

    def _say(self, message):
        self.messages.append(message)
        self.output(message)

    def _run(self, uv, args, then):
        """Run uv with `args`; call `then(ok)` when it finishes."""
        self._start(lambda slots: uv.run(*args, slots=slots), then)

    def _start(self, start, then):
        """
        Start a uv command with `start(slots)` (a Uv method returning the
        running Process), show it, and call `then(ok)` when it finishes.
        """

        def finished():
            record = self.process.command_record
            self.process = None
            then(record.exit_code == 0)

        self.output("")
        self.process = start(Process.Slots(output=self.output, finished=finished))
        self.output("$ " + self.process.command_record.display())

    # --- the commands ---

    def _plugin_uv(self):
        return self._uv(venv_path=self.env.interpreter)

    def venv_args(self):
        return ["venv", "--python", nu_python(), self.env.path]

    def install_args(self, targets, upgrade=False):
        args = ["pip", "install"]
        if upgrade:
            args.append("--upgrade")
        args += ["--python", self.env.interpreter, "--excludes", self.env.excludes_path]
        return args + list(targets)

    def uninstall_args(self, names):
        return ["pip", "uninstall", "--python", self.env.interpreter, *names]

    def _display(self, args):
        return "$ " + quote_command(["uv", *args])

    # --- steps ---

    def _make_env(self, fresh=False):
        """Steps: make the plugin environment if it's missing (or `fresh`)."""

        def remove_old():
            self.output(_("Removing the old plugin environment…"))
            shutil.rmtree(self.env.path, ignore_errors=True)
            self._next()

        def make():
            if self.env.exists():
                self._next()
                return

            def made(ok):
                if ok and self.env.exists():
                    self.env.record_python()
                    self._next()
                else:
                    self.steps = []
                    self._fail(_("Nu couldn't make the plugin environment."))
                    self._next()

            self._run(self._uv(), self.venv_args(), made)

        steps = [make]
        if fresh:
            steps.insert(0, remove_old)
        if fresh or not self.env.exists():
            self.preview.append(self._display(self.venv_args()))
        return steps

    def _install(self, name, target, wheel=None, requirement=None, upgrade=False):
        """Steps: install `target` (a requirement or wheel path) as the plugin
        package `name`, check it, record it and add its learner-env packages."""
        args = self.install_args([target], upgrade=upgrade)
        self.preview.append(self._display(args))
        state = {"dist": None}

        def install():
            self.env.write_excludes()

            def installed(ok):
                if not ok:
                    self._fail(
                        _("Nu couldn't install {name} (see above).").format(name=name)
                    )
                    self._skip_rest_of(name)
                self._next()

            self._run(
                self._plugin_uv(), self.install_args([target], upgrade), installed
            )

        def check():
            dist = self.env.distribution(name)
            if dist is None:
                self._fail(
                    _("Nu installed {name} but can't find it now.").format(name=name)
                )
                self._skip_rest_of(name)
                self._next()
                return
            problems = self.env.problems_with(dist)
            if problems:
                self._fail(
                    _("Nu can't use {name}, so it's removing it again:").format(
                        name=dist.metadata["Name"]
                    )
                )
                for problem in problems:
                    self._fail("  " + problem)
                self._skip_rest_of(name)
                self.steps.insert(0, self._uninstall_step(dist.metadata["Name"]))
                self._next()
                return
            state["dist"] = dist
            self.env.record_added(dist.metadata["Name"], requirement, wheel)
            self.changed = True
            if upgrade:
                done = _("Updated {name}: it's now version {version}.")
            else:
                done = _("Added {name} {version}.")
            self._say(done.format(name=dist.metadata["Name"], version=dist.version))
            self._next()

        def learner_env():
            dist = state["dist"]
            requirements = learner_env_requirements(dist)
            if not requirements:
                self._next()
                return
            uv = self._learner_uv() if self._learner_uv else None
            if uv is None:
                self._say(
                    _(
                        "It also needs {packages} for your programs; Nu will "
                        "add them when it next makes your Python environment."
                    ).format(packages=", ".join(requirements))
                )
                self._next()
                return
            self.output(
                _(
                    "Adding the packages {name} needs to your Python environment…"
                ).format(name=dist.metadata["Name"])
            )

            def added(ok):
                if not ok:
                    self._fail(
                        _(
                            "Nu couldn't add {packages} to your Python "
                            "environment (see above). Add them on the "
                            "Environment tab."
                        ).format(packages=", ".join(requirements))
                    )
                self._next()

            self._start(lambda slots: uv.install(requirements, slots=slots), added)

        install.plugin = check.plugin = learner_env.plugin = name
        return [install, check, learner_env]

    def _skip_rest_of(self, name):
        """Drop the remaining steps for the plugin package `name`."""
        self.steps = [s for s in self.steps if getattr(s, "plugin", None) != name]

    def _uninstall_step(self, name, forget=False):
        def uninstall():
            def removed(ok):
                if forget:
                    if ok:
                        self.env.record_removed(name)
                        self.changed = True
                        self._say(
                            _(
                                "Removed {name}. It's gone the next time you start Nu."
                            ).format(name=name)
                        )
                    else:
                        self._fail(
                            _("Nu couldn't remove {name} (see above).").format(
                                name=name
                            )
                        )
                self._next()

            self._run(self._plugin_uv(), self.uninstall_args([name]), removed)

        return uninstall


def add_job(environment, requirement=None, wheel=None, **kwargs):
    """
    A job adding the plugin `requirement` (a packaging Requirement, from
    `parse_requirement`) or the wheel file at `wheel` (checked with
    `wheel_name`) to the plugin environment.
    """
    job = PluginJob(environment, **kwargs)
    job.steps += job._make_env()
    if wheel:
        wheel = os.path.abspath(wheel)
        name, _version = wheel_name(wheel)
        job.steps += job._install(name, wheel, wheel=wheel)
    else:
        job.steps += job._install(
            requirement.name, str(requirement), requirement=str(requirement)
        )
    return job


def update_job(environment, name, **kwargs):
    """A job updating the plugin package `name` to its latest version."""
    job = PluginJob(environment, **kwargs)
    requirement = str(canonicalize_name(name))
    for entry in environment.added():
        if canonicalize_name(entry["name"]) == canonicalize_name(name):
            requirement = entry.get("requirement") or requirement
    # Upgrading by name: the latest that fits what the learner typed, if
    # they gave a version, otherwise the latest.
    job.steps += job._install(name, requirement, requirement=requirement, upgrade=True)
    return job


def remove_job(environment, name, **kwargs):
    """A job removing the plugin package `name` from the plugin environment."""
    job = PluginJob(environment, **kwargs)
    job.preview.append(job._display(job.uninstall_args([name])))
    job.steps.append(job._uninstall_step(name, forget=True))
    return job


def reinstall_job(environment, **kwargs):
    """
    A job making the plugin environment again with Nu's Python and adding
    every plugin the learner had added (after Nu moved to a new Python). A
    plugin added from a file that's gone is reported, not fatal.
    """
    job = PluginJob(environment, **kwargs)
    added = environment.added()
    job.steps += job._make_env(fresh=True)
    missing = []
    for entry in added:
        wheel = entry.get("wheel")
        if wheel:
            if not os.path.isfile(wheel):
                missing.append(entry)
                continue
            job.steps += job._install(entry["name"], wheel, wheel=wheel)
        else:
            requirement = entry.get("requirement") or entry["name"]
            job.steps += job._install(
                entry["name"], requirement, requirement=requirement
            )

    def report_missing():
        for entry in missing:
            job._fail(
                _(
                    "Nu couldn't add {name} again: its file {file} isn't there "
                    "any more. Add it again with “Add from a file…”."
                ).format(name=entry["name"], file=entry["wheel"])
            )
            environment.record_removed(entry["name"])
        job._next()

    def made_again():
        # The environment is new, for Nu's Python: it loads at the next start.
        job.changed = True
        job._next()

    job.steps.append(made_again)
    if missing:
        job.steps.append(report_missing)
    return job


#: The plugin environment in Nu's data folder.
plugin_env = PluginEnvironment()
