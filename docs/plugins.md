# Writing a Nu plugin

!!! warning "Status: working, but early"

    Nu loads plugins at startup, both installed packages and files in the
    plugins folder (Phases 5a and 5b in `TODO.md`), CircuitPython and Pygame
    Zero ship as plugins (5c), and the **Plugins** tab lists them and switches
    them on and off (5e). The API is at version **0.5**, so it can still
    change between releases. In the downloadable installers the plugins
    folder is the only way to add a plugin (see
    [Roadmap: installing plugins](#roadmap-installing-plugins)).

## Managing plugins

*This part is for learners and teachers; the rest of the page is for people
writing plugins.*

Click the **cog** in the bottom-right corner of Nu's window and choose the
**Plugins** tab. It lists every plugin Nu found when it started:

| Column | What it shows |
|---|---|
| **On** | Tick to switch the plugin on, untick to switch it off. |
| **Plugin** | Its name. Hover over it to see what it adds. |
| **From** | *Bundled with Nu* (it comes with Nu: CircuitPython and Pygame Zero), *Installed package* (installed into the Python that Nu runs from), or *Plugins folder* (a file or folder put in Nu's plugins folder). Hover over it for the exact package or file. |
| **Status** | *On*, *Off*, *Couldn't load*, or *Switched off after errors; see the log*. |
| **Modes** | The modes it adds to the mode picker. |

Click a plugin to see more about it under the list. If it couldn't load,
there's a plain sentence saying why (for example *It has an error in its code,
so Nu couldn't start it*), then the error itself, with a **Copy** button so
you can send it to whoever wrote the plugin.

**Switching a plugin off, or back on.** Untick it and click **OK**. Bundled
plugins can be switched off too: a class that only uses Python 3 can take
CircuitPython and Pygame Zero out of the mode picker. Changes take effect the
**next time you start Nu**; until then the plugin keeps working, and the tab
says *On until you restart Nu*. A switched-off plugin isn't loaded at all.

**Adding a plugin.** Click **Open plugins folder**, put the plugin's `.py`
file (or its folder) there, and restart Nu. Installing plugins from inside Nu
is planned (see the [roadmap](#roadmap-installing-plugins)).

**When a plugin keeps failing**, Nu tells you each time and carries on. After
three errors it offers to switch the plugin off; if you agree, the Plugins tab
shows it as *Switched off after errors; see the log* from the next start, and
the errors are on the **Current Log** tab. Tick it to give it another go.

**Only add plugins you trust.** A plugin is Python code that runs inside Nu,
with the same access to your computer as Nu itself: it can read and change
your files, like any program you install. Nu can't check what a plugin does.

**How to write a plugin** on the tab opens this page.

!!! note "For teachers: where the choice is kept"

    Nu keeps the ids of switched-off plugins (the **Id** in a plugin's
    details) in its `settings.json`, in the same data folder as `plugins/`,
    and saves it as soon as you click **OK**:

    ```json
    {
      "disabled_plugins": ["pygamezero"]
    }
    ```

    To prepare several computers, you can write that file yourself while Nu
    is closed. `plugins_switched_off_after_errors` lists the plugins Nu
    switched off because they kept failing; leave it out.

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
| **Bundled plugin** | A first-party plugin shipped and enabled by default. Today: **CircuitPython** (`plugins/circuitpython`) and **Pygame Zero** (`plugins/pygamezero`). micro:bit follows (Phase 6). |

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

Nu logs the reason, shows it on the Plugins tab (*Couldn't load*, with the
details), and starts without the plugin if it:

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
  the learner agrees, it isn't loaded the next time Nu starts, and the
  Plugins tab says it was switched off after errors. Switching it back on
  there starts the count afresh.

An error counts as the plugin's when the plugin's own modules appear in the
traceback, or when core code was running on one of its modes (for example
`MicroPythonMode` code it inherits).

**Threads** are covered too. If an error ends a thread your plugin started
(a `threading.Thread`, a `QThread` or a `QRunnable`), it's reported the same
way, with the thread's name in the log. The dialog itself is always shown
from Nu's main thread, so it's safe. Errors in threads that aren't a plugin's
go to Nu's log as well. As ever, never touch Qt widgets from your own
threads: send a signal to the main thread instead.

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

Learners do it on the Plugins tab (see [Managing plugins](#managing-plugins)),
which keeps the plugin's id in `disabled_plugins` in Nu's `settings.json`. A
switched-off plugin isn't even imported, so its `register` isn't called.

## The API

Everything a plugin needs is imported from `mu.plugin`. Nothing else in `mu`
is public: `mu.modes`, `mu.logic` and `mu.interface` can change in any
release.

| Name | What it is |
|---|---|
| `PLUGIN_API_VERSION` | The API version this Nu provides, e.g. `"0.5"`. |
| `Plugin` | Base class for a plugin. |
| `ModePlugin` | A `Plugin` that registers one or more modes for you. |
| `Mode` | Base class for a mode (today's `BaseMode`). |
| `MicroPythonMode` | A `Mode` with serial REPL, plotter and board detection, for MicroPython devices. |
| `Device` | A board a `MicroPythonMode` found: what its `compatible_board(port)` returns, and `find_devices()` lists. *(0.3)* |
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
    description = "Adds My mode, for doing my thing."
    api_version = "0.5"

    def register(self, host):
        """Called once when the plugin loads. Do all wiring here, through
        `host`."""

    def unregister(self, host):
        """Optional. Called when the plugin unloads. Modes it registered are
        removed for you; undo anything else here."""
```

`name` and `description` *(0.4)* are what the Plugins tab shows: keep the
description to one sentence saying what the plugin adds. Both are optional; a
plugin without a `name` is called by its id.

If `register` raises, the plugin is logged and skipped, and any modes it had
already registered are removed. A broken plugin never stops Nu starting.

For the common case of a plugin that only adds modes, use `ModePlugin`:

```python
from mu.plugin import ModePlugin

class MicrobitPlugin(ModePlugin):
    name = "micro:bit"
    description = "Adds micro:bit mode, for the BBC micro:bit."
    api_version = "0.5"
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
If matching on USB ids isn't enough, override `compatible_board(port)` (`port`
is a Qt `QSerialPortInfo`): return a `Device` for a port that is your board, or
`None`. Build it as
`Device(vid, pid, port_path, serial_number, manufacturer, self.name,
self.short_name, board_name)`; `self.port_path(port.portName())` gives the
path. CircuitPython does this, asking `adafruit-board-toolkit` which ports are
CircuitPython REPLs.

`MicroPythonMode` brings `toggle_repl` and `toggle_plotter`, handlers for a
Serial and a Plotter button that connect to the board Nu has detected (and
tell the learner if there's none). Offer the Plotter only if
`self.host.plotter_available`.

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
| `shared_apis()` | The autocomplete entries every Python has, MicroPython and CircuitPython included (built-ins, `str`/`list`/`dict` methods), as a new list: what a board mode's `api()` builds on. *(0.3)* |
| `plotter_available` | `True` if Nu can show the plotter (the optional Qt Charts package is installed). A property. *(0.3)* |
| `current_device` | The board picked in the device selector (a `Device`), or `None`. A property; use it instead of `self.editor.current_device`. *(0.5)* |
| `data_dir(name)` | A folder of your plugin's own in Nu's data folder, `<data folder>/<name>`, made if missing (`name` is a plain folder name, normally your plugin's id). For downloads and caches, not the learner's work. *(0.5)* |
| `log_command(argv, cwd=None, note=None)` | Add a command to **What Nu ran** (and Nu's log), next to uv's: `argv` as the learner could type it, `note` for anything they should know (e.g. "Nu did this through mpremote's Python API"). Returns a record: call `add_output(text)` as output arrives and `finish(exit_code, output=None)` when done (0 for success). Safe from any thread. *(0.5)* |
| `settings(namespace)` | A `PluginSettings` with `get(key, default=None)` and `set(key, value)`. Values are saved with the user's settings under `plugins.<namespace>` and must be JSON-serialisable. |
| `logger(name)` | A logger writing to Nu's log as `mu.plugins.<name>`. |
| `api_version` | The `PLUGIN_API_VERSION` this Nu provides. |

The core uses `load_plugin`, `unload_plugin`, `modes`, `plugins`,
`plugin_records`, `describe_plugins`, `set_plugin_enabled` and
`plugins_folder` (the last four for the Plugins tab); plugins shouldn't need
them.

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
- **Installing a plugin and its learner-env packages from Nu** (Phase 5d; see
  the [roadmap](#roadmap-installing-plugins)).
- **Translations for plugins.** Bundled plugins use Nu's own message catalog
  (their strings are extracted with Nu's); a community plugin's strings aren't
  translated yet.

### What changed in 0.5

0.5 adds what the micro:bit plugin needs to stay on the API: `Host.log_command`
(so a plugin's equivalent commands show in **What Nu ran**, as uv's do),
`Host.current_device` (the selected board, without `self.editor`) and
`Host.data_dir` (a folder for downloads such as firmware). Nothing was removed,
but a 0.4 plugin needs its `api_version` changed to `"0.5"`.

### What changed in 0.4

0.4 adds `Plugin.description`, the sentence the Plugins tab shows under your
plugin's name. Nothing was removed, but a 0.3 plugin needs its `api_version`
changed to `"0.4"`.

### What changed in 0.3

0.3 adds what a MicroPython-family mode needs, so CircuitPython could become a
plugin: `Device`, `Host.shared_apis()` and `Host.plotter_available`. Nothing
was removed, but a 0.2 plugin needs its `api_version` changed to `"0.3"`.

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
- An incompatible plugin is logged and skipped, never a crash. The Plugins
  tab shows it as *Couldn't load*, saying it was written for a different
  version of Nu, with the exact versions in its details.
- The API is bumped deliberately, with a short compatibility-shim window. It
  stays at 0.x until the micro:bit plugin (Phase 6) has proven it.

## Trust & safety

Plugins are **arbitrary in-process Python** — there is no sandbox. The trust
model is the same as `pip`: *you chose to install it.* The Plugins tab says so
in plain words: a plugin runs inside Nu with the same access to your computer
as Nu itself, so only add plugins you trust, as you'd only install programs
you trust. When Nu can install plugins (see below), it will show the real `uv`
command before running it. (A curated/signed index is a possible future, not a
v1 guarantee.) In-process plugins can't be meaningfully sandboxed without a
far larger redesign, which is out of scope.

## Roadmap: installing plugins

!!! note "Design only"

    This is the plan for Phase 5d. None of it is built yet: today a learner
    adds a plugin by putting it in the plugins folder.

**The constraint.** In the installers, Nu runs from the environment Briefcase
bundled into the app. It can't be installed into: it's read-only (`Program
Files`, a signed `.app`, an AppImage's squashfs), and changing it would break
Nu's signature and its next upgrade. So entry-point discovery only sees the
bundled plugins there, and a plugin from PyPI needs somewhere else to live.

**1. A plugin environment.** A virtual environment of its own under Nu's data
folder (`DATA_DIR/plugin-env`, next to the learner's `mu_venv-…`), made the
first time a plugin is added with

```bash
uv venv --python <Nu's own Python> <DATA_DIR>/plugin-env
```

Using Nu's own interpreter (`sys.executable`; in the installers, the Python
Briefcase bundled) gives it exactly Nu's Python version and ABI, so a plugin's
compiled extensions match the process that imports them. It's separate from
the learner's environment on purpose: plugin code runs *inside* Nu, the
learner's programs run in their own process, and a learner removing a package
must never break Nu. A small `plugin-env.json` records the Python version and
the plugins the learner added, so the environment can be rebuilt (see the open
questions).

**2. On `sys.path` before discovery.** At startup, before `discover()`, Nu
adds the plugin environment's `site-packages` to `sys.path` with
`site.addsitedir` (so `.pth` files work), *after* Nu's own entries, so Nu's
own packages (PyQt6 above all) always win. `importlib.metadata` then finds the
plugin's `mu.plugins` entry point like any installed package's; the Plugins
tab shows it as *Installed package*. Nothing else about loading changes:
disabling, error isolation and the tab work as they do now.

**3. Installing.** The Plugins tab grows an **Add a plugin…** button. It asks
for a package name (for example `nu-microbit`), shows what PyPI says about it
(summary, author, homepage) with the trust note, and the exact command it will
run:

```bash
uv pip install --python <DATA_DIR>/plugin-env/bin/python nu-microbit
```

The command goes through the same `Uv` wrapper as the learner's packages, so
it's in **What Nu ran** and the log, and its output streams into the same
progress window. Like switching, an added plugin loads at the next start.
**Add from a file…** takes a `.whl` the teacher downloaded, which works
offline.

**4. The plugin's packages for the learner.** A plugin's `learner-env` extra
(see [Packages for the learner's environment](#packages-for-the-learners-environment))
is read from the newly installed package's metadata and installed into the
learner's environment straight away, through the same command log:

```bash
uv pip install --python <the learner's environment's Python> <its learner-env requirements>
```

`wheels.baseline_packages()` already includes every installed plugin's extra,
so a rebuilt learner environment gets them too, once the plugin environment is
on `sys.path`.

**5. Removing.** A plugin in the plugin environment gets a **Remove** button
(bundled and plugins-folder plugins don't: switch them off, or delete the
file):

```bash
uv pip uninstall --python <DATA_DIR>/plugin-env/bin/python nu-microbit
```

### Open questions

- **PyQt6 and the other packages Nu already has.** A plugin depends on Nu, and
  so, through it, on PyQt6. Installing it must not put a second PyQt6 (or a
  different QScintilla) into the plugin environment: Nu's copy is the one
  imported, and a mismatched one could only cause confusion. Candidates, to
  prototype: a `--constraint` file pinning every package Nu has to its exact
  version (from `importlib.metadata`) together with a `--no-deps` install of
  the packages Nu provides, or a `.pth` file in the plugin environment that
  makes Nu's own packages visible so uv treats them as already installed.
  Plugins should not list `nu-editor` itself as a dependency.
- **Upgrading Nu.** A new Nu may bring a new Python (3.11 → 3.12): the plugin
  environment then has to be rebuilt and its plugins reinstalled, as the
  learner's environment already is. A new plugin API version skips plugins
  that haven't caught up, with the reason on the tab; an **Update** button
  (`uv pip install --upgrade`) would help.
- **Offline.** Installing by name needs PyPI; a wheel file doesn't. Should
  the installers carry a small set of vetted plugins' wheels, as they carry
  the bundled ones?
- **Uninstalling leaves dependencies behind** (`uv pip uninstall` removes only
  what it's given). Rebuilding the plugin environment from the recorded list
  is cheap with uv and may be simpler than tracking dependencies. The
  learner-env packages a plugin brought stay too, since the learner's own
  programs may use them.
- **Trust when installing by name:** typosquatting on PyPI. Showing the
  package's metadata before confirming helps; a curated list is a possible
  future.
- **Same id twice.** An installed plugin and a plugins-folder plugin with the
  same id: the installed one wins today. Is that still right when the learner
  installed one themselves?

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
and tests. `plugins/circuitpython/` is the one for a board: a
`MicroPythonMode` with its own board detection, the learner's files on the
board's drive, Serial and Plotter buttons, and a dependency of its own
(`adafruit-board-toolkit`) in the environment Nu runs from.

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
`.github/workflows/test.yml`, `docs.yml` and `build.yml`, and
to mkdocstrings' `paths` in `mkdocs.yml`. Then `uv lock`.

If a bundled plugin's mode used to be built in, keep its `short_name`: saved
sessions and the `mode` setting refer to it. (If the plugin is switched off or
missing, Nu asks the learner to pick a mode at startup, as it does for any
mode it doesn't know.)

## See also

- [Modes](modes.md) — the mode concept the plugin `Mode` formalizes.
- [API reference](api.md#muplugin) — generated from the `mu.plugin`
  docstrings.
- `TODO.md` — Phase 5 (plugin architecture) and Phase 6 (the micro:bit plugin).
