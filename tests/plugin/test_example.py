# -*- coding: utf-8 -*-
"""
Tests for the example plugin template in plugins/example.
"""

import importlib
import os
import tomllib
from unittest import mock

import pytest

from mu.plugin import PLUGIN_API_VERSION, Host

EXAMPLE_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "example"
)


@pytest.fixture
def nu_example(monkeypatch):
    monkeypatch.syspath_prepend(EXAMPLE_DIR)
    return importlib.import_module("nu_example")


@pytest.fixture
def host():
    return Host(mock.MagicMock(), mock.MagicMock())


def test_entry_point_names_the_plugin(nu_example):
    """
    The pyproject entry point resolves to the plugin class.
    """
    with open(os.path.join(EXAMPLE_DIR, "pyproject.toml"), "rb") as f:
        project = tomllib.load(f)["project"]
    target = project["entry-points"]["mu.plugins"]["example"]
    module_name, attr = target.split(":")
    plugin_class = getattr(importlib.import_module(module_name), attr)
    assert plugin_class is nu_example.ExamplePlugin


def test_targets_the_current_api(nu_example):
    """
    Keep the template current: bump it with PLUGIN_API_VERSION.
    """
    assert nu_example.ExamplePlugin.api_version == PLUGIN_API_VERSION


def test_loads_into_a_host(nu_example, host):
    assert host.load_plugin(nu_example.ExamplePlugin()) is True
    mode = host.modes["example"]
    assert isinstance(mode, nu_example.ExampleMode)
    (action,) = mode.actions()
    assert action["handler"] == mode.count_lines
    assert mode.api() == []


def test_count_lines(nu_example, host):
    host.load_plugin(nu_example.ExamplePlugin())
    mode = host.modes["example"]
    host._view.current_tab.text.return_value = "a\nb\nc\n"
    plugin_settings = mock.MagicMock()
    plugin_settings.get.return_value = 4
    with mock.patch.object(host, "settings", return_value=plugin_settings):
        mode.count_lines()
    plugin_settings.set.assert_called_once_with("presses", 5)
    host._editor.show_status_message.assert_called_once_with("3 lines (count #5)", 5)


def test_count_lines_without_a_tab(nu_example, host):
    host.load_plugin(nu_example.ExamplePlugin())
    host._view.current_tab = None
    host.modes["example"].count_lines()
    host._view.show_message.assert_called_once()
    host._editor.show_status_message.assert_not_called()
