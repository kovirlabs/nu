# -*- coding: utf-8 -*-
"""
Tests for plugin discovery and loading.
"""

import importlib.metadata
import logging
import sys
import textwrap
import uuid
from unittest import mock

import pytest

from mu import settings
from mu.plugin import PLUGIN_API_VERSION, Host, Plugin, loader
from mu.plugin.loader import (
    DISABLED,
    LOADED,
    SKIPPED,
    PluginLoadError,
    PluginSource,
)
from mu.modes.base import BaseMode

GOOD_PLUGIN = textwrap.dedent(
    """
    from mu.plugin import ModePlugin, Mode

    class {cls}Mode(Mode):
        short_name = "{name}"

    class {cls}Plugin(ModePlugin):
        name = "{cls}"
        api_version = "{version}"
        mode = {cls}Mode
    """
)


@pytest.fixture
def unique():
    """A module name no test has used, removed from sys.modules afterwards."""
    names = []

    def make():
        name = "dropin_" + uuid.uuid4().hex[:8]
        names.append(name)
        return name

    yield make
    for name in list(sys.modules):
        if any(name == n or name.startswith(n + ".") for n in names):
            del sys.modules[name]


@pytest.fixture
def host():
    return Host(mock.MagicMock(), mock.MagicMock())


def write_plugin(dirpath, name, version=PLUGIN_API_VERSION):
    (dirpath / (name + ".py")).write_text(
        GOOD_PLUGIN.format(cls="Good", name=name, version=version)
    )


class GoodPlugin(Plugin):
    api_version = PLUGIN_API_VERSION


# --- _instantiate ---


def test_instantiate_class_instance_and_factory():
    assert isinstance(loader._instantiate(GoodPlugin, "x"), GoodPlugin)
    instance = GoodPlugin()
    assert loader._instantiate(instance, "x") is instance
    assert loader._instantiate(lambda: instance, "x") is instance


@pytest.mark.parametrize("obj", [object, "nope", lambda: "nope", BaseMode])
def test_instantiate_rejects_non_plugins(obj):
    with pytest.raises(PluginLoadError, match="x is not a mu.plugin.Plugin"):
        loader._instantiate(obj, "x")


# --- entry points ---


def test_entry_point_sources():
    """
    Installed plugins come from the mu.plugins entry points, named by the
    entry point and described by their distribution.
    """
    with_dist = mock.MagicMock()
    with_dist.name = "microbit"
    with_dist.value = "nu_microbit:MicrobitPlugin"
    with_dist.dist.name = "nu-microbit"
    with_dist.dist.version = "1.0"
    with_dist.load.return_value = GoodPlugin
    no_dist = mock.MagicMock()
    no_dist.name = "bare"
    no_dist.value = "bare:Plugin"
    no_dist.dist = None
    no_dist.load.side_effect = ImportError("no bare")
    with mock.patch(
        "importlib.metadata.entry_points", return_value=[with_dist, no_dist]
    ) as entry_points:
        sources = loader.entry_point_sources()
    entry_points.assert_called_once_with(group="mu.plugins")
    assert [(s.id, s.kind, s.origin) for s in sources] == [
        ("microbit", "package", "nu-microbit 1.0"),
        ("bare", "package", "bare:Plugin"),
    ]
    assert isinstance(sources[0].load(), GoodPlugin)
    with pytest.raises(ImportError):
        sources[1].load()


def test_entry_point_sources_finds_a_real_entry_point():
    """
    A real EntryPoint object (as importlib.metadata returns) works too.
    """
    entry_point = importlib.metadata.EntryPoint(
        name="good",
        value="tests.plugin.test_loader:GoodPlugin",
        group="mu.plugins",
    )
    with mock.patch("importlib.metadata.entry_points", return_value=[entry_point]):
        (source,) = loader.entry_point_sources()
    assert source.id == "good"
    assert isinstance(source.load(), GoodPlugin)


# --- the drop-in folder ---


def test_dropin_sources_finds_modules_and_packages(tmp_path, unique):
    """
    Each name.py or name/ package is a plugin; other entries are ignored.
    """
    module_name, package_name = unique(), unique()
    write_plugin(tmp_path, module_name)
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("")
    (tmp_path / "not_a_package").mkdir()
    (tmp_path / ".hidden.py").write_text("")
    (tmp_path / "_private.py").write_text("")
    (tmp_path / "notes.txt").write_text("")
    (tmp_path / "bad-name.py").write_text("")
    sources = loader.dropin_sources(str(tmp_path))
    assert sorted(s.id for s in sources) == sorted([module_name, package_name])
    assert {s.kind for s in sources} == {"folder"}


def test_dropin_sources_defaults_to_the_data_folder(tmp_path, monkeypatch):
    folder = tmp_path / "data_plugins"
    monkeypatch.setattr(loader, "DROPIN_DIR", str(folder))
    write_plugin(folder.parent, "unused")  # outside the folder: not found
    assert loader.dropin_sources() == []
    assert folder.is_dir()


def test_dropin_sources_creates_the_folder(tmp_path):
    folder = tmp_path / "plugins"
    assert loader.dropin_sources(str(folder)) == []
    assert folder.is_dir()


def test_dropin_sources_unreadable_folder(tmp_path, caplog):
    with mock.patch("os.makedirs", side_effect=PermissionError("no")):
        with caplog.at_level(logging.ERROR):
            assert loader.dropin_sources(str(tmp_path / "x")) == []
    assert "Can't read the plugins folder" in caplog.text


def test_load_dropin_module(tmp_path, unique):
    name = unique()
    write_plugin(tmp_path, name)
    (source,) = loader.dropin_sources(str(tmp_path))
    plugin = source.load()
    assert type(plugin).__name__ == "GoodPlugin"
    assert source.origin == str(tmp_path / (name + ".py"))


def test_load_dropin_package_with_relative_import(tmp_path, unique):
    """
    A drop-in package can import its own submodules.
    """
    name = unique()
    package = tmp_path / name
    package.mkdir()
    (package / "modes.py").write_text(
        "from mu.plugin import Mode\n\nclass PkgMode(Mode):\n    short_name = 'pkg'\n"
    )
    (package / "__init__.py").write_text(
        "from mu.plugin import ModePlugin\n"
        "from .modes import PkgMode\n\n"
        "class PkgPlugin(ModePlugin):\n"
        "    api_version = '{}'\n"
        "    mode = PkgMode\n".format(PLUGIN_API_VERSION)
    )
    (source,) = loader.dropin_sources(str(tmp_path))
    plugin = source.load()
    assert plugin.mode.short_name == "pkg"


def test_load_dropin_uses_PLUGIN_attribute(tmp_path, unique):
    """
    PLUGIN picks the plugin when a module defines more than one.
    """
    name = unique()
    (tmp_path / (name + ".py")).write_text(
        "from mu.plugin import Plugin\n\n"
        "class One(Plugin):\n    pass\n\n"
        "class Two(Plugin):\n    pass\n\n"
        "PLUGIN = Two\n"
    )
    (source,) = loader.dropin_sources(str(tmp_path))
    assert type(source.load()).__name__ == "Two"


@pytest.mark.parametrize(
    "body, count",
    [
        ("from mu.plugin import Plugin\n", 0),  # imported, not defined here
        (
            "from mu.plugin import Plugin\n\n"
            "class One(Plugin):\n    pass\n\n"
            "class Two(Plugin):\n    pass\n",
            2,
        ),
    ],
)
def test_load_dropin_needs_exactly_one_plugin(tmp_path, unique, body, count):
    name = unique()
    (tmp_path / (name + ".py")).write_text(body)
    (source,) = loader.dropin_sources(str(tmp_path))
    with pytest.raises(PluginLoadError, match="found {}".format(count)):
        source.load()


@pytest.mark.parametrize("name", ["json", "mu"])
def test_load_dropin_refuses_to_shadow_modules(tmp_path, name):
    (tmp_path / (name + ".py")).write_text("raise RuntimeError('ran!')\n")
    (source,) = loader.dropin_sources(str(tmp_path))
    with pytest.raises(PluginLoadError, match="clashes with an installed module"):
        source.load()


def test_load_dropin_failed_import_is_cleaned_up(tmp_path, unique):
    name = unique()
    (tmp_path / (name + ".py")).write_text("raise RuntimeError('broken')\n")
    (source,) = loader.dropin_sources(str(tmp_path))
    with pytest.raises(RuntimeError, match="broken"):
        source.load()
    assert name not in sys.modules


def test_discover_puts_packages_before_the_folder(tmp_path, unique):
    package = PluginSource("pkg", "package", "pkg 1.0", lambda: None)
    name = unique()
    write_plugin(tmp_path, name)
    with mock.patch.object(loader, "entry_point_sources", return_value=[package]):
        sources = loader.discover(str(tmp_path))
    assert [s.id for s in sources] == ["pkg", name]


def test_discover_survives_broken_metadata(tmp_path, caplog):
    with mock.patch.object(
        loader, "entry_point_sources", side_effect=RuntimeError("bad metadata")
    ):
        with caplog.at_level(logging.ERROR):
            assert loader.discover(str(tmp_path)) == []
    assert "Can't read installed plugin entry points" in caplog.text


# --- switching plugins on and off ---


def test_enable_and_disable():
    store = settings.UserSettings()
    assert loader.disabled_plugins(store) == set()
    loader.set_plugin_enabled("microbit", False, store)
    loader.set_plugin_enabled("example", False, store)
    assert store["disabled_plugins"] == ["example", "microbit"]
    loader.set_plugin_enabled("microbit", True, store)
    loader.set_plugin_enabled("never-disabled", True, store)
    assert loader.disabled_plugins(store) == {"example"}
    assert "disabled_plugins" in store._dirty


def test_disabled_plugins_defaults_to_user_settings():
    with mock.patch.object(settings, "settings", {"disabled_plugins": ["x"]}):
        assert loader.disabled_plugins() == {"x"}


def test_set_plugin_enabled_defaults_to_user_settings():
    store = settings.UserSettings()
    with mock.patch.object(settings, "settings", store):
        loader.set_plugin_enabled("x", False)
    assert store["disabled_plugins"] == ["x"]


# --- load_plugins ---


def source(plugin_id, load):
    return PluginSource(plugin_id, "package", plugin_id + " 1.0", load)


def make_mode_plugin(short_name, api_version=PLUGIN_API_VERSION):
    mode_class = type(short_name + "Mode", (BaseMode,), {"short_name": short_name})

    class P(Plugin):
        name = short_name

        def register(self, host):
            host.register_mode(mode_class)

    P.api_version = api_version
    return P()


def test_load_plugins_loads_and_records(host):
    plugin = make_mode_plugin("alpha")
    (record,) = loader.load_plugins(
        host, [source("alpha", lambda: plugin)], settings.UserSettings()
    )
    assert record.status == LOADED
    assert record.plugin is plugin
    assert record.reason == ""
    assert "alpha" in host.modes
    assert host.plugins == [plugin]


def test_load_plugins_skips_everything_that_goes_wrong(host, caplog):
    """
    Each kind of failure is recorded and logged; the good plugin still loads.
    """
    store = settings.UserSettings()
    loader.set_plugin_enabled("off", False, store)
    off = mock.MagicMock()

    def broken_import():
        raise ImportError("no module named nope")

    def exits():
        raise SystemExit(1)

    class FailsToRegister(Plugin):
        api_version = PLUGIN_API_VERSION

        def register(self, host):
            raise RuntimeError("boom")

    sources = [
        source("off", off),
        source("broken", broken_import),
        source("exits", exits),
        source("old", lambda: make_mode_plugin("old", "99.0")),
        source("fails", FailsToRegister),
        source("good", lambda: make_mode_plugin("good")),
        source("good", lambda: make_mode_plugin("good2")),  # duplicate id
    ]
    with caplog.at_level(logging.INFO):
        records = loader.load_plugins(host, sources, store)
    summary = [(r.id, r.status) for r in records]
    assert summary == [
        ("off", DISABLED),
        ("broken", SKIPPED),
        ("exits", SKIPPED),
        ("old", SKIPPED),
        ("fails", SKIPPED),
        ("good", LOADED),
        ("good", SKIPPED),
    ]
    off.assert_not_called()  # a switched-off plugin isn't even imported
    reasons = {r.id: r.reason for r in records if r.status == SKIPPED}
    assert "failed to import: no module named nope" in reasons["broken"]
    assert reasons["old"].startswith("it targets plugin API 99.0")
    assert reasons["fails"] == "it failed to register (see the log)"
    assert records[-1].reason == "another plugin is already called 'good'"
    assert list(host.modes) == ["good"]
    assert "Plugin off (off 1.0) is switched off" in caplog.text
    assert "Skipping plugin broken" in caplog.text


def test_load_plugins_lets_ctrl_c_through(host):
    def interrupted():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        loader.load_plugins(host, [source("x", interrupted)], settings.UserSettings())


def test_load_plugins_discovers_by_default(host):
    with mock.patch.object(loader, "discover", return_value=[]) as discover:
        assert loader.load_plugins(host, store=settings.UserSettings()) == []
    discover.assert_called_once_with()


def test_check_usb_survives_a_failing_mode(caplog):
    """
    Device polling runs for every mode each second; one mode's failure is
    logged and the others still detect their devices.
    """
    from mu.logic import Device, DeviceList

    broken, working = mock.MagicMock(), mock.MagicMock()
    broken.find_devices.side_effect = RuntimeError("serial gone")
    device = Device(
        0x239A, 0x8019, "COM1", 1, "Adafruit", "CircuitPython", "circuitpython"
    )
    working.find_devices.return_value = [device]
    devices = DeviceList({"broken": broken, "working": working})
    with caplog.at_level(logging.ERROR):
        devices.check_usb()
    assert list(devices) == [device]
    assert "Mode broken failed to look for devices" in caplog.text


def test_load_plugins_names_unnamed_plugins_by_id(host):
    plugin = GoodPlugin()
    named = make_mode_plugin("alpha")
    loader.load_plugins(
        host,
        [source("anon", lambda: plugin), source("alpha", lambda: named)],
        settings.UserSettings(),
    )
    assert plugin.name == "anon"
    assert named.name == "alpha"
    assert GoodPlugin.name == Plugin.name  # the class is untouched
