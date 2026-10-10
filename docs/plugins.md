# Writing a Nu plugin

!!! warning "Status: working, but early"

    Nu loads plugins at startup, both installed packages and files in the
    plugins folder (Phases 5a and 5b in `TODO.md`). The API is at version
    **0.1**, so it can still change between releases. There's no Plugins tab
    yet (Phase 5e), and in the downloadable installers the plugins folder is
    the only way to add a plugin (see below).

## Why plugins

Nu is shrinking to a lean **core** — text editing, the REPL, the debugger,
settings, the uv-managed environment, and a *plugin host*. Everything else —
CircuitPython, Pygame Zero, micro:bit, and whatever the community builds — becomes
a **plugin**: an installable package that registers itself with the core and
contributes one or more [modes](modes.md) (and, over time, panes, menu items, and
API metadata for autocomplete).

This page is the contract for plugin authors. For the surrounding rationale and
roadmap, see Phase 5 (architecture) and Phase 6 (the micro:bit plugin) in
`TODO.md`.

## Concepts

| Term | Meaning |
|---|---|
| **Core** | The always-present editor: editing, REPL, debugger, settings, the uv environment, and the plugin host. Ships the built-in **Python 3** + **Debugger** modes. |
| **Plugin** | An installable package that extends the core through the public `mu.plugin` API. |
| **Mode** | The primary thing a plugin contributes — a named, icon-bearing "personality" that adds toolbar buttons, autocomplete APIs, a workspace directory, etc. (today's `BaseMode`). |
| **Host** | The stable façade the core hands a plugin at load time — the *only* supported way to touch the editor. |
| **Bundled plugin** | A first-party plugin shipped and enabled by default (CircuitPython, Pygame Zero, micro:bit). |

## How a plugin is discovered

Nu looks for plugins once, at startup, in two places. Changes take effect the
next time Nu starts.

1. **Installed packages.** Any package installed in the environment Nu runs
   from that declares a `mu.plugins` entry point (see
   [The entry point](#the-entry-point)). Its id is the entry point's name.
2. **The plugins folder**, for local plugins that aren't packaged:

    | System | Folder |
    |---|---|
    | Windows | `%LOCALAPPDATA%\python\mu\plugins` |
    | macOS | `~/Library/Application Support/mu/plugins` |
    | Linux | `~/.local/share/mu/plugins` |

    Nu creates the folder if it's missing. Each `name.py` file, or `name/`
    folder with an `__init__.py`, is one plugin with id `name`. The plugin is
    the module's `PLUGIN` attribute if it sets one; otherwise the module must
    define exactly one `Plugin` subclass. A plugin folder imports its own
    files with relative imports (`from .modes import MyMode`). Names starting
    with `.` or `_` are ignored. A name that matches an installed module
    (`json.py`, say) is refused rather than allowed to replace that module.

Installed packages are found first. If a folder plugin has the same id as an
installed one, the folder plugin is skipped.

!!! note "Installers and installed packages"

    In the Windows, macOS and Linux installers, Nu runs from its own bundled
    environment, which you can't install packages into. Until Phase 5d adds
    plugin installs, use the plugins folder there. Installed packages are
    picked up in a development checkout (`uv pip install -e path/to/plugin`)
    or a `pip install nu-editor`.

### When a plugin is skipped

Nu logs the reason (see the log via the cog icon) and starts without the
plugin if it:

- is switched off;
- has the same id as a plugin already found;
- fails to import, including calling `sys.exit()` while importing;
- declares a missing or incompatible `api_version`; or
- raises an error in `register`.

Any modes it registered before failing are removed again. An unnamed plugin
(one that doesn't set `name`) is called by its id.

### When a plugin has an error

Once loaded, a plugin's errors don't crash Nu. That covers errors in the mode
methods Nu calls (`activate`, `actions`, `api`, `workspace_dir`, `stop`, …)
and in anything Qt calls for the plugin: button handlers, timers and signal
handlers. For each error:

- **The learner sees a dialog** naming the plugin, with the error for its
  author. Nu keeps running.
- **The log gets the full traceback.** An identical repeat gets a one-line
  entry instead.
- **Nu falls back to something safe** when it was calling the mode: `api()`
  and `actions()` give an empty list, `workspace_dir()` the usual workspace,
  and the rest give `None`.
- **Dialogs are rate limited.** Further errors within 30 seconds, or while a
  dialog is open, go to the status bar instead, so a failing timer can't bury
  the learner in dialogs.
- **A plugin that keeps failing** (3 errors) is offered to be switched off. If
  the learner agrees, it isn't loaded the next time Nu starts.

An error counts as the plugin's when the plugin's own modules appear in the
traceback, or when core code was running on one of its modes (for example
`MicroPythonMode` code it inherits).

For a problem the learner can fix, raise `PluginError` instead. Nu shows your
message as is, and doesn't count it against the plugin:

```python
from mu.plugin import PluginError

def flash(self, event=None):
    if not self.find_devices():
        raise PluginError(
            "Plug in your micro:bit first.",
            "Use a USB cable that carries data, not just power.",
        )
```

### Switching a plugin off

With Nu closed (it rewrites the file when it exits), add the plugin's id to
`disabled_plugins` in Nu's `settings.json`, which is in the same data folder
as `plugins/`:

```json
{
  "disabled_plugins": ["example"]
}
```

A switched-off plugin isn't even imported. The Plugins tab (Phase 5e) will do
this for you.

## The API

Everything a plugin needs is imported from `mu.plugin`. Nothing else in `mu`
is public: `mu.modes`, `mu.logic` and `mu.interface` can change in any
release.

| Name | What it is |
|---|---|
| `PLUGIN_API_VERSION` | The API version this Nu provides, e.g. `"0.1"`. |
| `Plugin` | Base class for a plugin. |
| `ModePlugin` | A `Plugin` that registers one or more modes for you. |
| `Mode` | Base class for a mode (today's `BaseMode`). |
| `MicroPythonMode` | A `Mode` with serial REPL, plotter and board detection, for MicroPython devices. |
| `Host` | What a plugin is handed: the supported way to reach the editor. |
| `PluginSettings` | A plugin's own persisted settings (from `Host.settings`). |
| `PluginError` | Raise it for a problem the learner can fix; Nu shows the message (see [When a plugin has an error](#when-a-plugin-has-an-error)). |
| `check_compatible` | The version check `Host` applies when loading a plugin. |

### The entry point

A packaged plugin advertises itself in its `pyproject.toml`:

```toml
[project.entry-points."mu.plugins"]
microbit = "nu_microbit:MicrobitPlugin"
```

The value points at a `Plugin` subclass, a `Plugin` instance, or a function
that returns one.

### Versioning: `api_version`

Each plugin declares the `PLUGIN_API_VERSION` it was written against, as a
literal string. When loading it, the host compares that with its own version:

- **Same MAJOR, and a MINOR no newer than Nu's:** the plugin loads.
- **While MAJOR is 0:** the MINOR must match exactly, because 0.x releases
  may break the API.
- **Anything else, or a missing/malformed `api_version`:** the plugin is
  logged and skipped. Nu carries on without it.

### `Plugin`

```python
from mu.plugin import Plugin

class MyPlugin(Plugin):
    name = "My Plugin"
    api_version = "0.1"

    def register(self, host):
        """Called once when the plugin loads. Do all wiring here, through
        `host`."""

    def unregister(self, host):
        """Optional. Called when the plugin unloads. Modes it registered are
        removed for you; undo anything else here."""
```

If `register` raises, the plugin is logged and skipped, and any modes it had
already registered are removed. A broken plugin never stops Nu starting.

For the common case of a plugin that only adds modes, use `ModePlugin`:

```python
from mu.plugin import ModePlugin

class MicrobitPlugin(ModePlugin):
    name = "micro:bit"
    api_version = "0.1"
    mode = MicrobitMode          # or: modes = (ModeA, ModeB)
```

### `Mode`

`Mode` is the mode base class the built-in modes use (see [Modes](modes.md)).
Set the class attributes and override the methods you need:

```python
from mu.plugin import Mode

class MicrobitMode(Mode):
    name = "micro:bit"             # shown in the mode picker
    short_name = "microbit"        # stable, unique id (settings and session keys)
    description = "Write MicroPython for the BBC micro:bit."
    icon = "microbit"              # a built-in icon name, for now

    def actions(self):
        """Toolbar buttons."""
        return [
            {
                "name": "flash",            # also the icon name, for now
                "display_name": "Flash",
                "description": "Flash your code to the micro:bit.",
                "handler": self.flash,
                "shortcut": "F3",
            },
        ]

    def api(self):
        """Autocomplete and call tip entries."""
        return MICROBIT_APIS

    # Optional hooks: activate(), deactivate(), stop(), workspace_dir()
```

Inside a mode, `self.host` is the `Host` that registered it. Use it rather
than `self.editor` and `self.view`, which are the internal objects and are not
part of the API.

For a MicroPython board, subclass `MicroPythonMode` instead and list the
boards in `valid_boards` as `(vid, pid, manufacturer, board_name)` tuples. Nu
then detects the board when it's plugged in and offers to switch to your mode.

### `Host`

| Method | Does |
|---|---|
| `register_mode(mode_class)` | Create the mode and add it to the editor. Its `short_name` must be unique. Returns the mode. |
| `show_message(message, information=None, icon=None)` | Show a modal message. `icon` is `"NoIcon"`, `"Question"`, `"Information"`, `"Warning"` (the default) or `"Critical"`. |
| `confirm(message, information=None, icon=None)` | Ask OK/Cancel; returns `True` for OK. |
| `show_status(message, duration=5)` | Show a message in the status bar for `duration` seconds. |
| `current_text()` | The current tab's text, or `None` if no tab is open. |
| `current_path()` | The current tab's file path, or `None`. |
| `workspace_dir()` | The learner's workspace directory. |
| `open_directory(path)` | Open `path` in the system file manager. |
| `settings(namespace)` | A `PluginSettings` with `get(key, default=None)` and `set(key, value)`. Values are saved with the user's settings under `plugins.<namespace>` and must be JSON-serialisable. |
| `logger(name)` | A logger writing to Nu's log as `mu.plugins.<name>`. |
| `api_version` | The `PLUGIN_API_VERSION` this Nu provides. |

The core uses `load_plugin`, `unload_plugin`, `modes` and `plugins`; plugins
shouldn't need them.

### Not in the API yet

These are planned, and are deliberately left out until a real plugin needs
them:

- **Icons shipped by the plugin.** Mode and button icons must be built-in icon
  names for now (Phase 5c).
- **Panes and settings pages**, e.g. micro:bit's file-transfer pane (Phase 6).
- **Installing packages into the learner's environment** (Phase 5d).

## Packaging & distribution

- A plugin is a normal Python distribution: its own `pyproject.toml` declaring
  dependencies and the `mu.plugins` entry point. Installing it pulls its
  dependencies into the user's **uv** environment (Phase 4 / 5d).
- **Bundled** plugins live in this repo under `plugins/<name>/` as members of a
  **uv workspace** (shared lockfile; independently buildable and publishable).
  They are also published to PyPI, so they travel the *exact same* path a
  third-party plugin does — dogfooding the community story.
- **Community** plugins live in their own repositories and publish independently.
  A bundled plugin "graduates" to its own repo only once the API is stable and it
  has a reason to diverge (separate maintainer, release cadence, or licence) —
  which, because it is already its own package, is a trivial directory move.
- **Licensing:** the core is **GPLv3**. Whether a plugin is a derivative work is
  the classic murky plugin question; first-party plugins stay GPLv3, and
  community authors should weigh the API boundary's licence implications.

## Versioning & compatibility

- The core advertises `PLUGIN_API_VERSION`; each plugin declares `api_version`
  (the rules are under [Versioning](#versioning-api_version) above).
- An incompatible plugin is logged and skipped, never a crash. From Phase 5e
  the Plugins tab will show why it was skipped.
- The API is bumped deliberately, with a short compatibility-shim window. It
  stays at 0.x until the micro:bit plugin (Phase 6) has proven it.

## Trust & safety

Plugins are **arbitrary in-process Python** — there is no sandbox. The trust
model is the same as `pip`: *you chose to install it.* Install plugins you trust;
the Plugins tab (Phase 5e) will show the real `uv` command it runs before installing. (A
curated/signed index is a possible future, not a v1 guarantee.)

## A minimal example

```text
my-nu-plugin/
├── pyproject.toml          # deps + [project.entry-points."mu.plugins"]
└── my_nu_plugin/
    └── __init__.py         # MyPlugin(Plugin) + MyMode(Mode)
```

A runnable template lives in this repo at `plugins/example/`: an "Example"
mode with one button that counts the lines in the current tab and stores a
setting. Copy it to start a plugin. The built-in modes in `mu/modes/` are
worked examples of bigger modes.

## See also

- [Modes](modes.md) — the mode concept the plugin `Mode` formalizes.
- [API reference](api.md#muplugin) — generated from the `mu.plugin`
  docstrings.
- `TODO.md` — Phase 5 (plugin architecture) and Phase 6 (the micro:bit plugin).
