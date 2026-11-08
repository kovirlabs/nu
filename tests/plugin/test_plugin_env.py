# -*- coding: utf-8 -*-
"""
Tests for the plugin environment: where the plugins a learner adds live.

uv and PyPI are faked: `FakeUvs` records each uv command and, when the test
runs it, applies what it would do to the folders (making the environment,
writing a package's metadata, removing it).
"""

import io
import json
import os
import shutil
import sys
import urllib.error
from types import SimpleNamespace
from unittest import mock

import pytest

from mu import __version__ as nu_version
from mu.command_log import CommandRecord
from mu.plugin import plugin_env
from mu.plugin.plugin_env import (
    MISSING,
    PYTHON_CHANGED,
    READY,
    PluginEnvironment,
    PluginInputError,
)

PY = plugin_env.python_version()


# --- helpers ---


def make_env(environment, version=None):
    """Make the plugin environment's folders, as `uv venv` would."""
    os.makedirs(os.path.dirname(environment.interpreter), exist_ok=True)
    with open(environment.interpreter, "w") as f:
        f.write("")
    os.makedirs(environment.site_packages(), exist_ok=True)
    with open(os.path.join(environment.path, "pyvenv.cfg"), "w") as f:
        f.write("home = /usr/bin\nversion_info = {}.7\n".format(version or PY))


def write_dist(
    folder, name, version="1.0", requires=(), plugin=True, summary="A plugin."
):
    """Install the metadata of a package `name` into `folder`."""
    dist_info = os.path.join(
        folder, "{}-{}.dist-info".format(name.replace("-", "_"), version)
    )
    os.makedirs(dist_info, exist_ok=True)
    lines = [
        "Metadata-Version: 2.1",
        "Name: " + name,
        "Version: " + version,
        "Summary: " + summary,
    ]
    lines += ["Requires-Dist: " + r for r in requires]
    with open(os.path.join(dist_info, "METADATA"), "w") as f:
        f.write("\n".join(lines) + "\n")
    if plugin:
        with open(os.path.join(dist_info, "entry_points.txt"), "w") as f:
            f.write("[mu.plugins]\n{0} = {0}:Plugin\n".format(name.replace("-", "_")))
    return dist_info


def remove_dist(folder, name):
    for entry in os.listdir(folder):
        if entry.startswith(name.replace("-", "_") + "-"):
            shutil.rmtree(os.path.join(folder, entry))


class FakeUvs:
    """
    Stands in for mu.virtual_environment.Uv (`FakeUvs()(venv_path=...)` is
    a Uv). Commands wait until `run_all`, which asks `handler(args,
    venv_path)` for each one's exit code (the handler does what uv would).
    """

    def __init__(self, handler=None):
        self.calls = []
        self.pending = []
        self.handler = handler or (lambda args, venv_path: 0)

    def __call__(self, uv_executable=None, venv_path=None):
        return FakeUv(self, venv_path)

    def run_all(self):
        while self.pending:
            args, venv_path, slots, record = self.pending.pop(0)
            code = self.handler(args, venv_path)
            slots.output("uv says hello")
            record.finish(code)
            slots.finished()


class FakeUv:
    def __init__(self, owner, venv_path):
        self.owner = owner
        self.venv_path = venv_path

    def run(self, *args, slots):
        record = CommandRecord(["/opt/bin/uv", *args])
        self.owner.calls.append((list(args), self.venv_path))
        self.owner.pending.append((list(args), self.venv_path, slots, record))
        return SimpleNamespace(command_record=record)

    def install(self, packages, slots):
        return self.run(
            "pip", "install", "--python", self.venv_path, *packages, slots=slots
        )


class Behaviour:
    """What the fake uv does: make the environment and (un)install the
    packages in `packages` ({target: (name, version, requires, plugin)})."""

    def __init__(self, environment, packages=None, fail=()):
        self.env = environment
        self.packages = packages or {}
        self.fail = set(fail)

    def __call__(self, args, venv_path):
        command = " ".join(args[:2])
        if command in self.fail or args[-1] in self.fail:
            return 1
        if args[0] == "venv":
            make_env(self.env)
        elif command == "pip install" and venv_path == self.env.interpreter:
            name, version, requires, plugin = self.packages[args[-1]]
            remove_dist(self.env.site_packages(), name)
            write_dist(self.env.site_packages(), name, version, requires, plugin)
        elif command == "pip uninstall":
            remove_dist(self.env.site_packages(), args[-1])
        return 0


def run(job):
    """Run `job` to the end; return its output lines."""
    lines = []
    finished = []
    job.start(lines.append, finished.append)
    job._uv.run_all()
    if job._learner_uv:
        learner = job._learner_uv()
        if learner is not None:
            learner.owner.run_all()
            job._uv.run_all()
    assert finished == [job]
    assert job.done
    return lines


@pytest.fixture
def env(tmp_path):
    return PluginEnvironment(str(tmp_path / "data"))


# --- small helpers ---


def test_python_version():
    assert PY == "{}.{}".format(*sys.version_info[:2])


def test_nu_python_is_sys_executable():
    with mock.patch.object(sys, "executable", "/opt/nu/bin/python3.11"):
        assert plugin_env.nu_python() == "/opt/nu/bin/python3.11"


def test_nu_python_from_an_app_launcher(tmp_path):
    """
    In an app whose executable is a launcher, not Python, the Python in its
    prefix is used; failing that, its version for uv to find.
    """
    (tmp_path / "bin").mkdir()
    python = tmp_path / "bin" / "python3"
    python.write_text("")
    with (
        mock.patch.object(sys, "executable", "/Applications/Nu.app/Nu Editor"),
        mock.patch.object(sys, "base_prefix", str(tmp_path)),
    ):
        assert plugin_env.nu_python() == str(python)
        python.unlink()
        assert plugin_env.nu_python() == PY


def test_short():
    assert plugin_env._short("3.11.15") == "3.11"
    assert plugin_env._short(None) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("nu-microbit", "nu-microbit"),
        ("  nu-microbit>=0.2 ", "nu-microbit>=0.2"),
        ("nu_microbit[extra]", "nu_microbit[extra]"),
    ],
)
def test_parse_requirement(text, expected):
    assert str(plugin_env.parse_requirement(text)) == expected


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "Type the name"),
        (None, "Type the name"),
        ("--index-url=http://evil", "isn't a package name"),
        ("-r requirements.txt", "isn't a package name"),
        ("./my-plugin", "isn't a package name"),
        ("nu microbit", "isn't a package name"),
        ("nu-microbit @ https://example.com/x.whl", "Add from a file"),
        ('nu-microbit; sys_platform == "linux"', "Add from a file"),
    ],
)
def test_parse_requirement_refuses_anything_but_a_name(text, message):
    """Only a plain requirement gets near uv's arguments."""
    with pytest.raises(PluginInputError, match=message):
        plugin_env.parse_requirement(text)


def test_wheel_name(tmp_path):
    wheel = tmp_path / "Nu_Example_Plugin-0.1.0-py3-none-any.whl"
    wheel.write_text("")
    assert plugin_env.wheel_name(str(wheel)) == ("nu-example-plugin", "0.1.0")


def test_wheel_name_problems(tmp_path):
    with pytest.raises(PluginInputError, match="can't find the file"):
        plugin_env.wheel_name(str(tmp_path / "missing.whl"))
    with pytest.raises(PluginInputError, match="can't find the file"):
        plugin_env.wheel_name("")
    not_a_wheel = tmp_path / "plugin.zip"
    not_a_wheel.write_text("")
    with pytest.raises(PluginInputError, match="plugin.zip isn't a wheel file"):
        plugin_env.wheel_name(str(not_a_wheel))


# --- PyPI ---


def pypi(data):
    """A fake urlopen answering with `data` as JSON."""
    urlopen = mock.MagicMock()
    urlopen.return_value = io.BytesIO(json.dumps(data).encode("utf-8"))
    return urlopen


def test_fetch_pypi_info():
    urlopen = pypi(
        {
            "info": {
                "name": "nu-microbit",
                "version": "0.2.0",
                "summary": " micro:bit mode for Nu. ",
                "author": "",
                "author_email": "Kovir Labs <hi@example.com>",
                "home_page": None,
                "project_urls": {"Source": "https://github.com/kovirlabs/nu"},
            }
        }
    )
    info = plugin_env.fetch_pypi_info("nu-microbit", urlopen=urlopen)
    assert info == {
        "name": "nu-microbit",
        "version": "0.2.0",
        "summary": "micro:bit mode for Nu.",
        "author": "Kovir Labs <hi@example.com>",
        "homepage": "https://github.com/kovirlabs/nu",
    }
    urlopen.assert_called_once_with(
        "https://pypi.org/pypi/nu-microbit/json", timeout=10
    )


def test_fetch_pypi_info_with_little_info():
    info = plugin_env.fetch_pypi_info("cows", urlopen=pypi({}))
    assert info == {
        "name": "cows",
        "version": "",
        "summary": "",
        "author": "",
        "homepage": "",
    }
    info = plugin_env.fetch_pypi_info(
        "cows",
        urlopen=pypi({"info": {"maintainer": "Daisy", "home_page": "https://cow"}}),
    )
    assert (info["author"], info["homepage"]) == ("Daisy", "https://cow")


def test_fetch_pypi_info_quotes_the_name():
    urlopen = pypi({})
    plugin_env.fetch_pypi_info("a b", urlopen=urlopen)
    assert urlopen.call_args.args[0] == "https://pypi.org/pypi/a%20b/json"


def http_error(code):
    return urllib.error.HTTPError("https://pypi.org", code, "nope", {}, None)


def test_fetch_pypi_info_no_such_package():
    urlopen = mock.MagicMock(side_effect=http_error(404))
    assert plugin_env.fetch_pypi_info("nu-nothing", urlopen=urlopen) is None


def test_fetch_pypi_info_cant_reach_pypi():
    with pytest.raises(urllib.error.HTTPError):
        plugin_env.fetch_pypi_info(
            "x", urlopen=mock.MagicMock(side_effect=http_error(503))
        )
    with pytest.raises(OSError):
        plugin_env.fetch_pypi_info(
            "x", urlopen=mock.MagicMock(side_effect=urllib.error.URLError("offline"))
        )


def test_fetch_pypi_info_not_json():
    urlopen = mock.MagicMock(return_value=io.BytesIO(b"<html>"))
    with pytest.raises(OSError, match="can't read"):
        plugin_env.fetch_pypi_info("x", urlopen=urlopen)


def test_fetch_pypi_info_uses_urllib():
    with mock.patch("urllib.request.urlopen", pypi({})) as urlopen:
        plugin_env.fetch_pypi_info("x")
    urlopen.assert_called_once()


# --- the environment and its manifest ---


def test_paths(env, tmp_path):
    data = str(tmp_path / "data")
    assert env.path == os.path.join(data, "plugin-env")
    assert env.manifest_path == os.path.join(data, "plugin-env.json")
    assert env.excludes_path == os.path.join(env.path, "nu-provides.txt")
    assert env.interpreter.startswith(env.path)
    assert env.site_packages().startswith(env.path)
    assert env.site_packages().endswith("site-packages")


def test_default_data_dir():
    from mu import config

    assert PluginEnvironment().path == os.path.join(config.DATA_DIR, "plugin-env")


def test_manifest_empty(env):
    assert env.manifest() == {"python": None, "plugins": []}
    assert env.added() == []


@pytest.mark.parametrize(
    "content",
    ["not json", "[1, 2]", '{"plugins": "nope"}', '{"plugins": [1, {"x": 1}]}'],
)
def test_manifest_unreadable(env, content):
    os.makedirs(os.path.dirname(env.manifest_path), exist_ok=True)
    with open(env.manifest_path, "w") as f:
        f.write(content)
    assert env.manifest()["plugins"] == []


def test_manifest_records(env):
    env.record_python()
    env.record_added("Nu_Cows", requirement="nu-cows>=1")
    env.record_added("nu-example", wheel="/w/nu_example-1-py3-none-any.whl")
    env.record_added("nu-plain")
    assert env.manifest() == {
        "python": PY,
        "plugins": [
            {"name": "nu-cows", "requirement": "nu-cows>=1"},
            {"name": "nu-example", "wheel": "/w/nu_example-1-py3-none-any.whl"},
            {"name": "nu-plain", "requirement": "nu-plain"},
        ],
    }
    assert env.installed_from_file("NU_example")
    assert not env.installed_from_file("nu-cows")
    # Adding again replaces it.
    env.record_added("nu-cows", wheel="/w/c.whl")
    assert env.added()[-1] == {"name": "nu-cows", "wheel": "/w/c.whl"}
    env.record_removed("Nu.Cows")
    assert [p["name"] for p in env.added()] == ["nu-example", "nu-plain"]


def test_status(env):
    assert env.status() == MISSING
    assert env.python() is None
    make_env(env)
    assert env.status() == READY
    assert env.python() == PY
    make_env(env, version="2.7")
    assert env.status() == PYTHON_CHANGED


def test_status_from_the_manifest(env):
    """Without a version in pyvenv.cfg, the manifest says."""
    make_env(env)
    os.remove(os.path.join(env.path, "pyvenv.cfg"))
    assert env.status() == READY
    env._write_manifest({"python": "2.7", "plugins": []})
    assert env.python() == "2.7"
    assert env.status() == PYTHON_CHANGED


def test_add_to_sys_path(env):
    make_env(env)
    directory = env.site_packages()
    try:
        with mock.patch("site.addsitedir") as addsitedir:
            assert env.add_to_sys_path() == READY
        addsitedir.assert_called_once_with(directory)
        assert env.on_sys_path
        # Already there: not added twice.
        sys.path.append(directory)
        with mock.patch("site.addsitedir") as addsitedir:
            env.add_to_sys_path()
        addsitedir.assert_not_called()
    finally:
        while directory in sys.path:
            sys.path.remove(directory)


def test_add_to_sys_path_appends_after_nu(env):
    """The real thing: the plugin environment comes after Nu's own paths."""
    make_env(env)
    before = list(sys.path)
    try:
        env.add_to_sys_path()
        assert sys.path[: len(before)] == before
        assert sys.path[-1] == env.site_packages()
    finally:
        sys.path[:] = before


def test_add_to_sys_path_missing(env):
    with mock.patch("site.addsitedir") as addsitedir:
        assert env.add_to_sys_path() == MISSING
    addsitedir.assert_not_called()
    assert not env.on_sys_path


def test_add_to_sys_path_python_changed(env, caplog):
    make_env(env, version="2.7")
    with mock.patch("site.addsitedir") as addsitedir:
        assert env.add_to_sys_path() == PYTHON_CHANGED
    addsitedir.assert_not_called()
    assert not env.on_sys_path
    assert "installed for Python 2.7 and Nu now runs on Python" in caplog.text


# --- what's in it ---


def test_distribution_and_contains(env):
    make_env(env)
    write_dist(env.site_packages(), "nu-cows", "2.0")
    dist = env.distribution("Nu_Cows")
    assert dist.version == "2.0"
    assert env.contains(dist)
    assert env.distribution("nu-other") is None
    outside = mock.MagicMock()
    outside.locate_file.return_value = "/elsewhere"
    assert not env.contains(outside)
    odd = mock.MagicMock()
    odd.locate_file.side_effect = NotImplementedError
    assert not env.contains(odd)


def test_distribution_skips_nameless(env):
    make_env(env)
    nameless = os.path.join(env.site_packages(), "odd-1.0.dist-info")
    os.makedirs(nameless)
    with open(os.path.join(nameless, "METADATA"), "w") as f:
        f.write("Metadata-Version: 2.1\n")
    assert env.distribution("odd") is None


def test_nu_distributions(env):
    """Everything Nu's process has, except what's in the plugin environment."""
    make_env(env)
    write_dist(env.site_packages(), "nu-cows")
    nameless = mock.MagicMock()
    nameless.metadata = {"Name": None}
    ours = env.distribution("nu-cows")
    pyqt = mock.MagicMock()
    pyqt.metadata = {"Name": "PyQt6"}
    pyqt.version = "6.9.0"
    pyqt.locate_file.return_value = "/nu/site-packages"
    again = mock.MagicMock()
    again.metadata = {"Name": "pyqt6"}
    again.version = "1.0"
    again.locate_file.return_value = "/elsewhere"
    with mock.patch(
        "importlib.metadata.distributions", return_value=[nameless, ours, pyqt, again]
    ):
        assert env.nu_distributions() == {"pyqt6": "6.9.0"}


def test_nu_distributions_real(env):
    """Nu's own process really has PyQt6."""
    assert "pyqt6" in env.nu_distributions()


def test_write_excludes(env):
    with mock.patch.object(
        env, "nu_distributions", return_value={"pyqt6": "6.9", "black": "24"}
    ):
        path = env.write_excludes()
    with open(path) as f:
        assert f.read().split() == ["black", "mu-editor", "nu-editor", "pyqt6"]


def test_problems_with_a_good_plugin(env):
    make_env(env)
    write_dist(
        env.site_packages(),
        "nu-cows",
        requires=[
            "PyQt6>=6.6",
            "nu-editor>=2.0.0b1",
            "cowsay>=6",  # not Nu's: in the plugin environment
            'pywin32; sys_platform == "nonesuch"',
            'pytest; extra == "test"',
            "black>=nonsense",  # unreadable: ignored
            "qtconsole>=5",
        ],
    )
    provided = {"pyqt6": "6.9.0", "qtconsole": "not-a-version"}
    assert env.problems_with(env.distribution("nu-cows"), provided) == []


def test_problems_with_a_plugin_that_cant_be_used(env):
    make_env(env)
    write_dist(
        env.site_packages(),
        "nu-cows",
        requires=["PyQt6>=99", "nu-editor>=99"],
        plugin=False,
    )
    with mock.patch.object(env, "nu_distributions", return_value={"pyqt6": "6.9.0"}):
        problems = env.problems_with(env.distribution("nu-cows"))
    assert problems == [
        "nu-cows isn't a Nu plugin: it doesn't say it adds anything to Nu.",
        "It needs PyQt6>=99, but Nu has pyqt6 6.9.0.",
        "It needs nu-editor>=99, but Nu has nu-editor {}.".format(nu_version),
    ]


def test_problems_with_no_requirements(env):
    dist = mock.MagicMock()
    dist.entry_points = [SimpleNamespace(group="mu.plugins")]
    dist.requires = None
    assert env.problems_with(dist, {}) == []


# --- jobs ---


def job_kwargs(environment, packages=None, fail=(), learner=False, learner_fail=()):
    uvs = FakeUvs(Behaviour(environment, packages, fail))
    kwargs = {"uv": uvs}
    if learner:
        learner_uvs = FakeUvs(Behaviour(environment, fail=learner_fail))
        kwargs["learner_uv"] = lambda: learner_uvs(venv_path="/learner/bin/python")
    return kwargs


def test_add_by_name_makes_the_environment(env):
    """
    The first plugin makes the environment with Nu's Python, then installs
    it without anything Nu has; it's recorded, and loads at the next start.
    """
    requirement = plugin_env.parse_requirement("nu-cows>=1")
    kwargs = job_kwargs(env, {"nu-cows>=1": ("nu-cows", "1.2", [], True)})
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    excludes = env.excludes_path
    assert job.preview == [
        "$ uv venv --python {} {}".format(plugin_env.nu_python(), env.path),
        "$ uv pip install --python {} --excludes {} 'nu-cows>=1'".format(
            env.interpreter, excludes
        ),
    ]
    lines = run(job)
    calls = kwargs["uv"].calls
    assert calls == [
        (["venv", "--python", plugin_env.nu_python(), env.path], None),
        (
            ["pip", "install", "--python", env.interpreter, "--excludes"]
            + [excludes, "nu-cows>=1"],
            env.interpreter,
        ),
    ]
    assert "$ uv venv --python {} {}".format(plugin_env.nu_python(), env.path) in lines
    assert "uv says hello" in lines
    assert job.succeeded and job.changed
    assert job.messages == ["Added nu-cows 1.2."]
    assert env.manifest() == {
        "python": PY,
        "plugins": [{"name": "nu-cows", "requirement": "nu-cows>=1"}],
    }
    with open(excludes) as f:
        assert "pyqt6" in f.read().split()
    assert job.process is None


def test_add_from_a_file(env, tmp_path):
    """A wheel file goes in by its path; the environment is already there."""
    make_env(env)
    wheel = tmp_path / "nu_cows-1.0-py3-none-any.whl"
    wheel.write_text("")
    kwargs = job_kwargs(env, {str(wheel): ("nu-cows", "1.0", [], True)})
    job = plugin_env.add_job(env, wheel=str(wheel), **kwargs)
    assert len(job.preview) == 1
    run(job)
    assert [c[0][0] for c in kwargs["uv"].calls] == ["pip"]
    assert job.messages == ["Added nu-cows 1.0."]
    assert env.added() == [{"name": "nu-cows", "wheel": str(wheel)}]
    assert env.installed_from_file("nu-cows")


def test_add_that_isnt_a_plugin_is_removed_again(env):
    make_env(env)
    requirement = plugin_env.parse_requirement("cowsay")
    kwargs = job_kwargs(env, {"cowsay": ("cowsay", "6.1", [], False)}, learner=True)
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    lines = run(job)
    assert not job.succeeded and not job.changed
    assert job.messages == [
        "Nu can't use cowsay, so it's removing it again:",
        "  cowsay isn't a Nu plugin: it doesn't say it adds anything to Nu.",
    ]
    assert kwargs["uv"].calls[-1][0] == [
        "pip",
        "uninstall",
        "--python",
        env.interpreter,
        "cowsay",
    ]
    assert env.distribution("cowsay") is None
    assert env.added() == []
    assert any(line.startswith("$ uv pip uninstall") for line in lines)


def test_add_that_needs_another_pyqt_is_removed_again(env):
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    kwargs = job_kwargs(env, {"nu-cows": ("nu-cows", "1", ["PyQt6>=99"], True)})
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    with mock.patch.object(env, "nu_distributions", return_value={"pyqt6": "6.9.0"}):
        run(job)
    assert not job.succeeded and not job.changed
    assert job.messages[-1] == "  It needs PyQt6>=99, but Nu has pyqt6 6.9.0."
    assert env.distribution("nu-cows") is None


def test_add_when_the_install_fails(env):
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-nothing")
    kwargs = job_kwargs(env, fail={"nu-nothing"})
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    run(job)
    assert not job.succeeded and not job.changed
    assert job.messages == ["Nu couldn't install nu-nothing (see above)."]
    assert len(kwargs["uv"].calls) == 1


def test_add_when_uv_installs_something_else(env):
    """If the package isn't there afterwards (it had another name), say so."""
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    kwargs = job_kwargs(env, {"nu-cows": ("nu-other", "1", [], True)})
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    run(job)
    assert job.messages == ["Nu installed nu-cows but can't find it now."]
    assert not job.succeeded


def test_add_when_the_environment_cant_be_made(env):
    requirement = plugin_env.parse_requirement("nu-cows")
    kwargs = job_kwargs(env, fail={"venv " + "--python"})
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    run(job)
    assert job.messages == ["Nu couldn't make the plugin environment."]
    assert len(kwargs["uv"].calls) == 1
    assert env.manifest()["python"] is None


def test_add_when_uv_venv_says_ok_but_made_nothing(env):
    requirement = plugin_env.parse_requirement("nu-cows")
    uvs = FakeUvs()  # succeeds, does nothing
    job = plugin_env.add_job(env, requirement=requirement, uv=uvs)
    run(job)
    assert job.messages == ["Nu couldn't make the plugin environment."]


def test_add_with_learner_env_packages(env):
    """Its learner-env extra goes into the learner's environment."""
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    requires = ['cowsay>=6; extra == "learner-env"', 'moo; extra == "other"']
    kwargs = job_kwargs(
        env, {"nu-cows": ("nu-cows", "1", requires, True)}, learner=True
    )
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    lines = run(job)
    learner_calls = kwargs["learner_uv"]().owner.calls
    assert learner_calls == [
        (
            ["pip", "install", "--python", "/learner/bin/python", "cowsay>=6"],
            "/learner/bin/python",
        )
    ]
    assert "Adding the packages nu-cows needs to your Python environment…" in lines
    assert "$ uv pip install --python /learner/bin/python 'cowsay>=6'" in lines
    assert job.succeeded and job.changed


def test_add_with_learner_env_packages_failing(env):
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    requires = ['cowsay; extra == "learner-env"']
    kwargs = job_kwargs(
        env,
        {"nu-cows": ("nu-cows", "1", requires, True)},
        learner=True,
        learner_fail={"cowsay"},
    )
    job = plugin_env.add_job(env, requirement=requirement, **kwargs)
    run(job)
    assert job.changed and not job.succeeded
    assert job.messages[-1].startswith("Nu couldn't add cowsay to your Python")


def test_add_with_learner_env_packages_but_no_learner_env(env):
    """No learner environment yet: they're added when it's made."""
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    requires = ['cowsay; extra == "learner-env"']
    packages = {"nu-cows": ("nu-cows", "1", requires, True)}
    for kwargs in (
        job_kwargs(env, packages),
        dict(job_kwargs(env, packages), learner_uv=lambda: None),
    ):
        job = plugin_env.add_job(env, requirement=requirement, **kwargs)
        run(job)
        assert job.succeeded
        assert job.messages[-1] == (
            "It also needs cowsay for your programs; Nu will add them when it "
            "next makes your Python environment."
        )


def test_a_step_that_raises(env):
    """An unexpected error ends the job, saying what it was."""
    make_env(env)
    requirement = plugin_env.parse_requirement("nu-cows")
    job = plugin_env.add_job(env, requirement=requirement, uv=FakeUvs())
    with mock.patch.object(env, "write_excludes", side_effect=OSError("disk full")):
        run(job)
    assert job.messages == ["Something went wrong: disk full"]
    assert not job.succeeded


def test_update(env):
    """Update installs the latest of what the learner typed, with --upgrade."""
    make_env(env)
    env.record_added("nu-cows", requirement="nu-cows>=1")
    kwargs = job_kwargs(env, {"nu-cows>=1": ("nu-cows", "2.0", [], True)})
    job = plugin_env.update_job(env, "nu-cows", **kwargs)
    assert job.preview == [
        "$ uv pip install --upgrade --python {} --excludes {} 'nu-cows>=1'".format(
            env.interpreter, env.excludes_path
        )
    ]
    run(job)
    assert kwargs["uv"].calls[0][0][:3] == ["pip", "install", "--upgrade"]
    assert job.messages == ["Updated nu-cows: it's now version 2.0."]
    assert env.added() == [{"name": "nu-cows", "requirement": "nu-cows>=1"}]


def test_update_one_not_in_the_manifest(env):
    make_env(env)
    env.record_added("nu-other")
    kwargs = job_kwargs(env, {"nu-cows": ("nu-cows", "2.0", [], True)})
    job = plugin_env.update_job(env, "Nu_Cows", **kwargs)
    run(job)
    assert kwargs["uv"].calls[0][0][-1] == "nu-cows"
    assert job.succeeded


def test_remove(env):
    make_env(env)
    write_dist(env.site_packages(), "nu-cows")
    env.record_added("nu-cows")
    kwargs = job_kwargs(env)
    job = plugin_env.remove_job(env, "nu-cows", **kwargs)
    assert job.preview == [
        "$ uv pip uninstall --python {} nu-cows".format(env.interpreter)
    ]
    run(job)
    assert job.succeeded and job.changed
    assert job.messages == ["Removed nu-cows. It's gone the next time you start Nu."]
    assert env.added() == []
    assert env.distribution("nu-cows") is None


def test_remove_fails(env):
    make_env(env)
    env.record_added("nu-cows")
    kwargs = job_kwargs(env, fail={"pip uninstall"})
    job = plugin_env.remove_job(env, "nu-cows", **kwargs)
    run(job)
    assert not job.succeeded and not job.changed
    assert job.messages == ["Nu couldn't remove nu-cows (see above)."]
    assert env.added() == [{"name": "nu-cows", "requirement": "nu-cows"}]


def test_reinstall(env, tmp_path):
    """
    After Nu moved to a new Python, the environment is made again and every
    plugin added again; one from a file that's gone is reported and
    forgotten, not fatal.
    """
    make_env(env, version="2.7")
    write_dist(env.site_packages(), "stale")
    wheel = tmp_path / "nu_file-1.0-py3-none-any.whl"
    wheel.write_text("")
    env.record_added("nu-cows", requirement="nu-cows>=1")
    env.record_added("nu-file", wheel=str(wheel))
    env.record_added("nu-gone", wheel=str(tmp_path / "gone.whl"))
    env._write_manifest(dict(env.manifest(), python="2.7"))
    kwargs = job_kwargs(
        env,
        {
            "nu-cows>=1": ("nu-cows", "1.5", [], True),
            str(wheel): ("nu-file", "1.0", [], True),
        },
    )
    job = plugin_env.reinstall_job(env, **kwargs)
    assert job.preview[0].startswith("$ uv venv --python")
    assert len(job.preview) == 3
    lines = run(job)
    assert lines[0] == "Removing the old plugin environment…"
    assert env.status() == READY
    assert env.distribution("stale") is None
    assert env.distribution("nu-cows").version == "1.5"
    assert job.changed and not job.succeeded
    assert job.messages[:2] == ["Added nu-cows 1.5.", "Added nu-file 1.0."]
    assert job.messages[2].startswith("Nu couldn't add nu-gone again")
    assert env.manifest()["python"] == PY
    assert [p["name"] for p in env.added()] == ["nu-cows", "nu-file"]


def test_reinstall_carries_on_after_a_failure(env):
    make_env(env, version="2.7")
    env.record_added("nu-broken")
    env.record_added("nu-cows")
    kwargs = job_kwargs(
        env, {"nu-cows": ("nu-cows", "1", [], True)}, fail={"nu-broken"}
    )
    job = plugin_env.reinstall_job(env, **kwargs)
    run(job)
    assert job.messages == [
        "Nu couldn't install nu-broken (see above).",
        "Added nu-cows 1.",
    ]
    assert job.changed


def test_the_singleton_is_isolated_in_tests(temp_plugin_env):
    """conftest gives each test its own (missing) plugin environment."""
    assert plugin_env.plugin_env is temp_plugin_env
    assert plugin_env.plugin_env.status() == MISSING
