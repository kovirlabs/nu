# -*- coding: utf-8 -*-
"""
Tests for the packages the learner's environment is built with (mu.wheels):
the core's own list plus what installed plugins declare.
"""

import logging
from types import SimpleNamespace
from unittest import mock

import pytest

import mu.wheels
from mu.plugin import loader


def dist(name, *requires):
    return SimpleNamespace(name=name, requires=list(requires) or None)


def entry_points_for(*dists):
    """A stand-in for importlib.metadata.entry_points over `dists`."""

    def entry_points(group):
        assert group == mu.wheels.PLUGIN_ENTRY_POINT_GROUP
        return [SimpleNamespace(dist=d) for d in dists]

    return entry_points


def test_plugin_entry_point_group_matches_the_loader():
    """
    mu.wheels can't import mu.plugin (it needs Qt, and the installer build
    runs mu.wheels without it), so it keeps its own copy of the group name.
    """
    assert mu.wheels.PLUGIN_ENTRY_POINT_GROUP == loader.ENTRY_POINT_GROUP


def test_learner_env_requirements():
    """
    Only requirements under the learner-env extra count, without their
    marker; plain dependencies and other extras are ignored.
    """
    pgz = dist(
        "nu-pygamezero",
        "pgzero>=1.2.1; extra == 'learner-env'",
        'pygame>=2.6 ; extra == "learner-env"',
        "requests",
        "pytest; extra == 'tests'",
        "colorama; python_version >= '3'",
    )
    assert mu.wheels.learner_env_requirements(pgz) == ["pgzero>=1.2.1", "pygame>=2.6"]


def test_learner_env_requirements_honours_platform_markers():
    """
    A learner-env requirement for another platform is left out: the wheels
    are fetched for, and installed on, the platform Nu runs on.
    """
    plugin = dist(
        "nu-thing",
        "pywin32; sys_platform == 'nonexistent-os' and extra == 'learner-env'",
        "thing; sys_platform != 'nonexistent-os' and extra == 'learner-env'",
    )
    assert mu.wheels.learner_env_requirements(plugin) == ["thing"]


def test_learner_env_requirements_without_any():
    assert mu.wheels.learner_env_requirements(dist("nu-plain")) == []


def test_learner_env_requirements_skips_unreadable_ones(caplog):
    plugin = dist("nu-odd", "not a requirement!!", "ok; extra == 'learner-env'")
    with caplog.at_level(logging.WARNING):
        assert mu.wheels.learner_env_requirements(plugin) == ["ok"]
    assert "not a requirement!!" in caplog.text


def test_plugin_packages():
    """
    Each installed plugin distribution with learner-env requirements gives
    one entry, named after the distribution. A distribution with several
    plugins counts once; plugins without metadata (or needs) add nothing.
    """
    pgz = dist("nu-pygamezero", "pgzero>=1.2.1; extra == 'learner-env'")
    plain = dist("nu-plain")
    entry_points = entry_points_for(pgz, pgz, plain, None)
    assert mu.wheels.plugin_packages(entry_points) == [
        ("nu-pygamezero", ("pgzero>=1.2.1",))
    ]


def test_baseline_packages_is_core_then_plugins():
    plugin = ("nu-pygamezero", ("pgzero>=1.2.1",))
    with mock.patch.object(mu.wheels, "plugin_packages", return_value=[plugin]):
        assert mu.wheels.baseline_packages() == mu.wheels.mode_packages + [plugin]


def test_core_packages_are_only_the_cores_own():
    """
    The core's list is what Nu itself needs in the learner's environment
    (the REPL's kernel); modes' packages come from their plugins.
    """
    assert [name for name, *_ in mu.wheels.mode_packages] == ["ipykernel"]


@pytest.fixture
def pip_runs():
    ok = SimpleNamespace(returncode=0, stdout=b"done")
    with mock.patch("mu.wheels.subprocess.run", return_value=ok) as run:
        yield run


def test_pip_download_fetches_the_baseline_packages(pip_runs, tmp_path):
    """
    By default the wheelhouse gets the core's packages and every installed
    plugin's, so bundled plugins work offline too.
    """
    packages = [("a", ("a>=1",)), ("nu-b", ("b", "c<2"))]
    with mock.patch.object(mu.wheels, "baseline_packages", return_value=packages):
        mu.wheels.pip_download(str(tmp_path), logging.getLogger("test"))
    downloaded = [
        call.args[0][-len(specs) :]
        for call, (_, specs) in zip(pip_runs.call_args_list, packages)
    ]
    assert downloaded == [["a>=1"], ["b", "c<2"]]


def test_pip_download_given_packages(pip_runs, tmp_path):
    mu.wheels.pip_download(
        str(tmp_path), logging.getLogger("test"), packages=[("x", ("x==1",))]
    )
    assert pip_runs.call_count == 1
    assert pip_runs.call_args.args[0][-1] == "x==1"


def test_pip_download_failure(tmp_path):
    failed = SimpleNamespace(returncode=1, stdout=b"nope")
    with mock.patch("mu.wheels.subprocess.run", return_value=failed):
        with pytest.raises(mu.wheels.WheelsDownloadError, match="x==1"):
            mu.wheels.pip_download(
                str(tmp_path), logging.getLogger("test"), packages=[("x", ("x==1",))]
            )
