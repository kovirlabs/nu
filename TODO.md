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
Current baseline (Python 3.11–3.14 + PyQt6): **889 passed, 20 skipped**.
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

- [x] **micro:bit mode — DROPPED.** Its tooling (`uflash` 2.0.0, `microfs` 1.4.5)
  is frozen since 2021 / unmaintained, with no actively-maintained desktop-Python
  alternative. See 1e below.

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
- [ ] Rewrite `mu/virtual_environment.py` internals as thin `QProcess` wrappers around
  `uv` (`uv venv`, `uv pip`/`uv add`, `uv run`). Resolve a pinned `uv` binary at runtime.
- [ ] Startup: ensure/create the default env via uv (replaces `venv.ensure_and_create`,
  same splash/worker flow); "activate" by setting `VIRTUAL_ENV` + `PATH` in the spawned
  process env; render the UI scoped to that env. (uv also auto-discovers `.venv` in the
  working dir.)
- [ ] Keep the suite green; add tests for the uv wrapper.

**4b. Env UX (progressive disclosure):**
- [ ] "Environment: <name>" indicator + package list scoped to the active env.
- [ ] `uv` buttons (new env / add package / show packages) that **echo the real command**
  into a log/console pane — the transparency is the lesson.
- [ ] PEP 723: "Run" uses `uv run` so inline `# /// script` dependencies auto-resolve.
- [ ] Advanced multi-env create/switch, hidden by default.

**4c. Bundle assets for offline:**
- [ ] Vendor a pinned `uv` binary per platform.
- [ ] Vendor a python-build-standalone **CPython 3.14** per platform; make it the *primary*
  source (NOT network-conditional): `uv venv --python <bundled>` or pre-seed
  `UV_PYTHON_INSTALL_DIR` + `UV_PYTHON_DOWNLOADS=never`.
- [ ] Build a wheelhouse (extend `mu/wheels/`) and wire `UV_FIND_LINKS` for offline `pip`.

**4d. Briefcase packaging:**
- [ ] Add `[tool.briefcase]` to `pyproject.toml`; declare PyQt6 + Qt plugins/data; include
  uv + PBS 3.14 + wheelhouse as app resources.
- [ ] **Build all three in CI** (`build.yml`): ubuntu → AppImage, windows → MSI,
  macOS → `.dmg` — so cutting a release is push-button. Local builds stay available for dev
  (Linux here; the maintainer's Windows box for spot-checking the GUI), but are no longer
  the release path.
- [ ] Repoint `make.py`/`Makefile` installer targets at Briefcase (dev/local convenience).
- NOTE: CI *builds* are credential-free, but **signing isn't** — macOS notarization (Apple
  Developer cert) and Windows Authenticode need secrets wired into `build.yml`, else users
  hit Gatekeeper / SmartScreen warnings. Land unsigned-but-building first, add signing after.

**4e. Retire pup:**
- [ ] Remove pup-based targets, the `_PUP_PBS_URLs` table refs, `linux-docker`, and the
  `carlosperate/pup` fork usage once Briefcase builds are confirmed on all three OSes.

## Notes / deferred

- `virtual_environment.py` (~1k lines) powers "install packages from the UI" — being
  **replaced by the uv-driven model in Phase 4** (not dropped; reshaped).
- Orphaned resource icons / locale strings for removed modes are harmless; sweep later.
- 100%-coverage mandate is great for the Qt6 port; can relax to "don't regress" afterward
  if it slows iteration.
