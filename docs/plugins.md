# Writing a Nu plugin

!!! warning "Status: working, but early"

    Nu loads plugins at startup, both installed packages and files in the
    plugins folder (Phases 5a and 5b in `TODO.md`), and Pygame Zero already
    ships as one (5c). The API is at version **0.2**, so it can still change
    between releases. There's no Plugins tab yet (Phase 5e), and in the
    downloadable installers the plugins folder is the only way to add a plugin
    (see below).

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
| **Bundled plugin** | A first-party plugin shipped and enabled by default. Today: **Pygame Zero** (`plugins/pygamezero`). CircuitPython follows (5c part 2), then micro:bit (Phase 6). |

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
| `PLUGIN_API_VERSION` | The API version this Nu provides, e.g. `"0.2"`. |
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
    api_version = "0.2"

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
    api_version = "0.2"
    mode = MicrobitMode          # or: modes = (ModeA, ModeB)
    # Optional: the folder of icons the modes use (see "Icons and images").
    images = os.path.join(os.path.dirname(__file__), "images")
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
    icon = "microbit"              # an image name: Nu's, or your plugin's

    def actions(self):
        """Toolbar buttons."""
        return [
            {
                "name": "flash",            # also its icon and button id
                "display_name": "Flash",
                "description": "Flash your code to the micro:bit.",
                "handler": self.flash,
                "shortcut": "F3",
            },
        ]

    def api(self):
        """Autocomplete and call tip entries."""
        return MICROBIT_APIS

    # Optional hooks: activate(), deactivate(), stop(), workspace_dir(),
    # ensure_workspace_assets(workspace_dir)
```

Two more things a mode can declare (new in 0.2):

| Member | Meaning |
|---|---|
| `uses_user_environment = False` | Set it to `True` if the mode runs the learner's programs in Nu's Python environment (as Python 3 and Pygame Zero do). The admin dialog then shows that environment's variables and third-party packages. |
| `ensure_workspace_assets(workspace_dir)` | Called for every mode each time Nu starts, once the workspace exists. Put what the mode needs there (Pygame Zero makes its `images`, `fonts`, `sounds` and `music` folders and copies in demo files). Leave anything already there alone. Errors are reported like any other plugin error and don't stop Nu starting. |

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
| `save_current()` | Save the current tab, asking for a name if it has none. Returns its path, or `None` if there's no tab or the learner cancelled. *(0.2)* |
| `run_program(path, python_args=None, interactive=False)` | Run the Python program at `path` as the Run button does: in the learner's environment, with their environment variables, from the program's folder, output in the output pane. `python_args` go before the program (e.g. `["-m", "pgzero"]`). Returns `True` if it started. *(0.2)* |
| `stop_program()` | Stop the program `run_program` started and close its pane. *(0.2)* |
| `update_action(name, display_name=None, description=None, icon=None)` | Change the current mode's toolbar button `name`: label, tooltip and/or icon. Raises `ValueError` if there's no such button. *(0.2)* |
| `register_images(directory)` | Make the images in `directory` available by name (see below). *(0.2)* |
| `python_apis()` | The Python 3 mode's autocomplete entries, as a new list to add yours to. *(0.2)* |
| `settings(namespace)` | A `PluginSettings` with `get(key, default=None)` and `set(key, value)`. Values are saved with the user's settings under `plugins.<namespace>` and must be JSON-serialisable. |
| `logger(name)` | A logger writing to Nu's log as `mu.plugins.<name>`. |
| `api_version` | The `PLUGIN_API_VERSION` this Nu provides. |

The core uses `load_plugin`, `unload_plugin`, `modes` and `plugins`; plugins
shouldn't need them.

### Icons and images

A mode's `icon`, each action's `name` and `update_action(icon=...)` are image
names: a file `name.svg` or `name.png`. Nu looks in its own images first, then
in folders plugins have registered, in the order they were registered. A plugin
registers its folder by setting `ModePlugin.images` (registered before its
modes) or calling `host.register_images(directory)`; it's removed again when
the plugin unloads. The same names work in a theme stylesheet's `images:` URLs.

An action's `name` is also its toolbar button's id, so it has to be unique
anyway. Image names must be unique too: if your folder has an image named like
one Nu or an already-loaded plugin has (whatever the extension),
`register_images` raises `ValueError` naming it, so your plugin fails to
register and is skipped, with the reason in the log. **Prefix your image names
with your plugin's name** (as `plugins/example` does: `example-mode`,
`example-count`) so a later Nu can't take a name you use. Your mode can still
use Nu's own icons by name (Pygame Zero uses Nu's `stop`).

### Packages for the learner's environment

The learner's programs run in Nu's own Python environment for them, not the one
Nu runs from. If your mode needs packages there (Pygame Zero needs `pgzero` and
`pygame`), list them as an extra called `learner-env` in your
`pyproject.toml`:

```toml
[project.optional-dependencies]
learner-env = ["pgzero>=1.2.1", "pygame>=2.6"]
```

Nu reads it from your package's metadata, without importing your plugin, so it
counts even while your plugin is switched off. These packages are installed
with Nu's own when the learner's environment is built (on first run, and when
Nu is upgraded), and bundled plugins' wheels ship in the installers so that
works offline. Not yet (Phase 5d): installing them into an *existing*
environment when you add a plugin later, and a way for drop-in plugins (which
have no package metadata) to declare any.

### Not in the API yet

These are planned, and are deliberately left out until a real plugin needs
them:

- **Panes and settings pages**, e.g. micro:bit's file-transfer pane (Phase 6).
- **Installing a plugin and its learner-env packages from Nu** (Phase 5d/5e).
- **Translations for plugins.** Bundled plugins use Nu's own message catalog
  (their strings are extracted with Nu's); a community plugin's strings aren't
  translated yet.

### What changed in 0.2

0.2 adds plugin images (`register_images`, `ModePlugin.images`), the mode
members `uses_user_environment` and `ensure_workspace_assets`, the `learner-env`
extra, and the Host methods `save_current`, `run_program`, `stop_program`,
`update_action` and `python_apis`. Nothing was removed, but while the API is
0.x a plugin must target the exact minor version, so a 0.1 plugin needs its
`api_version` changed to `"0.2"` (and is skipped, with the reason logged,
until it is).

## Packaging & distribution

- A plugin is a normal Python distribution: its own `pyproject.toml` declaring
  dependencies, the `mu.plugins` entry point and (optionally) the
  `learner-env` extra. Installing it into the learner's environment from Nu
  comes in Phase 5d.
- **Bundled** plugins live in this repo under `plugins/<name>/` as members of a
  **uv workspace** (shared lockfile; independently buildable and publishable).
  They are also published to PyPI, so they travel the *exact same* path a
  third-party plugin does — dogfooding the community story. See
  [Bundled plugins](#bundled-plugins) below.
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
    ├── __init__.py         # MyPlugin(ModePlugin) + MyMode(Mode)
    └── images/             # my-plugin-mode.svg, my-plugin-action.svg, ...
```

A runnable template lives in this repo at `plugins/example/`: an "Example"
mode with its own icons and one button that counts the lines in the current
tab and stores a setting. To start a plugin from it:

1. Copy `plugins/example` and rename the package (`nu_example`), the project
   `name`, the entry point and the `short_name`.
2. Rename the images, keeping your plugin's prefix, and point `icon` and the
   actions' `name`s at them.
3. List anything your mode needs in the learner's environment under
   `learner-env`.
4. Install it into the environment Nu runs from (`uv pip install -e
   path/to/plugin` in a checkout) and restart Nu.

`plugins/pygamezero/` is the worked example of a full mode: buttons that
toggle, running the learner's program, workspace assets, autocomplete stubs
and tests.

## Bundled plugins

A bundled plugin is an ordinary plugin package that lives in this repo, under
`plugins/<name>/`, and ships with Nu, switched on by default:

- It's a member of the repo's **uv workspace**, and `nu-editor` depends on it,
  so `uv sync` installs it (editable) and Nu finds it through its entry point,
  just as it finds a community plugin. The installers include it through
  Briefcase's `requires` (see [packaging](packaging.md)).
- It imports only `mu.plugin`, so it can graduate to its own repository by
  moving the folder.
- Its tests live in `plugins/<name>/tests` and run with Nu's (`pytest`
  collects `tests` and `plugins`; coverage covers both).
- It uses Nu's message catalog: `make translate_begin` extracts its strings
  with the core's.
- It's published to PyPI before the Nu release that depends on it.

To add one: create `plugins/<name>/` (from the template), add
`"nu-<name>>=<version>"` to `nu-editor`'s dependencies and
`nu-<name> = { workspace = true }` to `[tool.uv.sources]`, add
`"./plugins/<name>"` to `[tool.briefcase.app.mu].requires`, its source folder
to `pythonpath` in `[tool.pytest.ini_options]`, its package to
`_TRANSLATE_PLUGIN_PACKAGES` in `make.py`, and its path to the pip installs in
`.github/workflows/test.yml` and `build.yml`. Then `uv lock`.

If a bundled plugin's mode used to be built in, keep its `short_name`: saved
sessions and the `mode` setting refer to it. (If the plugin is switched off or
missing, Nu asks the learner to pick a mode at startup, as it does for any
mode it doesn't know.)

## See also

- [Modes](modes.md) — the mode concept the plugin `Mode` formalizes.
- [API reference](api.md#muplugin) — generated from the `mu.plugin`
  docstrings.
- `TODO.md` — Phase 5 (plugin architecture) and Phase 6 (the micro:bit plugin).
