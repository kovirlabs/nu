# API reference

This API reference is automatically generated from the docstrings found within
the source code of Nu and its bundled plugins. It's meant as an easy to use and easy to share window into the
code base.

Take a look around! The code is simple and short.

## `mu.app`

The Nu application is created and configured in this module (see
[how Nu starts](architecture.md#how-nu-starts)).

::: mu.app

## `mu.logic`

Most of the fundamental logic for Nu is in this module: the `Editor` class.

::: mu.logic

## `mu.debugger`

The debugger consists of two parts:

* Client - used by Nu to process messages from the process being debugged.
* Runner - created in a new process to run the code to be debugged.

Messages are passed via inter-process communication.

### `mu.debugger.client`

Code used by Nu to communicate with the process being debugged.

::: mu.debugger.client

### `mu.debugger.runner`

The runner code controls the debug process.

::: mu.debugger.runner

## `mu.plugin`

The public API for plugins. See [Writing a Nu plugin](plugins.md). Plugins
import from `mu.plugin` only; it re-exports the names below.

::: mu.plugin
    options:
      members: false

::: mu.plugin.base

::: mu.plugin.host

::: mu.plugin.loader

::: mu.plugin.errors

## `mu.interface`

This module contains all the PyQt related code needed to create the user
interface for Nu. All interaction with the user interface is done via the
`Window` class in `mu.interface.main`.

All the other sub-modules contain different bespoke aspects of the user
interface.

### `mu.interface.main`

Contains the core user interface assets used by other parts of the application.

::: mu.interface.main

### `mu.interface.dialogs`

Bespoke modal dialogs required by Nu, including the admin dialog's tabs.

::: mu.interface.dialogs

### `mu.interface.editor`

Contains the customised Scintilla based editor used for textual display and
entry.

::: mu.interface.editor

### `mu.interface.panes`

Contains code used to populate the various panes found in the user interface
(REPL, file list, debug inspector etc...).

::: mu.interface.panes

### `mu.interface.themes`

Theme related code so Qt changes for each pre-defined theme.

::: mu.interface.themes

## `mu.modes`

Contains the core's two modes (every other mode comes from a plugin). All the
core functionality is in the `mu.modes.base` module.

### `mu.modes.base`

Core functionality and base classes for all modes (plugins get them as
`mu.plugin.Mode` and `mu.plugin.MicroPythonMode`). The definitions of
API autocomplete and call tips can be found in the `mu.modes.api` namespace.

::: mu.modes.base

### `mu.modes.debugger`

The Python 3 debugger mode.

::: mu.modes.debugger

### `mu.modes.python3`

The Python 3 editing mode.

::: mu.modes.python3

## Bundled plugins

Plugins shipped with Nu, in `plugins/` (see [plugins](plugins.md)).

### `nu_circuitpython`

The CircuitPython mode for Adafruit boards (and others), as a bundled plugin
(`plugins/circuitpython`).

::: nu_circuitpython

::: nu_circuitpython.mode

### `nu_pygamezero`

The Pygame Zero / pygame mode, as a bundled plugin (`plugins/pygamezero`).

::: nu_pygamezero

::: nu_pygamezero.mode

### `nu_microbit`

The BBC micro:bit mode, as an opt-in plugin (`plugins/microbit`; see
[The BBC micro:bit](microbit.md)).

::: nu_microbit

::: nu_microbit.mode

::: nu_microbit.board

::: nu_microbit.firmware

::: nu_microbit.flash

::: nu_microbit.worker

## `mu.virtual_environment`

The learner's Python environment, made and managed with uv (see
[Your Python environment](environment.md) and the
[design notes](design/runtime_virtual_environment.md#nu-today)).

::: mu.virtual_environment

## `mu.settings` and `mu.config`

Settings files and where they live (see
[settings and sessions](design/settings-and-sessions.md#nu-today)).

::: mu.settings

::: mu.config

## `mu.command_log`

The log of the uv commands Nu runs in the learner's Python environment, shown
as "What Nu Ran" (see [Your Python environment](environment.md)).

::: mu.command_log

## `mu.script_metadata`

Finds PEP 723 `# /// script` blocks, so Run can use `uv run` for them.

::: mu.script_metadata

## `mu.resources`

Contains utility functions for working with binary assets used by Nu (mainly
images).

::: mu.resources
