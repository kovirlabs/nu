# nu — Modernization & Lightening Plan

A continuation of the [Mu editor](https://github.com/mu-editor/mu). Goal: keep it
usable and make it **friendly to rapid, agile development** — nimble and easily
maintained — *without* a giant overhaul. This file is the working plan; check
items off as they land.

## Strategy

Cut surface area **first**, then do the Qt6 / modern-Python engine swap on the
smaller codebase (less to port, lower risk). Keep the test suite green at every
step — it's what makes the bigger changes safe.

Baseline test suite (Python 3.8 + PyQt5, pre-changes): **1120 passed, 20 skipped**.
Current baseline (Python 3.11–3.14 + PyQt6): **929 passed, 20 skipped**
(924 after Phase 4a + 5 new `find_uv` tests in the Phase 4 packaging work).
Run headless with:
```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -p no:randomly -q
```
(On a headless box without Mesa, Qt6 needs `libEGL.so.1` on `LD_LIBRARY_PATH`
even for the `offscreen` platform plugin.)

## Decisions locked in

| Question | Decision |
|---|---|
| License | **Stay GPLv3** → keep PyQt5/QScintilla; modernize *within* Qt |
| GUI framework | **Keep Qt** (kivy/tkinter rejected: would lose QScintilla + qtconsole REPL; full rewrite) |
| Qt/Python baseline | **Modernize**: PyQt5 → **PyQt6**, require **Python 3.11+** (verified through 3.14), drop stale pins |
| Modes to keep | **Python3, Debugger, Pygame Zero, CircuitPython** |
| Modes to drop | ESP, Pico, Pyboard, Lego, Snek, **Web** |
| OS targets | **Linux, Windows, macOS** (all three) |

### Resolved decision

- [x] **micro:bit mode — DROPPED** (for now). Its tooling (`uflash` 2.0.0, `microfs` 1.4.5)
  is frozen since 2021 / unmaintained. See 1e below. **Reintroduced** the right way — as a
  modern **plugin** on maintained tooling (`mpremote`/`pyOCD`) — in **Phase 6**, atop the
  **Phase 5** plugin architecture.

---

## Phase 0 — uv dependency workflow ✅ DONE

- [x] `pyproject.toml` mirroring `setup.py` deps; pinned to Python 3.8 for now
- [x] `uv sync` installs the pinned PyQt5 stack into `.venv` (managed CPython 3.8)
- [x] Added `setuptools` dep (runtime `pkg_resources` import; see Phase 2 cleanup)

## Phase 1 — Lighten & retool (low risk)

**1a. Drop the 5 cleanly-separable modes** (esp, lego, pico, pyboard, snek): ✅ DONE
- [x] Delete `mu/modes/{esp,lego,pico,pyboard,snek}.py`
- [x] Delete API stubs `mu/modes/api/{esp,lego,pyboard,snek}.py`; update `api/__init__.py`
- [x] Unregister in `mu/modes/__init__.py` and `mu/app.py` (imports + `setup_modes` dict)
- [x] Remove `ESPFirmwareFlasherWidget` from `interface/dialogs.py` + the `esp` tab in `AdminDialog`
- [x] Remove `SnekREPLPane` from `interface/panes.py` + `add_snek_repl` from `interface/main.py`
- [x] Delete `mu/contrib/esptool.py` (only the ESP flasher used it; ~5.5k lines)
- [x] Delete tests `tests/modes/test_{esp,lego,pico,pyboard,snek}.py` + ESP/snek tests in
  `tests/interface/test_{dialogs,panes,main}.py`; prune unused imports
- [x] Suite green: **1033 passed, 20 skipped** (was 1120; 87 mode tests removed); flake8 clean
- Remaining modes: `python, circuitpython, microbit, web, debugger, pygamezero`

**1b. Drop Web mode** (separate step — threads through core session code): ✅ DONE
- [x] `mu/modes/web.py` + `api/flask.py` (FLASK_APIS, ~2.1k lines)
- [x] `interface/dialogs.py` `PythonAnywhereWidget` + `AdminDialog` web/PythonAnywhere blocks
- [x] `interface/workers.py` `PythonAnywhereWorker` (whole file removed)
- [x] `interface/main.py` `upload_to_python_anywhere` + handlers + import (+ unused QThread/QProgressDialog)
- [x] `logic.py` `pa_username`/`pa_token`/`pa_instance` session save/load + settings
- [x] `mu/wheels/__init__.py` flask wheel entry
- [x] Corresponding tests (test_web, test_workers deleted; test_dialogs/main/logic pruned); suite green
- [x] Suite green: **990 passed, 20 skipped**; flake8 clean. Modes: python, circuitpython, microbit, debugger, pygamezero

**1d-micro. Drop micro:bit mode** (split in two — the mode, then its orphaned subsystem):
- [x] Mode + API stub + registration; `MicrobitSettingsWidget`, `get_microbit_path`,
  `minify`/`microbit_runtime` session+settings handling; **vendored `uflash.py` (1.86 MB)**; tests.
  Suite green: **932 passed, 20 skipped**; flake8 clean. Modes: python, circuitpython, debugger, pygamezero.
- [x] **Removed the orphaned serial file-transfer subsystem**: `FileManager` (`modes/base.py`),
  `FileSystemPane` + device/local file-list classes (`interface/panes.py`),
  `Window.add_filesystem`/`remove_filesystem` (`interface/main.py`), and the **vendored
  `microfs.py`** + tests. `mu/contrib/` is now empty (all of uflash/esptool/microfs gone).
  Suite green: **889 passed, 20 skipped**; flake8 clean.

**1c. Toolchain**: ✅ DONE
- [x] Adopted **ruff** for dev lint+format (replaces flake8 + pycodestyle + pyflakes + black
  *as dev tools*). `pyflakes` + `pycodestyle` (via the `flake8` pin) and `black` stay as
  **runtime** deps — `logic.py` uses pyflakes/pycodestyle for the in-editor code checker and
  black for the "Tidy" button.
- [x] Repointed `make.py` / `Makefile` targets at ruff: `make lint` (ruff check),
  `make format` (ruff format --check), `make tidy` (ruff format), `make check` =
  clean + format + lint + coverage. Dropped the `PYFLAKES_BUILTINS=_` dance — the gettext
  `_` builtin is now declared in `[tool.ruff] builtins`.
- [x] ruff config lives in `pyproject.toml` `[tool.ruff]`; removed the `[flake8]` section
  from `setup.cfg`. **Unified line-length to 88** for both format and the `E501` lint check
  (retired the old black-79 / flake8-88 split), so the tree was reformatted to 88 columns
  (mostly the modern "blank line after module docstring" rule). Fixed one new finding
  (`E721` in `mu/app.py`: `!=` → `is not` for an exception-type comparison).
- [x] Suite still green: **889 passed, 20 skipped**; `ruff check` + `ruff format --check` clean.

**1d. Packaging consolidation**: ✅ DONE
- [x] Moved all metadata into `pyproject.toml` with the **hatchling** backend; **deleted
  `setup.py` + `setup.cfg`**. pytest/coverage config moved to `[tool.pytest.ini_options]` /
  `[tool.coverage.run]`; lint config already in `[tool.ruff]`. Version stays in
  `mu/__init__.py` via `[tool.hatch.version]` (still the single source the installer tooling
  parses). Distribution name preserved as **`mu-editor`** v1.2.2 (package dir stays `mu`).
- [x] `make dist` / Makefile now run `python -m build` (was `setup.py sdist bdist_wheel`);
  `--cov-config` repointed to `pyproject.toml`. Build verified: sdist + wheel produced, all
  data files (resources/locale/wheels/`conf`) included, metadata correct (`mu-editor` 1.2.2,
  `License-Expression: GPL-3.0-or-later`, entry point `mu-editor = mu.app:run`).
- [x] **black bumped to `>=24`** and the `click<=8.0.4` clamp dropped (old black crashed on
  Python 3.12+; ruff is the dev formatter so the bump can't reflow the tree). Enabled
  **Python 3.14**: stack resolves + suite green on 3.14 (PyQt6 6.11, black 26). Kept
  `requires-python = ">=3.11"` (don't strand 3.11–3.13 users); classifiers list 3.11–3.14.
- NOTE: the original "once installers are confirmed working" caveat is **deferred** — the
  maintainer will re-validate the pup-driven installers (`make win64`/`macos`/`linux` +
  `build.yml`) separately. Those still reference old Python and are untouched here.

## Phase 2 — Modern Python + Qt6 (the one "medium" change) ✅ DONE

- [x] PyQt5 → **PyQt6** (`PyQt6-QScintilla` 2.14, `PyQt6-Charts`); bump
  `qtconsole`/`jupyter-client`/`ipykernel` to current; **deleted the FIXME pins**
  (pyzmq/jupyter-client/ipykernel/ipython_genutils). Dropped the old "skip Qt on
  ARM" markers — PyQt6 ships aarch64 wheels.
- [x] Mechanical port: scoped enums (`Qt.AlignBottom` → `Qt.AlignmentFlag.AlignBottom`),
  `exec_()` → `exec()`, `QAction`/`QShortcut` moved to `QtGui`,
  `QtChart` → `QtCharts`, `QChart.setAxisX/Y` → `addAxis`+`attachAxis`,
  `QDesktopWidget` → `QApplication.primaryScreen()`, `QFontDatabase` static API,
  `setToolButtonStyle`/`QIODevice.OpenModeFlag` enums, dropped the Qt5-only
  `AA_*HighDpi*` attributes (always-on in Qt6).
- [x] `requires-python = ">=3.11"`; `.venv` refreshed to managed CPython 3.11.
- [x] Migrated `pkg_resources` → `importlib.resources`; dropped the `setuptools` dep.
- [x] Suite green on the new stack: **889 passed, 20 skipped**; flake8 + black clean.
- NOTE: `black`/`click` left at their existing pins (the `<22.1.0` ceiling
  resolves to a build that runs on 3.11). Bumping black + reformatting the tree
  belongs to the toolchain work in **Phase 1c**, kept out of this diff.

## Phase 3 — Verify packaging & CI

- [ ] Confirm AppImage / macOS `.app` / Windows installer build on the PyQt6 base.
  **Superseded by Phase 4**: the stale `pup` pipeline (alpha, Py3.8-only, 3.10-capped,
  needs a macOS fork + custom Docker image) is being replaced by **Briefcase**, and the
  baked-in venv that forced a venv-capable bundled Python is being replaced by a uv-driven
  model. Installer work continues there.
- [x] Trimmed CI (`.github/workflows/test.yml`) to the supported range: matrix is now
  Python **3.11 + 3.14** on ubuntu/macOS/Windows, with 3.12 + 3.13 added on Linux only.
  **Deleted the two PyQt5-era jobs** (`test-arm` Debian-buster + `test-pios` Raspberry Pi OS
  stretch/buster) — QEMU-emulated, slow, and incompatible with the PyQt6/Py3.11 stack.
  Added the Qt6 apt deps (`libxcb-cursor0`/`libegl1`/`libgl1`). `build.yml` left for the
  installer work above.

## Phase 4 — uv-driven environments + Briefcase installers

A deliberate departure from Mu's "hide everything" ethos: make the Python environment a
**real, visible, scriptable** thing (good pedagogy), which also dissolves the packaging
constraint — the app's own interpreter no longer needs to be venv-capable because **uv**
manages the kid's-code Python separately. Decisions (maintainer, 2026-06): PEP 723
`uv run` **and** explicit `uv` buttons; progressive disclosure to keep the beginner-first
feel; offline-first via bundled assets; **Briefcase** for native installers.

**4a. Replace the baked-in venv with uv** (on the current stack — testable before packaging):
- [x] **uv wrapper** (`find_uv` + `Uv` in `mu/virtual_environment.py`): thin QProcess
  wrappers around `uv venv`, `uv pip install/uninstall/list`, and `uv run`. The binary is
  resolved at runtime by `find_uv()` (`MU_UV` override → `uv` on `PATH`); pinning/bundling
  a per-platform `uv` is deferred to 4c.
- [x] **Venv creation now goes through uv**: `VirtualEnvironment.create_venv` calls
  `uv venv --python <sys.executable> --seed <path>` (which yields the same
  `bin/python` + `bin/pip` + `pyvenv.cfg` layout, so the pip-based baseline-wheel install
  downstream is untouched) instead of `python -m virtualenv`. Dropped the `virtualenv`
  runtime dep, added `uv>=0.5`, regenerated `uv.lock`. User-package install/remove/list
  already route through `uv pip` (b267f14).
- [x] **"Activate" the env for spawned user code**: `VirtualEnvironment.activation_vars()`
  returns `VIRTUAL_ENV` (→ the user's env) + a `PATH` with the env's `bin`/`Scripts`
  prepended, applied at **both** spawn paths — `PythonProcessPane.start_process` (the Run
  path: Python 3, Pygame Zero, debugger, which all share it) and `KernelRunner.start_kernel`
  (the REPL/Jupyter kernel, which sets `os.environ` directly; `stop_kernel` restores it).
  So user code runs with the env *activated*, not merely launched by interpreter path. NB
  the startup strip of any *inherited* `VIRTUAL_ENV` (`app.run`, the old pgzero fix) stays:
  we now set the variable explicitly per-child to the **user's** env (the
  historically-correct target).
- [x] Suite green: **924 passed, 20 skipped**; ruff check + format clean. Added direct
  tests for the uv wrapper (`find_uv`/`UvNotFound`/`Uv`, previously entirely uncovered),
  for `activation_vars`, and for the activation wiring at both spawn paths.
- [ ] **Still to do in 4a — GUI validation** (can't be done headlessly): spot-check the
  activation across modes on a real display — especially Pygame Zero, whose interaction
  with `VIRTUAL_ENV` was the original reason for the startup strip — and the REPL. Wiring
  `uv run` to the "Run" action for PEP 723 inline deps, and scoping the UI to the env
  (indicator + package list), land with 4b.

**4b. Env UX (progressive disclosure):**
- [ ] "Environment: <name>" indicator + package list scoped to the active env.
- [ ] `uv` buttons (new env / add package / show packages) that **echo the real command**
  into a log/console pane — the transparency is the lesson.
- [ ] PEP 723: "Run" uses `uv run` so inline `# /// script` dependencies auto-resolve.
- [ ] Advanced multi-env create/switch, hidden by default.

**4c. Bundle assets for offline:**
- [x] Vendor a pinned `uv` binary per platform — achieved via the PyPI **`uv` wheel** in
  the Briefcase `requires` (so it lands in `app_packages/bin/uv`); `find_uv()` now resolves
  it through `uv.find_uv_bin()` at runtime, no `MU_UV`/`PATH` needed. (No separate
  standalone-binary download/MU_UV plumbing required after all.)
- [x] **Bundle a CPython for the learner's env** (offline first run; regressed in b2 and
  fixed 2026-10). The original plan reused the app's interpreter via
  `uv venv --python <sys.executable>`, but in a packaged app that's Briefcase's launcher
  stub (crashed Windows b1); b2's `--python X.Y` workaround made uv download a CPython
  on machines without a matching one. Now `python -m mu.wheels --package` also bundles
  the python-build-standalone build for the platform + a pip wheel
  (`mu/wheels/python/`); first launch extracts it to `DATA_DIR/python/<build>/` and runs
  `uv venv --python <it> --seed --no-index --find-links …`. Verified offline end to end
  on macOS arm64 (network blocked, empty uv cache, no managed/system Python).
  Follow-ups: verify on Windows + Linux installers; old extracted builds under
  `DATA_DIR/python/` aren't cleaned up after upgrades (~70 MB each); check the archive
  survives Apple notarization once signing lands.
- [x] Build a wheelhouse — `python -m mu.wheels --package` builds `mu/wheels/<version>.zip`
  (pgzero/pygame/ipykernel + deps), bundled via `sources`; the first-run baseline install
  is offline (pip from the zip, see `install_from_zipped_wheels`). Bumped the stale
  `pygame<2.1.3` cap (no 3.12+ wheels) → `pygame>=2.6`. (`UV_FIND_LINKS` not wired: only
  *new* user-package installs hit the network, which is expected; baseline is already
  offline.)

**4d. Briefcase packaging:** ✅ (pending maintainer CI validation on Win/macOS)
- [x] Added `[tool.briefcase]` + `[tool.briefcase.app.mu]` (+ per-OS sections) to
  `pyproject.toml`: PyQt6 stack + runtime `requires`, `sources=["mu"]`, icon, license. The
  app starts via `mu/__main__.py` (`python -m mu`), no shim. `briefcase` added to the
  `package` extra.
- [x] **Build all three in CI** (`build.yml` rewritten): `windows-latest → MSI`,
  `macos-latest (Apple Silicon) → zipped .app`, `ubuntu-latest → AppImage`, on
  `workflow_dispatch` + `v*` tags; a tag also publishes a GitHub Release with the
  installers. (Started on Intel `macos-13`; moved to arm64 in b1 when the Intel runners
  stalled. The baseline wheels are fetched for the runner's arch.)
- [x] Repointed `make.py`/`Makefile` `win64`/`macos`/`linux` at Briefcase (dev/local).
- [x] **Validated locally on Linux**: `briefcase create`+`build` produce a working AppImage
  headlessly (no Docker); the bundled interpreter imports PyQt6 + `mu`, and `find_uv()`
  resolves the bundled `uv` on a uv-less machine. Fixed a packaging-blocker found this way:
  the Jupyter-kernel install spawned `sys.executable -I -m ipykernel`, which can't import
  ipykernel in a frozen app (deps live in `app_packages`, off a fresh subprocess's path) and
  would crash startup — now runs via the **venv** interpreter (which carries ipykernel as a
  baseline package). Also fixed a tuple `%`-format bug in `mu/wheels` that masked download
  errors.
- [ ] **Maintainer to validate**: download the Windows MSI (and macOS dmg) from a
  `build.yml` run and confirm install + launch + REPL on real hardware. Linux AppImage
  validated here.
- [ ] **Signing** (deferred): macOS notarization (Apple Developer cert) + Windows
  Authenticode need secrets in `build.yml`, else users hit Gatekeeper / SmartScreen.
  Unsigned-but-building first; signing after.

**4e. Retire pup:** ✅ DONE (2026-10, after b1–b3 built green on all three OSes)
- [x] Removed the pup `make` targets (`win32`, `win64-pup`, `macos-pup`, `linux-pup`,
  `linux-docker`), `_PUP_PBS_URLs` + `_build_windows_msi` in `make.py`, and the
  `carlosperate/pup` fork usage.
- [x] Removed pup/PyInstaller-era files from `package/` (`README.rst`, `dmg_settings.py`,
  `install_pip3.sh`, `qt.conf`, `mac_icon.icns`, `win_icon.ico`); Briefcase uses
  `package/icons/mu.*`.
- [x] Removed `conf/` (hand-written `.desktop`/AppStream/micro:bit udev rule) and the
  2017 Raspberry Pi `debian/` packaging (PyQt5, setup.py-based, unbuildable here) that
  consumed it. Briefcase emits the AppImage's `org.kovir.mu.desktop` itself (its AppImage
  template ships no AppStream metainfo; re-add one only if we target software centres).
- [x] App-ID realigned: `setDesktopFileName("org.kovir.mu")` to match Briefcase.

## Phase 5 — Plugin architecture (shell the core; modes become plugins)

**Long-term direction.** Shrink Nu to a lean **core** — editor, REPL, plotter, the
uv-managed environment, and a **plugin host** — and push capability out into **plugins**.
The specialized modes ship as bundled, default-enabled plugins; the community can write and
install their own. This is what lets "reintroduce micro:bit" (Phase 6) be a *plugin* rather
than a fork-wide change, and it leans directly on the Phase 4 uv model (a plugin is an
installable package; "add a plugin" is a uv install).

### Decisions locked in (maintainer, 2026-06)

| Question | Decision |
|---|---|
| Discovery / distribution | **Entry points** (installable packages, `mu.plugins` group) **+ a drop-in dir** for local/dev |
| Core vs plugin boundary | **Core keeps Python 3 + Debugger** (plain editing/run/REPL/debug); CircuitPython, Pygame Zero, micro:bit, … are plugins |
| Plugin API | **Stable, versioned API up front** — a documented façade over the editor, not raw internals |
| Source layout & distribution | Bundled plugins live **in-repo** under `plugins/*` as a **uv workspace** of independently-published PyPI packages; **extract** one to its own repo only once the API is stable *and* it needs to diverge (separate maintainer / release cadence / licence). Community plugins live in their own repos. |

NOTE (packaging rationale): three *independent* axes — **loading** (entry points, fixed),
**distribution** (a real installable package, optionally on PyPI), and **source location**
(this repo vs its own). Keeping bundled plugins in a monorepo *now* keeps the volatile-API
phase **atomic** (change the API + all bundled plugins in one PR) and **dogfoods** the
community path (same entry-point install), while independent packaging makes "graduate to its
own repo later" a trivial directory move. Purely-local plugins need no PyPI at all — the
drop-in dir covers them.

**5a. Define the plugin API + host (no behavior change yet):** ✅ DONE
- [x] `mu/plugin/` package: a **versioned** API (`PLUGIN_API_VERSION = "0.1"`), a `Plugin`
  base (`register(host)`/`unregister(host)`) and a `ModePlugin` that registers `mode` /
  `modes`. `BaseMode` is re-exported as `mu.plugin.Mode` (and `MicroPythonMode` too, for
  board plugins like micro:bit); modes get a `host` attribute.
- [x] **Host façade** (`mu/plugin/host.py`): `register_mode`, `show_message`, `confirm`,
  `show_status`, `current_text`/`current_path`, `workspace_dir`, `open_directory`,
  namespaced persisted `settings(ns)` (under `settings["plugins"][ns]`), `logger(name)`.
  Kept to what the existing modes actually use; panes, plugin-shipped icons and env
  installs are left out until a plugin needs them (5c/5d/Phase 6).
- [x] Compatibility: same MAJOR and MINOR ≤ core's (exact MINOR while 0.x); an incompatible
  plugin, or one whose `register` raises, is **logged and skipped**, and modes it registered
  are rolled back.
- [x] The built-in modes are now registered through a `Host` in `app.setup_modes` (same
  four modes, same keys) — the path plugins will take.
- [x] `docs/plugins.md` rewritten from proposal to the real API; `mu.plugin` added to
  `docs/api.md`; a runnable template plugin in `plugins/example/` (entry point + mode using
  only `mu.plugin`), with tests. 100% coverage of `mu/plugin`.
- NOTE (gaps found while building 5a, for later steps): mode/action icons are resolved only
  from `mu/resources/images` (an action's `name` doubles as its icon *and* toolbar slot key,
  so it can't clash with core buttons); the core still names modes in
  `interface/dialogs.py` (`["python", "pygamezero"]`) and `logic.py` (copies Pygame Zero
  assets); `wheels.mode_packages` is a single global list. Fix these in 5b–5d.

**5b. Plugin discovery + loading:** ✅ DONE
- [x] `mu/plugin/loader.py` discovers installed plugins via `importlib.metadata` entry
  points (group `mu.plugins`); the id is the entry point name.
- [x] Also scans a **drop-in dir** (`config.DATA_DIR/plugins/`, created if missing): each
  `name.py` / `name/__init__.py` is a plugin with id `name` (its `PLUGIN` attribute, else
  its single `Plugin` subclass). Imported under its own name so relative imports work; a
  name that's already importable (`json.py`) is refused instead of shadowing it.
- [x] `app.setup_modes` registers the built-in modes, then `load_plugins(host)`; a
  `PluginRecord` per discovered plugin (loaded / disabled / skipped + reason) is kept on
  `host.plugin_records` for the 5e Plugins tab. Enabled/disabled **registry** persisted as
  `settings["disabled_plugins"]` (`set_plugin_enabled`); a disabled plugin isn't imported.
- [x] **Error isolation**: a plugin that's disabled, a duplicate id, fails to import
  (incl. `SystemExit`), is API-incompatible or fails `register` is logged and skipped.
  `DeviceList.check_usb` now also survives a mode whose `find_devices` raises (it polls
  every mode each second, so one broken plugin would otherwise crash Nu via `excepthook`).
- [x] Verified end to end: the example plugin installed editable + a drop-in plugin both
  appear in the mode picker; a broken drop-in is skipped. Tests point the drop-in dir at a
  temp folder (`tests/conftest.py`).
- [x] **Runtime isolation** (`mu/plugin/errors.py`): plugin errors no longer crash Nu.
  `Host.register_mode` wraps a plugin mode's core-called methods (`activate`, `actions`,
  `api`, `workspace_dir`, `stop`, `find_devices`, …) to report and return a safe fallback;
  `app.excepthook` first asks `plugin_errors.handle_uncaught`, which attributes the
  traceback to a plugin (its modules, or core code running on one of its modes) so errors
  in button handlers/timers/signals are reported instead of exiting. The learner gets a
  rate-limited dialog (30 s / one at a time; status bar otherwise), the log gets the
  traceback once per distinct error, and after 3 errors Nu offers to switch the plugin off
  (`disabled_plugins`). `mu.plugin.PluginError(message, information)` is the interface for
  *expected*, learner-fixable problems. Verified in the real app with a drop-in plugin
  whose timer raises every 2 s: Nu keeps running.
- NOTE (open): errors in a plugin's **threads** go to `threading.excepthook` (logged to
  stderr, not the log file, no dialog) — they can't crash Nu, but they're easy to miss.
  Route them to the log in 5e.
- NOTE (open, 5d): in **installers** Nu runs from Briefcase's bundled env, which users
  can't install into, so entry-point discovery only sees bundled plugins there; the
  drop-in folder is the only user route until 5d puts a plugin env on `sys.path`.

**5c. Convert the specialized modes to bundled plugins (proof of the API):**
- [ ] Scaffold a `plugins/` **uv workspace** (`[tool.uv.workspace]`): each bundled plugin is
  `plugins/<name>/` with its own `pyproject.toml` + `mu.plugins` entry point — independently
  buildable/publishable, sharing the repo lockfile.
- [ ] Move **CircuitPython** and **Pygame Zero** out of the core set into bundled plugins
  loaded through the same entry-point path (shipped + enabled by default) — they become the
  reference plugins. Keep **Python 3 + Debugger** in core.
- [ ] Relocate each plugin's API stubs (`modes/api/`), wheels, icons, and settings into its
  own package; keep the suite green (port mode tests → plugin tests).

**5d. Plugin dependencies via uv (ties into Phase 4):**
- [ ] A plugin declares its PyPI runtime deps; installing the plugin **uv-installs** the
  package + deps into the user env (or a dedicated plugin env). "Add a plugin" reuses the
  Phase 4b uv buttons and echoes the real command.
- [ ] Offline-first: bundled plugins' wheels ship in the installer wheelhouse (`mu/wheels`).

**5e. Plugin management UX:**
- [ ] A **"Plugins"** admin tab: list bundled / installed / available, enable/disable,
  install/remove — surfacing the real uv command (transparency, as in 4b).
- NOTE on **trust**: plugins are arbitrary in-process Python; the trust model is "you chose
  to install it" (same as pip) — document this plainly. A curated/signed plugin index is a
  possible *future*, not a v1 gate. In-process plugins can't be meaningfully sandboxed
  without a far larger redesign — explicitly out of scope.

NOTE: the versioned API is a real commitment — bump it deliberately and keep a small
compatibility-shim window. micro:bit (Phase 6) is the deliberate **first external-shaped
plugin**: if it can be a clean plugin, the API is good.

---

## Phase 6 — micro:bit, reintroduced as a modern plugin

micro:bit was **dropped in Phase 1** because its desktop tooling (`uflash`, `microfs`) was
frozen/unmaintained. Reintroduce it the right way: as the **flagship plugin** on the Phase 5
system, built entirely on **actively-maintained** tooling. (Maintainer deferred the tech
choice; recommended stack below.)

### Recommended stack

| Concern | Modern tool (replaces) |
|---|---|
| REPL + on-device file transfer | **`mpremote`** — MicroPython's official, maintained tool (replaces vendored `microfs`) |
| Firmware/program flashing | **`pyOCD`** (CMSIS-DAP/DAPLink), with **DAPLink mass-storage drag-and-drop** as a zero-dependency fallback (replaces vendored `uflash` + its 1.86 MB blob) |
| Hex format | **Universal Hex** — one image covers micro:bit **V1 + V2** |
| Board detect | serial VID:PID via the existing `adafruit-board-toolkit` + the mounted `MICROBIT` DAPLink volume |

**6a. Connectivity + flashing foundation:**
- [ ] REPL + file ops (`ls`/`cp`/`rm`/mount) over serial via **`mpremote`**.
- [ ] Flash via **`pyOCD`**; fall back to copying a `.hex` onto the mounted `MICROBIT` drive
  (no drivers needed). Handle **Universal Hex** for V1+V2.
- [ ] Obtain the micro:bit MicroPython firmware by **pin + fetch / installer-bundle** — do
  **not** re-vendor a frozen blob (the original mistake that got the mode dropped).

**6b. The plugin (on the Phase 5 API):**
- [ ] A `nu-microbit` plugin providing the micro:bit **mode**: flash button, REPL,
  file-transfer pane, workspace dir.
- [ ] Reintroduce the **file-transfer pane** (the old `FileSystemPane`, removed in Phase 1d)
  as plugin-owned UI driven by `mpremote`.
- [ ] Ship **modern `microbit` V2 API stubs** for autocomplete/calltips (audio, microphone,
  speaker, `log`, radio, …).

**6c. Packaging + distribution:**
- [ ] Bundle as a default-enabled plugin; include `mpremote`/`pyOCD` wheels for offline
  installers.
- [ ] Also publish to PyPI so it doubles as the **worked example** for community authors.

**6d. Stretch / future:**
- [ ] WebUSB-style direct flashing (pyOCD already gives programmatic flashing; full WebUSB
  parity is a browser concept — lower priority on the desktop/Qt stack).
- [ ] V2 extras: filesystem browser, radio tooling, on-device `log` integration in the pane.

---

## Notes / deferred

- `virtual_environment.py` (~1k lines) powers "install packages from the UI" — being
  **replaced by the uv-driven model in Phase 4** (not dropped; reshaped).
- Orphaned resource icons / locale strings for removed modes are harmless; sweep later.
- 100%-coverage mandate is great for the Qt6 port; can relax to "don't regress" afterward
  if it slows iteration.
- **Translations re-extraction after the in-app "Mu" → "Nu" rename** (i18n follow-up). The
  user-facing app-name strings were renamed from "Mu" to "Nu" (window title, dialogs,
  tooltips, error/confirmation messages, the MOTD, and the Jupyter kernel label) across
  `mu/interface/main.py`, `mu/interface/dialogs.py`, `mu/logic.py`,
  `mu/modes/{base,circuitpython}.py`, and `mu/virtual_environment.py`. Because each is a
  gettext `_()` string, renaming changes its `msgid`, so the existing
  `mu/locale/*/LC_MESSAGES/mu.po` catalogues **no longer match** those strings — they fall
  back to the (English) "Nu …" source until the catalogues are regenerated. **To do:**
  re-extract the `.pot` and merge into the per-locale `.po` (the `make translate*` / babel
  flow), then update the translations. NB heritage strings were intentionally left as "Mu"
  (e.g. the MOTD credit "Mu was created by Nicholas H. Tollervey."), so they keep their
  existing translations.
- ~~**App-ID realignment**~~ — done in 4e: `setDesktopFileName("org.kovir.mu")` matches
  Briefcase's generated `.desktop`; `conf/` removed.
- ~~**Stale `conf/mu.appdata.xml` description**~~ — moot: `conf/` removed in 4e (it
  wasn't shipped by the Briefcase AppImage anyway).
