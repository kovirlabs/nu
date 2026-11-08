# -*- coding: utf-8 -*-
"""
Tests for the learner's named environments (Phase 4b part 2): the registry
(default + the folders in ``config.ENVS_DIR``), making one the way the
default is made, and switching between them from the next start.
"""

import os
import sys
from unittest import mock

import pytest

import mu
import mu.config
import mu.settings
import mu.virtual_environment
import mu.wheels

VE = mu.virtual_environment.VirtualEnvironment
VEError = mu.virtual_environment.VirtualEnvironmentError
CreateError = mu.virtual_environment.VirtualEnvironmentCreateError
EnsureError = mu.virtual_environment.VirtualEnvironmentEnsureError
UV = mu.virtual_environment.Uv


def make_env(path, version="3.11.15", home="/x"):
    """A folder that looks like an environment (it has a pyvenv.cfg)."""
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "pyvenv.cfg"), "w", encoding="utf-8") as cfg:
        cfg.write("home = %s\nversion_info = %s\n" % (home, version))
    return path


@pytest.fixture
def data_dir(tmp_path):
    """Nu's data folder, and so ENVS_DIR and VENV_DIR, in a temporary one."""
    data = tmp_path / "data"
    data.mkdir()
    with (
        mock.patch.object(mu.config, "DATA_DIR", str(data)),
        mock.patch.object(mu.config, "ENVS_DIR", str(data / "envs")),
        mock.patch.object(mu.config, "VENV_DIR", str(data / "mu_venv")),
    ):
        yield data


@pytest.fixture
def default_path(data_dir):
    return make_env(str(data_dir / "mu_venv-311-20261108-030353"))


@pytest.fixture
def venv(default_path):
    """The environment Nu uses: the default one, with venv.json not saved."""
    venv = VE(default_path, persist=False)
    venv.settings["mu_version"] = mu.__version__
    yield venv


#
# Module helpers
#
def test_same_path(tmp_path):
    assert mu.virtual_environment.same_path(str(tmp_path), str(tmp_path / "a" / ".."))
    assert not mu.virtual_environment.same_path(str(tmp_path), str(tmp_path / "a"))


def test_is_named_environment(data_dir):
    envs = mu.config.ENVS_DIR
    assert mu.virtual_environment.is_named_environment(os.path.join(envs, "a"))
    assert not mu.virtual_environment.is_named_environment(envs)
    assert not mu.virtual_environment.is_named_environment(os.path.join(envs, "a", "b"))
    assert not mu.virtual_environment.is_named_environment(
        os.path.join(str(data_dir), "mu_venv-311-20261108-030353")
    )


def test_environment_interpreter():
    interpreter = mu.virtual_environment.environment_interpreter
    assert interpreter("e", windows=False) == os.path.join("e", "bin", "python")
    assert interpreter("e", windows=True) == os.path.join("e", "scripts", "python.exe")
    with mock.patch.object(sys, "platform", "win32"):
        assert interpreter("e").endswith("python.exe")


def test_directory_is_venv(tmp_path):
    is_venv = mu.virtual_environment.directory_is_venv
    assert is_venv(make_env(str(tmp_path / "cfg")))
    # No pyvenv.cfg, but an executable python where expected.
    bin_dir = tmp_path / "exe" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    python.write_text("")
    python.chmod(0o755)
    with mock.patch.object(sys, "platform", "linux"):
        assert is_venv(str(tmp_path / "exe"))
    assert not is_venv(str(tmp_path))


def test_environment_display_name():
    name = mu.virtual_environment.environment_display_name
    assert name("mu_venv-311-20261108-030353") == "mu_venv"
    assert name("project-a") == "project-a"


#
# The registry
#
def test_relocate_remembers_the_default(venv, data_dir, default_path):
    """The default's folder is remembered, a named one's isn't."""
    assert venv.settings["default_dirpath"] == default_path
    named = os.path.join(mu.config.ENVS_DIR, "project-a")
    venv.relocate(named)
    assert venv.settings["dirpath"] == named
    assert venv.settings["default_dirpath"] == default_path


def test_default_dirpath_from_settings(venv, data_dir):
    venv.settings["default_dirpath"] = "/somewhere/mu_venv-311-1-1"
    assert venv.default_dirpath() == "/somewhere/mu_venv-311-1-1"


def test_default_dirpath_is_this_one(venv, default_path):
    del venv.settings["default_dirpath"]
    assert venv.default_dirpath() == default_path


def test_default_dirpath_found_when_not_remembered(data_dir):
    """A named one in use and no default_dirpath (an older venv.json): the
    newest default folder, not a moved-aside one."""
    older = make_env(str(data_dir / "mu_venv-311-20250101-000000"))
    newer = make_env(str(data_dir / "mu_venv-311-20261108-030353"))
    make_env(str(data_dir / "mu_venv-311-20271108-030353.FAILED"))
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    venv = VE(named, persist=False)
    assert "default_dirpath" not in venv.settings
    assert venv.default_dirpath() == newer
    assert older != newer


def test_default_dirpath_none(data_dir):
    venv = VE(os.path.join(mu.config.ENVS_DIR, "project-a"), persist=False)
    assert venv.default_dirpath() is None


def test_named_environment_paths(venv, data_dir):
    """Every valid-named folder in ENVS_DIR that's an environment, by name,
    including one made by hand; not moved-aside or other folders."""
    envs = mu.config.ENVS_DIR
    b = make_env(os.path.join(envs, "B-project"))
    a = make_env(os.path.join(envs, "a_project"))
    make_env(os.path.join(envs, "a_project.FAILED"))
    make_env(os.path.join(envs, "has space"))
    os.makedirs(os.path.join(envs, "not-an-env"))
    open(os.path.join(envs, "notes"), "w").close()
    assert venv.named_environment_paths() == [a, b]


def test_named_environment_paths_no_folder(venv):
    assert venv.named_environment_paths() == []


def test_list_environments(venv, default_path):
    """Default first, then the named ones, with what the tab shows."""
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"), "3.11.9")
    venv.settings["dirpath"] = named
    assert venv.list_environments() == [
        {
            "name": "mu_venv",
            "path": default_path,
            "python_version": "3.11.15",
            "default": True,
            "in_use": True,
            "next_start": False,
        },
        {
            "name": "project-a",
            "path": named,
            "python_version": "3.11.9",
            "default": False,
            "in_use": False,
            "next_start": True,
        },
    ]


def test_list_environments_without_a_default(data_dir):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    venv = VE(named, persist=False)
    with mock.patch.object(venv, "default_dirpath", return_value=None):
        environments = venv.list_environments()
    assert [env["name"] for env in environments] == ["project-a"]
    assert environments[0]["in_use"] and environments[0]["next_start"]


@pytest.mark.parametrize(
    "name, problem",
    [
        ("", "Please give the environment a name."),
        ("my project", "Please use only letters"),
        ("../x", "Please use only letters"),
        ("é", "Please use only letters"),
        ("x" * 41, "shorter name (40 characters at most)"),
        ("NUL", "can't be a folder's name on Windows"),
        ("com1", "can't be a folder's name on Windows"),
        ("Project-A", "There's already an environment called “Project-A”"),
        ("MU_VENV", "There's already an environment called “MU_VENV”"),
        ("leftover", "There's already an environment called “leftover”"),
    ],
)
def test_environment_name_problem(venv, name, problem):
    make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    os.makedirs(os.path.join(mu.config.ENVS_DIR, "leftover"))
    assert problem in venv.environment_name_problem(name)


def test_environment_name_ok(venv):
    """Fine names, including when there's no envs folder yet."""
    for name in ("project-a", "Game_2", "x" * 40):
        assert venv.environment_name_problem(name) is None


#
# Making one
#
def test_create_environment(venv, data_dir):
    """Made in ENVS_DIR the same way as the default (`create`), checked
    (`ensure`), reporting progress; venv.json is left alone."""
    lines = []
    made = []

    def create(self):
        made.append(self)
        os.makedirs(self.path)

    with (
        mock.patch.object(VE, "create", create),
        mock.patch.object(VE, "ensure") as ensure,
    ):
        path = venv.create_environment("project-a", progress=lines.append)
    assert path == os.path.join(mu.config.ENVS_DIR, "project-a")
    environment = made[0]
    assert environment is not venv
    assert environment.path == path
    assert environment.progress == lines.append
    assert environment.settings.filepath is None  # not venv.json
    ensure.assert_called_once_with()
    assert venv.settings["dirpath"] == venv.path  # not switched


def test_create_environment_bad_name(venv):
    with (
        mock.patch.object(VE, "create") as create,
        pytest.raises(CreateError, match="Please use only letters"),
    ):
        venv.create_environment("my project")
    create.assert_not_called()


@pytest.mark.parametrize(
    "error, reason",
    [
        (CreateError("uv failed"), "uv failed"),
        (OSError("disk full"), "disk full"),
    ],
)
def test_create_environment_fails(venv, error, reason):
    """The half-made folder goes and the learner gets a plain message."""

    def create(self):
        os.makedirs(os.path.join(self.path, "bin"))
        raise error

    with (
        mock.patch.object(VE, "create", create),
        pytest.raises(CreateError) as exc_info,
    ):
        venv.create_environment("project-a")
    message = exc_info.value.message
    assert message.startswith("Nu couldn't make the environment “project-a”.")
    assert reason in message
    assert not os.path.exists(os.path.join(mu.config.ENVS_DIR, "project-a"))


def test_create_environment_fails_before_the_folder(venv):
    with (
        mock.patch.object(VE, "create", side_effect=CreateError("no uv")),
        pytest.raises(CreateError, match="no uv"),
    ):
        venv.create_environment("project-a")


def test_create_reports_progress(venv):
    """The steps of `create` are reported, when asked."""
    lines = []
    venv.progress = lines.append
    with (
        mock.patch.object(venv, "create_venv"),
        mock.patch.object(venv, "install_baseline_packages"),
        mock.patch.object(venv, "register_baseline_packages"),
        mock.patch.object(venv, "install_jupyter_kernel"),
    ):
        venv.create()
    assert lines == ["Adding Nu's packages…", "Setting up the REPL for it…"]


def test_create_without_progress(venv):
    """Nothing is reported for the environment made at start (no progress)."""
    with (
        mock.patch.object(venv, "create_venv"),
        mock.patch.object(venv, "install_baseline_packages"),
        mock.patch.object(venv, "register_baseline_packages"),
        mock.patch.object(venv, "install_jupyter_kernel"),
    ):
        venv.create()
    assert venv.progress is None


def test_create_venv_reports_the_command(venv):
    """The learner sees the `uv venv` command first, then what uv said."""
    lines = []
    venv.progress = lines.append
    with (
        mock.patch.object(mu.virtual_environment, "find_uv", return_value="/opt/uv"),
        mock.patch.object(venv, "ensure_bundled_python", return_value=None),
        mock.patch.object(
            UV, "run_subprocess", return_value=(True, "Using CPython 3.11\n")
        ),
        mock.patch.object(mu.virtual_environment.sys, "platform", "linux"),
    ):
        venv.create_venv()
    version = "%d.%d" % sys.version_info[:2]
    assert lines[0] == "$ " + mu.virtual_environment.quote_command(
        ["uv", "venv", "--python", version, "--seed", venv.path]
    )
    assert lines[1] == "Using CPython 3.11"


def test_install_from_zipped_wheels_reports_each(venv, tmp_path):
    import zipfile

    archive = str(tmp_path / "wheels.zip")
    with zipfile.ZipFile(archive, "w") as zip:
        zip.writestr("arrr-1.0-py3-none-any.whl", b"")
    lines = []
    venv.progress = lines.append
    with mock.patch.object(mu.virtual_environment, "Pip"):
        venv.install_from_zipped_wheels(archive)
    assert lines == ["Installing arrr-1.0-py3-none-any.whl"]


#
# Switching
#
def test_check_environment_not_an_environment(venv, tmp_path):
    assert "isn't a Python environment" in venv.check_environment(str(tmp_path))
    missing = str(tmp_path / "missing")
    assert "isn't a Python environment" in venv.check_environment(missing)


def test_check_environment_fails_the_checks(venv):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    with mock.patch.object(VE, "ensure", side_effect=EnsureError("No pip.")):
        assert venv.check_environment(named) == "Nu can't use it: No pip."


def test_check_environment_ok(venv):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    with mock.patch.object(VE, "ensure") as ensure:
        assert venv.check_environment(named) is None
    ensure.assert_called_once_with()


def test_switch_environment(venv):
    """From the next start: venv.json's dirpath changes (and is saved); the
    running Nu keeps its environment."""
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    in_use = venv.path
    with (
        mock.patch.object(venv, "check_environment", return_value=None),
        mock.patch.object(venv.settings, "save") as save,
    ):
        assert venv.switch_environment(named) is None
    assert venv.settings["dirpath"] == named
    save.assert_called_once_with()
    assert venv.path == in_use
    assert [env["next_start"] for env in venv.list_environments()] == [False, True]


def test_switch_environment_refused(venv):
    named = os.path.join(mu.config.ENVS_DIR, "project-a")
    with mock.patch.object(venv.settings, "save") as save:
        problem = venv.switch_environment(named)
    assert "isn't a Python environment" in problem
    assert venv.settings["dirpath"] == venv.path
    save.assert_not_called()


def test_switch_back_to_the_default(venv, default_path):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    with (
        mock.patch.object(venv, "check_environment", return_value=None),
        mock.patch.object(venv.settings, "save"),
    ):
        venv.switch_environment(named)
        venv.switch_environment(default_path)
    assert venv.settings["dirpath"] == default_path


def test_next_start_uses_a_switched_environment(data_dir, default_path):
    """
    At the next start the venv.json written by a switch makes Nu use the
    named environment; `ensure_and_create` finds it healthy and neither
    creates, recreates nor moves anything.
    """
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    venv_json = str(data_dir / "venv.json")
    with mock.patch.object(
        mu.settings.SettingsBase,
        "default_file_locations",
        return_value=[str(data_dir)],
    ):
        first = VE()
        first.settings.register_for_autosave = mock.Mock()
        assert first.path != named  # a fresh default
        first.relocate(default_path)
        first.settings["mu_version"] = mu.__version__
        with mock.patch.object(first, "check_environment", return_value=None):
            assert first.switch_environment(named) is None
        assert os.path.isfile(venv_json)

        second = VE()
    assert second.path == named
    assert second.display_name == "project-a"
    assert second.default_dirpath() == default_path
    with (
        mock.patch.object(second, "ensure") as ensure,
        mock.patch.object(second, "create") as create,
        mock.patch.object(second, "recreate") as recreate,
        mock.patch.object(second, "quarantine_venv") as quarantine,
        mock.patch.object(second, "remove_old_bundled_pythons"),
        mock.patch.object(second.settings, "save"),
    ):
        second.ensure_and_create()
    ensure.assert_called_once_with()
    create.assert_not_called()
    recreate.assert_not_called()
    quarantine.assert_not_called()
    assert second.path == named


#
# Keeping a named environment's folder when it's rebuilt
#
def test_replacement_dirpath(venv, default_path):
    assert venv._replacement_dirpath() != default_path
    named = os.path.join(mu.config.ENVS_DIR, "project-a")
    venv.relocate(named)
    assert venv._replacement_dirpath() == named


def test_recreate_keeps_a_named_environments_folder(venv):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    venv.relocate(named)
    with (
        mock.patch.object(venv, "installed_packages", return_value=([], ["cowsay"])),
        mock.patch.object(venv, "create"),
        mock.patch.object(venv, "install_user_packages") as install,
    ):
        venv.recreate()
    assert venv.path == named
    assert os.path.isdir(named + ".SUPERSEDED")
    install.assert_called_once_with(["cowsay"])


def test_ensure_and_create_rebuilds_a_named_environment_in_place(venv):
    named = make_env(os.path.join(mu.config.ENVS_DIR, "project-a"))
    venv.relocate(named)
    with (
        mock.patch.object(venv, "ensure", side_effect=[EnsureError("broken"), None]),
        mock.patch.object(venv, "create") as create,
        mock.patch.object(venv, "remove_old_bundled_pythons"),
        mock.patch.object(venv.settings, "save"),
    ):
        venv.ensure_and_create()
    assert venv.path == named
    create.assert_called_once_with()
    assert os.path.isdir(named + ".FAILED")


def test_quarantine_twice(venv):
    """Moved aside again: the earlier one stays, the new one is dated."""
    os.makedirs(venv.path + ".FAILED")
    venv.quarantine_venv()
    moved = [f for f in os.listdir(os.path.dirname(venv.path)) if ".FAILED-" in f]
    assert len(moved) == 1
    assert not os.path.exists(venv.path)


def test_remove_old_bundled_pythons_keeps_named_environments_python(venv, data_dir):
    """A named environment based on an older bundled Python keeps it."""
    root = os.path.join(str(data_dir), "python")
    for name in ("cpython-3.11.9-old", "cpython-3.11.12-named", "cpython-3.11.15"):
        os.makedirs(os.path.join(root, name, "python", "bin"))
    make_env(
        os.path.join(mu.config.ENVS_DIR, "project-a"),
        home=os.path.join(root, "cpython-3.11.12-named", "python", "bin"),
    )
    archive = "/bundle/cpython-3.11.15.tar.gz"
    with mock.patch.object(mu.wheels, "bundled_python_archive", return_value=archive):
        venv.remove_old_bundled_pythons()
    assert sorted(os.listdir(root)) == ["cpython-3.11.12-named", "cpython-3.11.15"]
