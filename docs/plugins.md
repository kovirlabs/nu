# Writing a Nu plugin

!!! warning "Status: proposed — not implemented yet"

    This page describes the **planned** plugin system (see **Phase 5** in
    `TODO.md`). The `mu.plugin` package and the host façade below **do not exist
    yet** — the API surface here is a design proposal and *will* change as
    Phase 5 is built. Until it lands, new capability is still added as a built-in
    [mode](modes.md).

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

Two mechanisms (Phase 5b):

1. **Entry points** — the normal, shareable path. A plugin registers a
   `mu.plugins` entry point in its packaging metadata; Nu finds it via
   `importlib.metadata` once the package is installed (e.g. `uv add nu-microbit`,
   or the Plugins tab).
2. **Drop-in directory** — for local/experimental plugins, Nu scans
   `<data>/plugins/` at startup. No packaging required — ideal for a quick
   classroom hack before you publish.

A plugin that fails to import or load is **logged and skipped**; it never takes
the editor down with it.

## Proposed API surface

!!! note

    Everything below is the **proposed** `mu.plugin` public API. Names and
    signatures are subject to change during Phase 5a — this is the design target,
    not a shipped contract.

### The entry point

A packaged plugin advertises itself in its `pyproject.toml`:

```toml
[project.entry-points."mu.plugins"]
microbit = "nu_microbit:MicrobitPlugin"
```

The value points at a `Plugin` subclass (or a factory returning one).

### `PLUGIN_API_VERSION`

```python
from mu.plugin import PLUGIN_API_VERSION   # e.g. "0.1"
```

A semver-ish string the **core advertises**. Each plugin declares the version it
was written against (`Plugin.api_version`); at load the host compares the two and
**warns/skips** on an incompatible major rather than crashing. This is the
commitment that lets a community plugin keep working across Nu releases.

### `Plugin` — the base class

```python
from mu.plugin import Plugin, Host

class MyPlugin(Plugin):
    name = "My Plugin"
    api_version = "0.1"          # the mu.plugin version this targets

    def register(self, host: Host) -> None:
        """Called once when the plugin is enabled. Use `host` to register
        modes, panes, menu items, etc. Do all wiring here."""

    def unregister(self, host: Host) -> None:
        """Optional. Called when the plugin is disabled/unloaded; undo anything
        that won't be cleaned up automatically."""
```

For the common case — "I just want to add a mode" — there is a convenience base
that registers a single mode for you:

```python
from mu.plugin import ModePlugin

class MicrobitPlugin(ModePlugin):
    name = "micro:bit"
    api_version = "0.1"
    mode = MicrobitMode          # a mu.plugin.Mode subclass; registered automatically
```

### `Mode` — what a plugin contributes

`Mode` is the stable, re-exported form of today's `BaseMode`. Plugins import it
from `mu.plugin`, never from `mu.modes.base`:

```python
from mu.plugin import Mode

class MicrobitMode(Mode):
    name = "micro:bit"             # shown in the mode picker
    short_name = "microbit"        # stable id (settings keys, persisted state)
    description = "Write MicroPython for the BBC micro:bit."
    icon = "microbit"              # icon name resolved from the plugin's resources

    def actions(self) -> list[dict]:
        """Toolbar buttons: name / display_name / description / handler / shortcut."""
        return [
            {
                "name": "flash",
                "display_name": "Flash",
                "description": "Flash your code to the micro:bit.",
                "handler": self.flash,
                "shortcut": "F3",
            },
        ]

    def api(self) -> list[str]:
        """API metadata strings powering autocomplete and call tips."""
        return MICROBIT_APIS

    def workspace_dir(self) -> str:
        """Where this mode saves the user's files by default."""
        ...

    # Optional lifecycle hooks
    def activate(self) -> None: ...     # this mode was selected
    def deactivate(self) -> None: ...   # switching away to another mode
    def stop(self) -> None: ...         # editor is shutting down
```

### `Host` — the façade

The single supported surface onto the editor. The core may refactor freely
*behind* this; a plugin only ever sees `Host`.

```python
class Host:
    api_version: str                       # the API version this core supports

    # --- registration (call from Plugin.register) ---
    def register_mode(self, mode_cls: type[Mode], *, default: bool = False) -> None: ...
    def add_pane(self, pane, *, area: str = "bottom") -> None: ...
    def add_menu_item(self, menu: str, text: str, handler) -> None: ...

    # --- editor state (read and drive the running editor) ---
    @property
    def editor(self) -> "EditorProxy": ...   # current tab, text, open/save, mode switch
    @property
    def window(self) -> "WindowProxy": ...   # dialogs, status messages, panes

    # --- the uv-managed environment (Phase 4) ---
    @property
    def env(self) -> "EnvProxy": ...         # install_packages(), interpreter path, run()

    # --- housekeeping ---
    @property
    def resources(self) -> "ResourceProxy": ...        # the plugin's bundled icons/assets
    def settings(self, namespace: str) -> "SettingsProxy": ...   # namespaced persisted settings
    def log(self) -> "logging.Logger": ...
```

The `*Proxy` types are deliberately narrow, documented *views* — **not** the
internal `Editor`, `Window`, or `VirtualEnvironment` objects. Their exact
surfaces are fleshed out in Phase 5a; the rule is that a plugin should never need
to reach past `Host` into `mu`'s internals.

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

- The core advertises `PLUGIN_API_VERSION`; each plugin declares `api_version`.
- Same major ⇒ compatible. The host **warns and skips** on an incompatible major,
  surfaced in the Plugins tab rather than as a crash.
- The API is bumped deliberately, with a short compatibility-shim window.

## Trust & safety

Plugins are **arbitrary in-process Python** — there is no sandbox. The trust
model is the same as `pip`: *you chose to install it.* Install plugins you trust;
the Plugins tab shows the real `uv` command it runs before installing. (A
curated/signed index is a possible future, not a v1 guarantee.)

## A minimal example

```text
my-nu-plugin/
├── pyproject.toml          # deps + [project.entry-points."mu.plugins"]
└── my_nu_plugin/
    └── __init__.py         # MyPlugin(Plugin) + MyMode(Mode)
```

A runnable template will ship in the Nu repo under `plugins/example/` (Phase 5a).
Until the plugin system lands, study the built-in modes in `mu/modes/` — the
plugin `Mode` is a thin re-export of the `BaseMode` they already subclass.

## See also

- [Modes](modes.md) — the mode concept the plugin `Mode` formalizes.
- [API reference](api.md) — once `mu.plugin` exists, its reference will be
  generated here via mkdocstrings.
- `TODO.md` — Phase 5 (plugin architecture) and Phase 6 (the micro:bit plugin).
