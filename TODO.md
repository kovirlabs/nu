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
Run headless with:
```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -p no:randomly -q
```

## Decisions locked in

| Question | Decision |
|---|---|
| License | **Stay GPLv3** → keep PyQt5/QScintilla; modernize *within* Qt |
| GUI framework | **Keep Qt** (kivy/tkinter rejected: would lose QScintilla + qtconsole REPL; full rewrite) |
| Qt/Python baseline | **Modernize**: PyQt5 → **PyQt6**, require **Python 3.11+**, drop stale pins |
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
- [ ] **Remove the now-orphaned serial file-transfer subsystem** (micro:bit was its last user;
  CircuitPython uses the CIRCUITPY drive, not this): `FileManager` (`modes/base.py`),
  `FileSystemPane` + the device/local file-list classes (`interface/panes.py`),
  `Window.add_filesystem` (`interface/main.py`), and the **vendored `microfs.py`** + tests.

**1c. Toolchain**:
- [ ] Adopt **ruff** for dev lint+format (replaces flake8 + pycodestyle + pyflakes + black
  *as dev tools*). NOTE: `pyflakes` + `pycodestyle` stay as **runtime** deps — `logic.py`
  uses them for the in-editor code checker.
- [ ] Point `make.py` / `Makefile` lint+tidy targets at ruff

**1d. Packaging consolidation** (do carefully — `make.py` installer scripts and the
Windows build parse `mu/__init__.py` + `setup.py`):
- [ ] Move metadata fully into `pyproject.toml` (hatchling backend), retire
  `setup.py` / `setup.cfg` duplication once installers are confirmed working

## Phase 2 — Modern Python + Qt6 (the one "medium" change)

- [ ] PyQt5 → **PyQt6** (`PyQt6-QScintilla` 2.14, `PyQt6-Charts`); bump
  `qtconsole`/`jupyter-client`/`ipykernel` to current; **delete the FIXME pins**
- [ ] Mechanical port: scoped enums (`Qt.AlignBottom` → `Qt.AlignmentFlag.AlignBottom`),
  `exec_()` → `exec()`, signal/slot signatures, `QAction` moves to `QtGui`, etc.
- [ ] `requires-python = ">=3.11"`; refresh `.venv` to a modern CPython
- [ ] Migrate `pkg_resources` → `importlib.resources`; drop the `setuptools` dep
- [ ] Suite green on the new stack

## Phase 3 — Verify packaging & CI

- [ ] Confirm AppImage / macOS `.app` / Windows installer build on the PyQt6 base
- [ ] Trim CI (`.github/workflows/`) to supported Python versions; speed it up

## Notes / deferred

- `virtual_environment.py` (~1k lines) powers "install packages from the UI" — a real
  feature; leave intact unless that feature is dropped.
- Orphaned resource icons / locale strings for removed modes are harmless; sweep later.
- 100%-coverage mandate is great for the Qt6 port; can relax to "don't regress" afterward
  if it slows iteration.
