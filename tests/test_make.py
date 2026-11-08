# -*- coding: utf-8 -*-
"""
Tests for make.py's packaging commands (dist, publish_test, publish_live).
Nothing is built or uploaded: subprocess.run is mocked.
"""

import os
import sys
from unittest import mock

import pytest

import make


def _run_ok(returncode=0):
    return mock.patch(
        "make.subprocess.run", return_value=mock.MagicMock(returncode=returncode)
    )


def _commands(run):
    return [call.args[0] for call in run.call_args_list]


def test_dist_builds_nu_editor_and_the_bundled_plugins():
    """dist builds nu-editor, then the two bundled plugins, into dist/."""
    with mock.patch("make.check", return_value=0), _run_ok() as run:
        assert make.dist() == 0
    build = [sys.executable, "-m", "build", "--outdir", "dist"]
    assert _commands(run) == [
        build + ["."],
        build + ["plugins/pygamezero"],
        build + ["plugins/circuitpython"],
    ]


def test_dist_leaves_out_the_opt_in_and_example_plugins():
    """Neither plugins/microbit nor plugins/example is built or published."""
    assert make.BUNDLED_PLUGINS == ["plugins/pygamezero", "plugins/circuitpython"]


def test_dist_stops_at_the_first_failed_build():
    with mock.patch("make.check", return_value=0), _run_ok(1) as run:
        assert make.dist() == 1
    assert run.call_count == 1


def test_dist_refuses_when_the_checks_fail():
    with mock.patch("make.check", return_value=1), _run_ok() as run:
        with pytest.raises(RuntimeError):
            make.dist()
    run.assert_not_called()


@pytest.mark.parametrize(
    "publish, repository",
    [(make.publish_live, []), (make.publish_test, ["-r", "test"])],
)
def test_publish_uploads_the_plugins_before_nu_editor(publish, repository):
    """
    The plugins go up first (skipping a version PyPI already has), then
    nu-editor, which depends on them. Nothing is signed: PyPI no longer
    accepts PGP signatures.
    """
    with mock.patch("make.dist", return_value=0), _run_ok() as run:
        assert publish() == 0
    twine = [sys.executable, "-m", "twine", "upload", *repository]
    assert _commands(run) == [
        twine
        + [
            "--skip-existing",
            os.path.join("dist", "nu_pygamezero-*"),
            os.path.join("dist", "nu_circuitpython-*"),
        ],
        twine + [os.path.join("dist", "nu_editor-*")],
    ]
    assert not any("--sign" in command for command in _commands(run))


def test_publish_uploads_nothing_when_the_build_fails():
    with mock.patch("make.dist", return_value=1), _run_ok() as run:
        assert make.publish_live() == 1
    run.assert_not_called()


def test_publish_stops_if_a_plugin_upload_fails():
    """nu-editor isn't uploaded when its plugins didn't make it."""
    with mock.patch("make.dist", return_value=0), _run_ok(1) as run:
        assert make.publish_live() == 1
    assert run.call_count == 1
