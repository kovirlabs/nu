# -*- coding: utf-8 -*-
"""
Tests for the plugin base classes and API versioning.
"""

from unittest import mock

import pytest

import mu.plugin
from mu.plugin import (
    PLUGIN_API_VERSION,
    ModePlugin,
    Plugin,
    check_compatible,
)
from mu.modes.base import BaseMode, MicroPythonMode


def test_public_api_reexports_modes():
    """
    Plugins get Mode and MicroPythonMode from mu.plugin, not mu.modes.
    """
    assert mu.plugin.Mode is BaseMode
    assert mu.plugin.MicroPythonMode is MicroPythonMode
    for name in mu.plugin.__all__:
        assert hasattr(mu.plugin, name)


def test_core_version_is_compatible_with_itself():
    assert check_compatible(PLUGIN_API_VERSION) is None


@pytest.mark.parametrize(
    "api_version, core_version",
    [
        ("1.0", "1.0"),
        ("1.0", "1.3"),  # older minor on a 1.x core: additive, so fine
        ("1.3", "1.3"),
        ("0.2", "0.2"),
    ],
)
def test_check_compatible_accepts(api_version, core_version):
    assert check_compatible(api_version, core_version) is None


@pytest.mark.parametrize(
    "api_version, core_version, expected",
    [
        ("2.0", "1.0", "targets plugin API 2.0"),  # different major
        ("1.0", "2.0", "targets plugin API 1.0"),
        ("0.1", "0.2", "targets plugin API 0.1"),  # 0.x minors may break
        ("0.3", "0.2", "targets plugin API 0.3"),
        ("1.4", "1.3", "newer than this Nu's 1.3"),  # needs a newer core
        (None, "1.0", "no valid api_version"),
        ("1", "1.0", "no valid api_version"),
        ("1.0.0", "1.0", "no valid api_version"),
        ("one.two", "1.0", "no valid api_version"),
        (1.0, "1.0", "no valid api_version"),
    ],
)
def test_check_compatible_rejects(api_version, core_version, expected):
    assert expected in check_compatible(api_version, core_version)


def test_plugin_defaults_do_nothing():
    """
    The base Plugin's lifecycle hooks are safe no-ops, and it declares no
    api_version (so it won't load until a subclass sets one).
    """
    plugin = Plugin()
    host = mock.MagicMock()
    plugin.register(host)
    plugin.unregister(host)
    assert host.mock_calls == []
    assert Plugin.api_version is None


def test_mode_plugin_registers_its_modes():
    """
    ModePlugin registers `mode` then each of `modes`.
    """

    class One(BaseMode):
        short_name = "one"

    class Two(BaseMode):
        short_name = "two"

    class Three(BaseMode):
        short_name = "three"

    class Both(ModePlugin):
        mode = One
        modes = (Two, Three)

    host = mock.MagicMock()
    Both().register(host)
    assert host.register_mode.call_args_list == [
        mock.call(One),
        mock.call(Two),
        mock.call(Three),
    ]


def test_mode_plugin_with_nothing_registers_nothing():
    host = mock.MagicMock()
    ModePlugin().register(host)
    host.register_mode.assert_not_called()
