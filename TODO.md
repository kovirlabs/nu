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
Current baseline (Python 3.11–3.14 + PyQt6): **1778 passed, 20 skipped** (after the
Windows review, #39/#40; 1638 after Phase 4b part 2; 1572 after the post-Phase 5/6 hardening; 1545 after Phase 6a/6b, 1267 after Phase 4b part 1, 929 after
Phase 4a's packaging work). Run headless with:
```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -q --random-order-bucket=none
```
(On a headless box without Mesa, Qt6 needs `libEGL.so.1` on `LD_LIBRARY_PATH`
even for the `offscreen` platform plugin. Where `/tmp` is mounted `noexec`, add
`--basetemp=<a folder programs can run from>`: one test builds and runs a real venv in
its `tmp_path`.) The suite never reads or writes your real Nu data, workspace or IPython
profile (the root `conftest.py` points them at a throwaway folder before `mu` is
imported), and every test file also passes on its own and in `--random-order`.

## Decisions locked in

| Question | Decision |
|---|---|
| License | **Stay GPLv3** → keep PyQt5/QScintilla; modernize *within* Qt |
| GUI framework | **Keep Qt** (kivy/tkinter rejected: would lose QScintilla + qtconsole REPL; full rewrite) |
| Qt/Python baseline | **Modernize**: PyQt5 → **PyQt6**, require **Python 3.11+** (verified through 3.14), drop stale pins |
| Modes to keep | **Python3, Debugger** (core), **Pygame Zero, CircuitPython** (bundled plugins since Phase 5c); **micro:bit** back as an opt-in plugin (Phase 6) |
| Modes to drop | ESP, Pico, Pyboard, Lego, Snek, **Web** |
| OS targets | **Linux, Windows, macOS** (all three) |

### Resolved decision

- [x] **micro:bit mode — DROPPED** (for now). Its tooling (`uflash` 2.0.0, `microfs` 1.4.5)
  is frozen since 2021 / unmaintained. See 1d-micro below. **Reintroduced** the right way —
  as a modern **plugin** on maintained tooling (`mpremote` + DAPLink drag-and-drop; pyOCD
  deferred) — in **Phase 6**, atop the **Phase 5** plugin architecture: built, opt-in until
  the maintainer's hardware pass.

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

Status: 4a, 4b, 4c, 4d (pending the maintainer's Windows/macOS install check) and 4e done
(4b's environment deletion deferred); signing deferred.

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
- [x] **GUI validation** of the activation, on Linux under Xvfb (2026-11, the parity audit
  and the post-Phase 5/6 sweep): Python 3 Run (environment variables reach the program),
  Pygame Zero Play with the venv activated, the REPL, packages added and removed. A real
  display on Windows/macOS is part of the maintainer's installer check (4d).

**4b. Env UX (progressive disclosure):** part 1 ✅ (2026-11, `feature/env-ux-transparency`),
part 2 ✅ (2026-11, `feature/env-advanced-multi`)
- [x] "Environment: <name>" indicator + package list scoped to the active env. The status
  bar reads `Environment: mu_venv · Python 3.11` in modes with `uses_user_environment`
  (hidden in CircuitPython/the debugger); the name is the env folder without its
  version/timestamp suffix, the version comes from `pyvenv.cfg`. Clicking it opens the
  admin dialog's new **Environment** tab: the facts (folder, interpreter, the exact
  activate / `uv pip --python` / `uv run --python` commands, Nu's uv, each copyable), then
  Packages / Environment variables (unchanged editors and settings keys) / What Nu Ran.
- [x] **Echo the real command**: every uv command goes through `Uv`, which records it in
  the GUI-free `mu/command_log.py` (argv, cwd, start, exit code, output tail; also logged
  at INFO); "What Nu Ran" renders it (`uv …` as typed, uv's full path in the tooltip and
  the log file), and the package dialog prints `$ uv pip install …` before the output.
  (No separate "new env" button yet: that's multi-env, below.)
- [x] PEP 723: Run uses `uv run --python <env python> --script <file>` when the file has a
  `# /// script` block (`mu/script_metadata.py`, PEP regex + tokenize so a block in a
  string doesn't count); the command is the Run pane's first line and a `Hint:` line goes
  above uv errors it can explain. NB: uv builds the script's env from the env's *base*
  Python, so packages added to the learner env aren't visible to a PEP 723 script
  (standard `uv run` semantics), and there's no `>>>` afterwards (`--script` can't take
  `-i`). Plain files run exactly as before. **Not yet** for the debugger and Pygame Zero's
  Play (they'd need `uv run … python -m pgzero` / the debug runner via `--with-requirements`).
- [x] **Advanced multi-env create/switch, hidden by default** (4b part 2): a collapsed
  "Advanced: more environments" section at the bottom of the Environment tab lists the
  environments (name, Python, In use / From the next start), with **Use this one** and
  **New environment…**. Registry (GUI-free, `mu/virtual_environment.py`): the default env
  (its folder remembered as venv.json `default_dirpath`) + the named ones found by scanning
  `DATA_DIR/envs/` (so one made there by hand with `uv venv` shows up); names are plain
  folder names (letters/digits/`-`/`_`, ≤ 40, no Windows device names), unique ignoring
  case. `create_environment` uses the default's own path (`create()`: bundled/system
  Python, `--seed`, offline pip wheel, the baseline wheelhouse incl. plugins'
  `learner-env`, the kernel) on a worker thread, showing `$ uv venv …` then each step;
  a failure removes the half-made folder. `switch_environment` runs the start-up checks
  (`ensure`) on the target and sets venv.json `dirpath`: it takes effect at the next start
  (status-bar message after OK), where `ensure_and_create` finds the env healthy and
  repairs nothing (tested). A named env Nu rebuilds (upgrade / failed check) keeps its
  folder; a bundled Python a named env uses isn't removed. Verified in the real app under
  Xvfb: create, use, restart, add a package, switch back, the package isn't there.
  - [ ] **Not done:** deleting an environment (by hand for now: switch away, restart,
    delete the folder; documented). `mu_version`/`baseline_packages` in venv.json are still
    global, not per environment: a named env made by an older Nu isn't rebuilt on upgrade
    until it's the one in use when the version changes.

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
  Follow-ups: verify on Windows + Linux installers; check the archive survives Apple
  notarization once signing lands. (Old extracted builds under `DATA_DIR/python/` are now
  removed at startup once the environment no longer uses them:
  `VirtualEnvironment.remove_old_bundled_pythons`.)
- [x] Build a wheelhouse — `python -m mu.wheels --package` builds `mu/wheels/<version>.zip`
  (pgzero/pygame/ipykernel + deps), bundled via `sources`; the first-run baseline install
  is offline (one `uv pip install --no-index --no-deps` of the zip's wheels since #39; it
  was one pip run per wheel, see `install_from_zipped_wheels`). Bumped the stale
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

Status: 5a, 5b, 5c, 5d and 5e done (API 0.5): learners add, update and remove plugins
from the Plugins tab, into a plugin environment of their own (`docs/plugins.md` →
"Adding a plugin").

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
  → All three fixed in 5c part 1 (plugin API 0.2): plugins register image folders,
  modes declare `uses_user_environment` / `ensure_workspace_assets`, and plugins list
  learner-env packages as a `learner-env` extra.

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
- NOTE: errors in a plugin's **threads** went to `threading.excepthook` (stderr only, no
  log entry, no dialog). → Fixed in 5e: `app.thread_excepthook` (chained) routes them
  through `PluginErrorHandler`, marshalled to the GUI thread.
- NOTE (5d): in **installers** Nu runs from Briefcase's bundled env, which users
  can't install into, so entry-point discovery only saw bundled plugins there. → Fixed
  in 5d: a plugin env goes on `sys.path` before discovery.

**5c. Convert the specialized modes to bundled plugins (proof of the API):** ✅ DONE
- [x] Scaffold a `plugins/` **uv workspace** (`[tool.uv.workspace]`): each bundled plugin is
  `plugins/<name>/` with its own `pyproject.toml` + `mu.plugins` entry point — independently
  buildable/publishable, sharing the repo lockfile. (`plugins/example` is a member but not a
  dependency.) `nu-editor` depends on each bundled plugin by name, resolved from the
  workspace by `[tool.uv.sources]`; Briefcase installs it from a wheel built from the
  checkout (`build/plugin-wheels`, found with `--find-links`; listing it in `requires` as a
  local path, the first approach, broke every installer build until 2026-11); pip installs from a checkout pass the path. Publishing order:
  bundled plugins to PyPI **before** the `nu-editor` release that needs them
  (`docs/packaging.md`).
- [x] Move the specialized modes out of the core set into bundled plugins loaded through the same
  entry-point path (shipped + enabled by default) — they become the reference plugins. Keep
  **Python 3 + Debugger** in core.
  - [x] **Pygame Zero** → `plugins/pygamezero` (`nu-pygamezero`, `nu_pygamezero`, entry point
    `pygamezero`, mode key unchanged). Built only on `mu.plugin`; to make that possible,
    plugin API **0.2** adds plugin images (`Host.register_images` / `ModePlugin.images`;
    a name clash with a core or other plugin image raises, so the plugin is skipped),
    `Mode.uses_user_environment` + `Mode.ensure_workspace_assets` (replacing the hardcoded
    mode names in `dialogs.py`/`logic.py`), the `learner-env` extra (replacing
    `wheels.mode_packages`' pgzero entry) and `Host.save_current` / `run_program` /
    `stop_program` / `update_action` / `python_apis`.
  - [x] **CircuitPython** → `plugins/circuitpython` (`nu-circuitpython`, `nu_circuitpython`,
    entry point `circuitpython`, mode key unchanged). Built only on `mu.plugin`; plugin API
    **0.3** adds what a `MicroPythonMode` plugin needs: `mu.plugin.Device` (what
    `compatible_board` returns), `Host.shared_apis()` (the autocomplete entries every Python
    has, for a board mode) and `Host.plotter_available` (Qt Charts present). The core's
    modes are now just **Python 3 + Debugger**; it no longer names or imports CircuitPython.
- [x] Relocate each plugin's API stubs (`modes/api/`), wheels, icons, and settings into its
  own package; keep the suite green (port mode tests → plugin tests).
  - [x] Pygame Zero: stubs → `nu_pygamezero/api/`, icons → `nu_pygamezero/images/`, demo
    assets → `nu_pygamezero/assets/`, wheels → its `learner-env` extra, tests →
    `plugins/pygamezero/tests/` (pytest `testpaths`/`pythonpath`, coverage includes
    `plugins/`; tests' shared fixtures moved to the root `conftest.py`). It had no settings
    of its own. Its strings stay in Nu's catalog (`make translate_*` extracts bundled
    plugins too).
  - [x] CircuitPython: stubs (`ADAFRUIT_APIS`) → `nu_circuitpython/api/`, icons →
    `nu_circuitpython/images/` (the Serial button's renamed `circuitpython-serial`, per the
    plugin-name prefix convention; `plotter` stays a core icon), tests + mount fixtures →
    `plugins/circuitpython/tests/` (now 100% coverage). Its runtime dependency
    `adafruit-board-toolkit` moved from the core's dependencies/Briefcase `requires` to the
    plugin's (`pyserial` stays in core: `MicroPythonMode` uses it). No `learner-env` extra:
    CircuitPython code runs on the board. It had no settings of its own.

**5d. Plugin dependencies via uv (ties into Phase 4):** ✅ DONE
- [x] A plugin declares its PyPI runtime deps; installing the plugin **uv-installs** the
  package + deps into a **dedicated plugin env**, and its `learner-env` extra into the
  learner env. Built as designed in 5e (`mu/plugin/plugin_env.py`, GUI-free):
  - **Plugin env** `DATA_DIR/plugin-env`, made on the first install with `uv venv
    --python <Nu's own interpreter>` (`sys.executable`; for an app launcher that isn't
    Python, the interpreter in `sys.base_prefix`, else its X.Y). `plugin-env.json` next
    to it records its Python X.Y and what the learner added (requirement as typed, or the
    wheel path).
  - `app.setup_modes` calls `plugin_env.add_to_sys_path()` **before** `load_plugins`:
    `site.addsitedir` (appends, so Nu's PyQt6 always wins). Its entry points are a new
    `PluginRecord.kind` **"added"** ("Added by you"), with the record's `distribution`;
    `BUNDLED_DISTRIBUTIONS` unchanged.
  - **Add a plugin…** (PEP 508 name only: no URL/path/option/marker reaches argv) →
    PyPI JSON fetched on a `QThread` (summary, author, homepage, latest version) + trust
    note + exact commands → `uv pip install --python <plugin env> --excludes
    <nu-provides.txt> <req>`. **Add from a file…** for a `.whl` (offline). All through
    `Uv` (What Nu Ran + log), streamed into `PackageDialog` (`setup_job`), effective at
    the next start. **Update** (`--upgrade`, name installs only) and **Remove** (`uv pip
    uninstall`) for "added" plugins only. Core-only `Host` methods; no API bump.
  - Open questions, decided by the maintainer's lead: **no second PyQt6** — every
    install passes `--excludes` listing every distribution Nu's process sees (outside the
    plugin env, plus `nu-editor`/`mu-editor`; needs uv ≥ 0.9.8, now the floor), then the
    plugin's own `Requires-Dist` on those is checked against Nu's versions (`packaging`,
    markers evaluated) and it's uninstalled with a plain reason if unsatisfied; **not a
    plugin** (no `mu.plugins` entry point) → uninstalled; **Nu moved to a new Python** →
    the env stays off `sys.path` (logged) and the tab offers **Reinstall my plugins**
    (fresh env + the recorded list; a vanished wheel is reported, not fatal);
    **uninstall leaves deps** — accepted for v1 (inert unless they declare
    `mu.plugins`), documented; **offline** = Add from a file; **same id installed +
    dropped in** — unchanged (installed wins).
  - Verified end to end (Xvfb, the real window): add the example plugin's wheel →
    restart → Example mode, "Added by you" → Remove → restart → gone; the plugin env
    never got PyQt6. Also by script: a plugin depending on PyQt6 + `nu-editor` (both
    excluded) with a `learner-env` extra (installed into the learner env), one needing
    `PyQt6>=99` and one without an entry point (both removed again), add by name from
    real PyPI, and Reinstall after a faked Python change.
- [x] Offline-first: bundled plugins' wheels ship in the installer wheelhouse (`mu/wheels`).
  Minimal version done in 5c part 1: `wheels.baseline_packages()` adds every installed
  plugin's `learner-env` requirements (read from metadata, so it works for switched-off
  plugins and in the bare build Python), and `build.yml` installs the bundled plugins
  (`--no-deps`) before `python -m mu.wheels --package`. 5d added installing a plugin's
  learner-env packages into the **existing** environment when the plugin is added. Still
  open: only the core's packages are verified by `ensure_key_modules`; drop-in plugins
  can't declare any; no vetted community wheels in the installers (offline = Add from a
  file).

**5e. Plugin management UX:**
- [x] A **"Plugins"** admin tab: every discovered plugin (bundled first, then installed
  packages, then the drop-in folder) with its name/description (plugin API **0.4** adds
  `Plugin.description`), where it comes from (`PluginRecord.kind`: bundled / package /
  folder; exact origin on hover), status (On / Off / Couldn't load / Switched off after
  errors) with a beginner-readable first line and the full reason + traceback (trimmed to
  the plugin's own frames, copyable) under the list, and the modes it adds. An On/Off
  checkbox per plugin (bundled ones too) persisted via `Host.set_plugin_enabled` when the
  dialog is accepted (`disabled_plugins` unchanged); takes effect at the next start
  (said in the tab, live per row, and in the status bar after OK). Buttons: **Open
  plugins folder** (made if missing), **How to write a plugin** (docs). Plain trust note.
  Checkbox styling added to all three themes (`QTreeView::indicator`).
- [x] The error handler's switch-off and the tab agree: it marks the plugin in
  `plugins_switched_off_after_errors`, the tab shows "Switched off after errors; see the
  log", and switching from the tab clears the mark (re-enabling a loaded plugin also
  resets its error count this session).
- [x] Plugin thread errors reach Nu's log and the learner (see the 5b note).
- [x] Found while building it: user settings were **never saved** (`UserSettings.autosave`
  was off and nothing called `save()`), so `disabled_plugins` and `PluginSettings` didn't
  persist. Now autosaved on exit, and `set_plugin_enabled` saves at once.
- [x] Install / update / remove from the tab — surfacing the real uv command
  (transparency, as in 4b), before running it and in What Nu Ran. Built in 5d.
- NOTE (future): no **live** unload/load. `Host.unload_plugin` exists, but the mode picker,
  the session's current mode, and running panes/REPLs/timers a plugin owns make live
  removal risky; changes apply at the next start.
- NOTE on **trust**: plugins are arbitrary in-process Python; the trust model is "you chose
  to install it" (same as pip) — document this plainly. A curated/signed plugin index is a
  possible *future*, not a v1 gate. In-process plugins can't be meaningfully sandboxed
  without a far larger redesign — explicitly out of scope.

NOTE: the versioned API is a real commitment — bump it deliberately and keep a small
compatibility-shim window. micro:bit (Phase 6) is the deliberate **first external-shaped
plugin**: if it can be a clean plugin, the API is good.

---

## Phase 6 — micro:bit, reintroduced as a modern plugin

Status: 6a and 6b built and tested against fakes, opt-in (`uv sync --extra microbit`) until
the maintainer's hardware pass; the Files pane is designed, not built; 6c (default-on,
installers, PyPI) and 6d open.

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

As built (2026-11): **mpremote** + **DAPLink drag-and-drop**, per-version hex; board detection
by VID:PID from Qt's port info (the device selector) and pyserial (the flash worker's thread),
not `adafruit-board-toolkit`. pyOCD and Universal Hex are deferred (below).

**6a. Connectivity + flashing foundation:** ✅ built, **needs hardware validation**
(everything below is tested against fakes only; there was no micro:bit when it was built —
the maintainer's checklist is in `plugins/microbit/README.md`)
- [x] Flash via **DAPLink mass-storage drag-and-drop**: `nu_microbit.flash.copy_hex` writes the
  firmware `.hex` onto the `MICROBIT` drive (found via `mount` output, `/media/*`,
  `/run/media/*`, `/Volumes`, ChromeOS's `/mnt/chromeos/removable`, Windows volume labels),
  then waits for DAPLink's remount (≤30 s gone, ≤60 s back) and checks `FAIL.TXT`.
  `DETAILS.TXT` gives the board ID (9900/9901 → V1, 9903–9906 → V2; anything else is
  refused politely) and the DAPLink version; a `MAINTENANCE` drive gets its own message.
- [x] Copy the learner's code as `main.py` + reset via **`mpremote`** (`>=1.29`), in-process:
  `SerialTransport.enter_raw_repl(soft_reset=True)` → `fs_writefile` → mpremote's own `reset`
  code (`machine.reset()`), in a worker `QThread` — no `sys.executable -m mpremote` problem
  in the packaged app. Echoed as `mpremote connect <port> fs cp <file> :main.py + reset`.
  MicroPython present? → REPL probe (Ctrl-C, Ctrl-B, banner `MicroPython … micro:bit vX`,
  3 s); absent (or **Shift+Flash**, confirmed) → firmware first, then a ≤20 s wait for the
  REPL. `time`, `time.sleep_ms` and `machine.reset` were checked in the V1 1.1.1 and V2 2.1.2
  firmware sources.
- [x] Firmware **pinned + fetched**, never vendored (`nu_microbit/firmware.py`): V2 **2.1.2**
  (`microbit-foundation/micropython-microbit-v2`; newest release, though GitHub's "latest"
  badge is still on 2.1.1) and V1 **1.1.1** (`bbcmicrobit/micropython`), by URL + SHA-256
  (verified by downloading both, 2026-11). Downloaded on first use to
  `DATA_DIR/microbit/firmware/` with progress, checked, kept; a bad cached copy is deleted;
  offline → a message naming the file, its URL and the folder. Also looked for in
  `nu_microbit/firmware/` (the installer-bundling hook for 6c). To update a pin: change the
  URL, version, size and SHA-256 together and re-run the tests.
- [ ] REPL file ops (`ls`/`cp`/`rm`) via mpremote — with the Files pane (6b).
- [ ] **Universal Hex** (one image for V1+V2): deferred. Per-version hex picked from
  `DETAILS.TXT` is simpler and robust; revisit if we ever ship the firmware in installers
  and want one file.
- [ ] **pyOCD** as the richer flasher: deferred (heavy deps, untestable without hardware).
  Hook: `BoardIO.copy_hex` is the one firmware-writing step; a pyOCD flasher would replace
  it (and could work when the drive doesn't mount).

**6b. The plugin (on the Phase 5 API):**
- [x] A `nu-microbit` plugin (`plugins/microbit`, import `nu_microbit`, entry point
  `microbit`, mode key `microbit` as in Mu) providing the micro:bit **mode**: **Flash**
  (F3; Shift+Flash re-flashes MicroPython), **REPL** and **Plotter** (MicroPythonMode's,
  unchanged — the micro:bit REPL is a plain MicroPython REPL), board detection by DAPLink
  VID:PID 0D28:0204 with V1/V2 named from the serial number, workspace
  `<workspace>/microbit`. Flash closes an open REPL/plotter first (they hold the port),
  greys the buttons while it runs and reopens them after. Needed plugin API **0.5**
  (`Host.log_command`, `Host.current_device`, `Host.data_dir`); boards' modes now show
  **What Nu Ran** as a tab of its own in the admin dialog. Opt-in (root `microbit` extra)
  until validated — see 6c.
- [ ] Reintroduce the **file-transfer pane** (the old `FileSystemPane`, removed in Phase 1d)
  as plugin-owned UI driven by `mpremote`. **Designed, not built**: `docs/plugins.md` →
  "Roadmap: the micro:bit Files pane" (API 0.6 `Host.add_pane`/`remove_pane`; mpremote
  `fs_listdir`/`fs_readfile`/`fs_writefile`/`fs_rmfile` on the same worker pattern, logged;
  exclusive with the REPL).
- [x] **Modern `microbit` V2 API stubs** for autocomplete/calltips
  (`nu_microbit/api/microbit.py`, 349 entries): upstream's, corrected and brought up to
  MicroPython 2.x (microphone, speaker, `Sound`, `audio.SoundEffect`, `log`, `power`,
  `pin_logo`, `run_every`, radio, music, neopixel, speech…), checked against the v2-docs and
  `micropython-microbit-stubs`; V2-only entries say "(micro:bit V2)".

**6c. Packaging + distribution:**
- [ ] **After the maintainer's hardware pass**: promote to a default-enabled bundled plugin —
  move `nu-microbit>=0.1` from the `microbit` extra to `nu-editor`'s dependencies, add
  `plugins/microbit` to `BUNDLED_PLUGINS` (`make.py`, `Makefile`), `loader.BUNDLED_DISTRIBUTIONS`
  and `build.yml`'s plugin installs and wheels (see `docs/packaging.md` → "Opt-in workspace plugins").
  Include `mpremote` (+ pyOCD if adopted) wheels for offline installers; optionally fetch the
  two pinned `.hex` files (SHA-256 checked) into `nu_microbit/firmware/` at build time so a
  fresh install can flash offline.
- [ ] Also publish to PyPI so it doubles as the **worked example** for community authors.

**6d. Stretch / future:**
- [ ] WebUSB-style direct flashing (pyOCD already gives programmatic flashing; full WebUSB
  parity is a browser concept — lower priority on the desktop/Qt stack).
- [ ] V2 extras: filesystem browser, radio tooling, on-device `log` integration in the pane.

---

## Hardening after Phases 5–6 ✅ (2026-11, `polish/post-phase-5-6-hardening`)

A regression sweep of the whole app under Xvfb (first run → saved session → German →
English; every mode, toolbar button, pane and admin tab), then the deferred fixes.
- [x] Fixed from the sweep: quitting after any debug session aborted Nu (the debugger's
  listener `QThread` was left running; upstream bug); opening a folder (Pygame Zero's
  asset buttons, **Open plugins folder**) could freeze Nu (`os.system("xdg-open …")` →
  `QDesktopServices.openUrl`); a board mode's admin dialog ran `uv pip list` for nothing.
- [x] Test isolation: `MU_DATA_DIR`/`MU_HOME_DIR` (+ `IPYTHONDIR`, the single-instance lock
  name) set by the root `conftest.py` before `mu` is imported; tests can't quit the
  `QApplication` or leave exception hooks patched; `mu.interface` installs `_` itself.
- [x] LF line endings everywhere (`.gitattributes`).
- [x] Window position honoured on any connected screen (`QGuiApplication.screenAt`).
- [x] REPL kernel connection encrypted (CurveZMQ via jupyter_client's
  `transport_encryption = "auto"`), which also silences ipykernel 7.4's warning.
- [x] Old bundled CPython builds removed (4c follow-up).
- [x] Toolbar shows icons only when its labels don't fit (long translations).
- [x] Admin tab titles consistent; What Nu Ran's text covers plugins' commands.
- Judgment calls left as they are (see the PR): a switched-off plugin shows its id
  (`pygamezero`), not its name, since it isn't imported; the Packages and Environment
  Variables texts still say "Python 3 mode" (translated upstream strings) though Pygame
  Zero uses the environment too; the overflow button stays a thin strip.

## Windows review ✅ (2026-11, #37, #39, #40)

A hands-on pass over a fresh install on Windows 11 (first run, every Python 3 toolbar
button, the debugger, the admin dialog's tabs, Pygame Zero Play, a second launch), plus
an audit for what Mu left behind.
- [x] #37: the first start crashed after #34 removed the Web mode's templates that
  `Editor.setup` still copied into the workspace.
- [x] #39 (learner-facing): Nu's own splash, window icon and Mode button
  (`utils/make_artwork.py` draws them from `icon.png`); a second launch hands over to
  the running Nu (`QLocalServer`: front, open its files) instead of exiting silently;
  baseline wheels in one `uv` call (about 9 s, was minutes); the 8.3 short-path
  workaround and `pywin32` gone; debugger exit codes; "program finished" note above
  `>>>`; Quit asks while a program runs; mode picker (Python 3 first, status-bar click);
  friendlier REPL banner, pane titles, debug inspector (no `__dunder__`s), pane height;
  Plugins-tab focus frame; log opens at the end and follows `MU_DATA_DIR`;
  `ensure_workspace_assets` on a mode's first use.
- [x] #40 (cleanup): Check's micro:bit special case → the `star_imports` mode attribute;
  dead REPL/file-system hooks, `device_list`, `_del_`, `find_next_match`; `nudatus`,
  `semver`, `mu/contrib`; 36 unused images; the Web API generator, `make video`, the
  CodeQL config; about 1,600 obsolete translations (`translate_begin` now passes
  `--ignore-obsolete`).
- Kept on purpose: the `mu_code` / `mu_venv` / data-folder names and the Briefcase app id
  (renaming needs a migration); the `venv_path` session key (documented); the docs'
  Mu design archive (`docs/swag`, `docs/logo_design`, `docs/icon_brief`).
- [x] #39's changes checked on **macOS** (Apple Silicon, 2026-11-13; from source and in a
  locally built `.app`): the new artwork, the one-call wheel install (under a second), and
  the second-launch hand-over (front + opens the file). Found and fixed on the way:
  - **The installers hadn't built since Phase 5c** (CI's last `build.yml` run, 2026-11-08,
    failed on all three OSes): Briefcase adds `[project.dependencies]` to `requires`, and
    pip can't match `nu-circuitpython>=0.1` with the `./plugins/circuitpython` path listed
    after it. The plugins now reach Briefcase as wheels built from the checkout
    (`build/plugin-wheels`, `requirement_installer_args`); see `docs/packaging.md`.
  - **The packaged app crashed at start**: `mu/plugin/loader.py` read
    `importlib.util.__file__`, which a frozen importlib (Briefcase's Python) doesn't have.
  - A second launch **while Nu was still starting** (splash, first-run mode picker) got
    "Nu is already running, but isn't responding": Nu now listens from the start and acts
    on it once the window is up (`app.OtherInstances`).
  - With both fixes the `.app` (`make macos`) does a first start with the network blocked
    and empty uv caches in about 3 s, loads both plugins, and runs a program importing
    pygame. Not exercised there: the REPL, the debugger, Pygame Zero's Play.
- [ ] Check #39's changes on **Linux**, and in the installers from a `build.yml` run (none
  has been built by CI since the fix above: run it by hand before tagging).
- [ ] **pygame has no wheels for Python 3.14**: a source/`pip` install of Nu on 3.14 makes a
  3.14 learner environment, where the baseline install can't get pygame (it tries to
  compile it; a warning in the log, and Pygame Zero's Play then fails). The installers
  (Python 3.12) are fine. Decide: cap the learner environment's Python, or `pygame-ce`.
- [x] `MU_DATA_DIR` didn't cover the Jupyter kernelspec (`ipykernel install --user` wrote
  to the real `~/Library/Jupyter/kernels` etc.), so a throwaway profile left one behind.
  Now `ipykernel install --prefix <env>` puts it in the environment
  (`<env>/share/jupyter/kernels`, `VirtualEnvironment.kernels_dir`), which `MuKernelManager`
  searches first: it goes with the environment, each named environment has its own. An
  environment made by an older Nu keeps using its `--user` spec until it's re-created;
  those old specs are left in the learner's Jupyter folder (not deleted by Nu).
- [ ] **Release 2.0.0**: `v2.0.0` was never tagged (the latest tag is `v2.0.0b3`); follow
  `docs/release.md`. The releases page still lists Mu's `v1.0.0-beta0.1`, and the
  `v1.0.0-beta0.1` / `v1.2.2.alpha.1` tags are Mu's too: consider removing them.

## Notes / deferred

- `virtual_environment.py` (~1.5k lines) powers "install packages from the UI" — reshaped
  around uv in Phase 4 (venv creation, `uv pip`, `uv run`); since #39 the baseline install
  at first run is uv too (only `pip --version` and listing the baseline packages still
  use the venv's pip).
- ~~Orphaned resource icons / locale strings for removed modes~~ — swept in #40.
- 100%-coverage mandate is great for the Qt6 port; can relax to "don't regress" afterward
  if it slows iteration.
- ~~**Translations re-extraction after the in-app "Mu" → "Nu" rename**~~ — done
  (branch `i18n/re-extract-after-rename`). All 14 catalogues were re-extracted from
  `mu/` + the bundled plugins and merged (`make translate_begin`); 213 entries whose
  only change was the app name had their translation carried across mechanically by
  `utils/recover_renamed_translations.py` (only where the translation writes the name
  literally as "Mu"); every `.mo` was recompiled (the fr and ru_RU binaries had drifted
  from their `.po` for years); Ukrainian was added to the language picker; and
  `tests/test_i18n.py` now guards `.po`/`.mo` sync, `{}` placeholders and
  picker ↔ `mu/locale` parity. Nothing was machine-translated. **Remaining, for
  translators** (see `docs/translations.md`, `make translate_status`): ~85–105
  untranslated messages per language (mostly the Environment/Plugins tabs, command log
  and PEP 723 hints) and ~16–36 "needs review" (fuzzy) ones, notably all of uk_UA's
  renamed strings (its translation writes "М'ю"), sv's genitive "Mus", and the nl
  `"{} REPL"` entry, which was mistranslated and is now flagged fuzzy.
- ~~**App-ID realignment**~~ — done in 4e: `setDesktopFileName("org.kovir.mu")` matches
  Briefcase's generated `.desktop`; `conf/` removed.
- ~~**Stale `conf/mu.appdata.xml` description**~~ — moot: `conf/` removed in 4e (it
  wasn't shipped by the Briefcase AppImage anyway).
