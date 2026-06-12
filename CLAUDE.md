# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Nu — project intent

A continuation of the original Mu Editor for the Python programming language (reference: https://github.com/mu-editor/mu).

The original maintainers archived the upstream GitHub repo. This fork exists so the maintainer's child and the wider community can keep using it safely into the future, with modernization as needed.

**Goal: maintain and modernize.**

## What this is

This repo is **"nu"** (`github.com/kovirlabs/nu`), a fork of the **Mu editor** (`github.com/mu-editor/mu`, the `upstream` remote). Mu is a modal Python code editor for beginner programmers, built on PyQt5. Upstream was archived/marked unmaintained; this fork's stated goal is to keep it usable and modernize it as needed.

The actual editor lives in `mu/`. Package metadata still identifies as `mu-editor` v1.2.2 (`mu/__init__.py`, `setup.py`).

`main.py` at the repo root is a stray PyCharm sample — not part of the project; ignore it.

Two packaging configs coexist: `setup.py` / `setup.cfg` remain the canonical definition used by the `make` targets and platform installers, while `pyproject.toml` + `uv.lock` provide a **uv-based dev workflow** whose dependencies mirror `setup.py` (see below).

## Runtime constraints

As of **Phase 2** (see `TODO.md`) Mu runs on **PyQt6** and **Python 3.11+**. `setup.py` declares `python_requires=">=3.11"` and depends on `PyQt6>=6.6`, `PyQt6-QScintilla>=2.14`, `PyQt6-Charts>=6.6`, with a modern Jupyter stack (`qtconsole>=5.5`, `ipykernel>=6.29`, `jupyter-client>=8.0`). The old frozen Py3.5-era pins are gone. Two pins are intentionally still old: `black>=19.10b0,<22.1.0` + `click<=8.0.4` — the `<22.1.0` ceiling resolves to a build that runs on 3.11, and bumping black means reformatting the whole tree (deferred to the toolchain phase). `black` powers the in-editor "Tidy" button (a runtime dependency), so don't drop it.

`pyproject.toml` mirrors `setup.py` and pins `requires-python = ">=3.11"`; `uv sync` auto-downloads a managed CPython into `.venv`. The system `python3` here is 3.14; prefer working through the uv venv (or any 3.11+ virtualenv).

## Common commands

Dev setup with uv (preferred): `uv sync` installs the runtime dependencies into `.venv` using a managed CPython 3.11; add `--extra dev` (or `--all-extras`) for the tests/docs/packaging/i18n tooling. Run things with `uv run python run.py`, `uv run python -m mu`, or `uv run pytest`.

Dev setup the original way (inside a 3.8 virtualenv): `pip install -e ".[dev]"` installs runtime + tests + docs + packaging + i18n extras.

Most workflows go through the `Makefile` (which delegates to `make.py`):

- `make run` — run the local dev build (requires an active virtualenv; equivalent to `python run.py` or `python -m mu`).
- `make test` — full test suite (`pytest -v --random-order`). Sets `LANG=en_GB.utf8`; locale-sensitive tests need this.
- `make coverage` — tests with coverage report (`--cov=mu`). Upstream maintained 100% coverage.
- `make flake8` — lint.
- `make black` — check formatting; `make tidy` — apply Black formatting. Black wraps at **79** (`make.py` `BLACK_FLAGS`); flake8 allows up to **88** (`setup.cfg`).
- `make check` — runs `black` + `flake8` + `coverage`; this is the pre-commit gate.
- `make dist` — build sdist/wheel. `make win32`/`win64`/`macos`/`linux` build platform installers via `pup`.

**Run a single test** (the Makefile has no target for this): `pytest tests/test_logic.py::test_name`. Note that `addopts = --random-order` is set in `setup.cfg`, so test order is randomized by default — add `-p no:randomly` or `--random-order-seed=...` when you need a reproducible order while debugging.

**Running tests headlessly** (no display, e.g. via uv): the Qt tests need a platform plugin, so set `QT_QPA_PLATFORM=offscreen`. Full incantation used during development:
```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -p no:randomly -q
```
Current green baseline (Python 3.11 + PyQt6): **889 passed, 20 skipped**. (`~/.local/share/mu` must exist or you'll see a harmless at-exit settings-save traceback.) On a headless box without Mesa, Qt6's `offscreen` plugin still needs `libEGL.so.1` — put it on `LD_LIBRARY_PATH` (e.g. `apt-get download libegl1 libglvnd0 && dpkg -x` into a local dir). Lint the project's way with `PYFLAKES_BUILTINS=_ python -m flake8 mu/ tests/` — the `_` builtin is gettext; without that env var you get spurious `F821 undefined name '_'`.

Test layout mirrors the source tree: `tests/test_logic.py` tests `mu/logic.py`, `tests/modes/` tests `mu/modes/`, etc.

## Architecture

Mu is a **modal editor**: a fixed core of always-available features, plus a set of *modes* that retarget the editor at different platforms. This fork has trimmed the upstream set to six (see `TODO.md` for the rationale): **python, circuitpython, microbit, web, debugger, pygamezero** (upstream also shipped esp/pico/pyboard/lego/snek — removed). Understanding the three collaborators below explains most of the codebase.

- **`mu/app.py`** — entry point (`run()`). Builds the `QApplication`, splash screen, the `Window`, and the `Editor`, registers the list of mode classes, and wires logging. The set of available modes is the import list at the top of this file + `mu/modes/__init__.py`.

- **`mu/logic.py`** — the **`Editor`** controller (non-GUI). Holds `self.modes` (a `dict` of name → mode instance), the current mode, and all the application logic: open/save/run, mode switching (`select_mode` / `change_mode`), flake8/pycodestyle checking, device detection (`Device` / `DeviceList`). The `Editor` talks to the UI only through the `view` object passed in — keep GUI code out of here; that separation is what makes `logic.py` unit-testable.

- **`mu/interface/`** — the Qt view layer. `interface/main.py` defines the **`Window`** class (the `view` the `Editor` drives). `editor.py` is the Scintilla-based text widget, `panes.py` the REPL/file/plotter panes, `dialogs.py` dialogs, `themes.py` the day/night/contrast stylesheets, `workers.py` background threads.

- **`mu/modes/`** — every mode subclasses **`BaseMode`** in `modes/base.py` (MicroPython-family modes subclass `MicroPythonMode`, which adds REPL/serial plumbing). A mode declares `name`, `description`, `icon`, and implements `actions()` (toolbar buttons), `api()` (autocomplete/calltip data), `workspace_dir()`, etc. To add a mode: create the class, then register it in `app.py` and `modes/__init__.py`. `modes/api/` holds generated API stubs (excluded from flake8).

- **`mu/virtual_environment.py`** — Mu manages a **separate "user" virtualenv** (the `venv` singleton at module bottom) into which it installs third-party packages requested from the UI, isolated from Mu's own environment. `VirtualEnvironment` / `Pip` / `Process` wrap creation and `pip` operations via `QProcess`. Bundled wheels live in `mu/wheels/` (`python -m mu.wheels --package` fetches them for installers).

- **`mu/debugger/`** — the Python3 visual debugger, split into a `client` (in-process, talks to the UI) and a `runner` (the debugged program's subprocess). See `docs/debugger.rst`.

Supporting modules: `mu/settings.py` + `mu/config.py` (persisted settings and path constants), `mu/i18n.py` + `mu/locale/` (gettext translations; `make translate_*` workflows), `mu/resources/` (icons, fonts, CSS, web assets).

## Where to read more

`docs/` is Sphinx source (hosted at mu.readthedocs.io). Most useful for orientation: `docs/architecture.rst`, `docs/modes.rst` (writing a mode), `docs/debugger.rst`, `docs/setup.rst`, `docs/tests.rst`, `docs/translations.rst`, `docs/packaging.rst`. Every class/method carries a human-written docstring; these are extracted into `docs/api.rst`.
