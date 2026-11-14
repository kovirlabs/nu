# Packaging Nu

Our target users (beginner programmers and those who support them) may not be
confident with installing software, so obtaining and setting up Nu needs to be
as simple as possible — and producing the installers needs to be automatic, so
cutting a release doesn't depend on one volunteer's time.

The native installers are built with
**[Briefcase](https://briefcase.readthedocs.io/)** (part of the BeeWare suite),
which replaced upstream Mu's `pup` pipeline in Phase 4 (see `TODO.md`). A
single definition in
`pyproject.toml`'s `[tool.briefcase]` drives all three platforms:

| OS | Format | CI runner |
|---|---|---|
| Windows | `.msi` | `windows-latest` |
| macOS | zipped `.app` (ad-hoc signed) | `macos-latest` (Apple Silicon) |
| Linux | `.AppImage` | `ubuntu-latest` |

## Bundled plugins: the uv workspace

The repo is a **uv workspace** (`[tool.uv.workspace] members = ["plugins/*"]`
in `pyproject.toml`). Each bundled plugin is its own package under
`plugins/<name>/`, with its own `pyproject.toml`, version and `mu.plugins`
entry point, sharing the repo's `uv.lock`. Today that's **`nu-circuitpython`**
(`plugins/circuitpython`) and **`nu-pygamezero`** (`plugins/pygamezero`);
`plugins/example` is a member too, so it's locked and buildable, but it's a
template and nothing depends on it.

`nu-editor` depends on each bundled plugin by name (`nu-circuitpython>=0.1`,
`nu-pygamezero>=0.1`), and
`[tool.uv.sources]` resolves that name from the workspace, so:

- **Development:** `uv sync` installs the bundled plugins editable into `.venv`,
  and Nu finds them through their entry points, the same way it finds a
  community plugin. The tests for each live in `plugins/<name>/tests` and run
  with Nu's.
- **pip from a checkout** (as CI's test job does): pip doesn't read
  `[tool.uv.sources]`, so give it the paths too:
  `pip install ./plugins/circuitpython ./plugins/pygamezero ".[dev]"`.
- **Installers:** Briefcase adds `[project.dependencies]` to its own
  `requires`, so it already asks pip for `nu-circuitpython` and
  `nu-pygamezero` by name. pip finds them as wheels built from the checkout
  into `build/plugin-wheels/`, which `requirement_installer_args`
  (`--find-links`) in `[tool.briefcase.app.mu]` points at; `make.py`
  (`_build_plugin_wheels`) and `build.yml` build them before
  `briefcase create`. The app gets the plugins' entry points, package data
  (icons, demo assets) and own dependencies (CircuitPython's
  `adafruit-board-toolkit`). Don't also list a plugin in `requires` as a
  local path (`"./plugins/<name>"`): pip then fails with "No matching
  distribution found for nu-<name>", because it meets the name before the
  path. That broke every installer build from Phase 5c until it was caught by
  building the macOS app locally (2026-11).
- **Publishing to PyPI:** `[tool.uv.sources]` is uv-only; the built `nu-editor`
  sdist/wheel just says `Requires-Dist: nu-circuitpython>=0.1` and
  `Requires-Dist: nu-pygamezero>=0.1`. So **each bundled plugin must be
  published to PyPI before the `nu-editor` release that needs it** (or
  `pip install nu-editor` can't resolve). The order is: `nu-circuitpython` and
  `nu-pygamezero` (in either order: neither depends on the other or on
  `nu-editor`), then `nu-editor`. `publish.yml` builds all three and
  uploads them in that order on a release tag, skipping a plugin version PyPI
  already has (see [Publishing to PyPI](pypi.md)); `make dist` and
  `make publish-live` (or `make publish-test` for test PyPI) do the same by
  hand. Bump a plugin's
  own version when it changes, independently of Nu's.

### Opt-in workspace plugins: micro:bit

**`nu-microbit`** (`plugins/microbit`, Phase 6) is a workspace member too, but
**not** a dependency of `nu-editor` yet: it hasn't been validated on real
micro:bits. Instead:

- `nu-editor` has an optional extra, `microbit = ["nu-microbit>=0.1"]`, and
  `[tool.uv.sources]` resolves `nu-microbit` from the workspace, so
  `uv sync --all-extras` (or `--extra microbit`) installs it editable in a
  checkout. A plain `uv sync` doesn't, and its tests that need the installed
  entry point skip.
- CI installs it anyway (`./plugins/microbit` in `test.yml`'s and `docs.yml`'s
  pip lines), so its tests and API docs run on every push.
- It is **not** one of `nu-editor`'s dependencies or in `build.yml`'s installs
  and plugin wheels, so the installers don't ship it, and the built `nu-editor` wheel lists it only as
  `Requires-Dist: nu-microbit>=0.1; extra == "microbit"`.
- Its own dependency is `mpremote`. The MicroPython firmware is **not** in the
  package: it's pinned (URL + SHA-256) and downloaded on first use into
  `DATA_DIR/microbit/firmware/`.

**Promotion (Phase 6c), after the maintainer's hardware pass** (the checklist
in `plugins/microbit/README.md`): move `nu-microbit>=0.1` from the extra to the
dependencies, add it to `BUNDLED_PLUGINS` in `make.py` and the `Makefile`
(so its wheel is built for Briefcase and published), to
`loader.BUNDLED_DISTRIBUTIONS` and to `build.yml`'s plugin installs and plugin
wheels, and
publish it to PyPI before that Nu release. To make Flash work offline from a
fresh install, the installer build can also put the two pinned `.hex` files in
`nu_microbit/firmware/` (the plugin checks there, after the data folder, and
verifies them like a download); fetch them in `build.yml` with their SHA-256s
from `nu_microbit/firmware.py`, never commit them.

### What the learner's environment gets from plugins

A plugin lists the packages its modes need *in the learner's environment*
(where their programs run, not where Nu runs) as an extra called
`learner-env`, e.g. Pygame Zero's `learner-env = ["pgzero>=1.2.1",
"pygame>=2.6"]`. `mu.wheels.baseline_packages()` is the core's own list
(`ipykernel`) plus the `learner-env` requirements of every installed
distribution with a `mu.plugins` entry point, read from package metadata
without importing the plugin. That's what goes into the offline wheelhouse and
what a new learner environment is built with.

## Building installers (Briefcase)

CI is the release path: `.github/workflows/build.yml` builds one OS per job and
uploads the installer as a downloadable artifact. **Trigger it from the GitHub
Actions tab** ("Build installers" → *Run workflow*) and download the artifact
for your OS from the run. Pushing a `v*` tag also builds all three and
publishes a GitHub Release with the installers attached. Release tags are
plain numeric `vX.Y.Z` (Windows MSI versions can't carry a pre-release
segment). See [Release process](release.md).

Briefcase is pinned per platform in `build.yml`: Windows uses 0.4.5, whose MSI
template replaces an installed older (or same-version) Nu instead of
installing alongside it; macOS and Linux stay on 0.4.2 because 0.4.5 breaks
the AppImage. The MSI's UpgradeCode is pinned as `guid` in `pyproject.toml`
— never change it, or Windows will stop treating new installers as upgrades.

Locally (inside a virtual environment that has pip, with the `package` extra:
`uv sync --extra package`, or with pip `pip install -e ./plugins/circuitpython -e ./plugins/pygamezero -e ".[package]"`):

```
$ make win64     # 64-bit Windows MSI
$ make macos     # macOS .app/.dmg (ad-hoc signed)
$ make linux     # Linux AppImage
```

Each target fetches the offline baseline wheels, builds the bundled plugins'
wheels and runs the Briefcase
create → build → package cycle (see `make.py`). The build is mostly self-driving
once the build tools are present (Briefcase fetches WiX for the Windows MSI on
demand).

### What ships inside the app

- The editor (`mu`) plus its third-party dependencies (PyQt6, etc.), installed
  into the bundle by Briefcase from `[tool.briefcase.app.mu].requires`.
- A pinned **`uv`** binary — it rides in via the PyPI `uv` wheel, and
  `find_uv()` locates it at runtime through `uv.find_uv_bin()` (no `PATH` or
  `MU_UV` needed in the packaged app).
- The bundled plugins (`plugins/pygamezero`, `plugins/circuitpython`),
  installed by Briefcase from wheels built from the checkout
  (`build/plugin-wheels/`, see [above](#bundled-plugins-the-uv-workspace)).
- The **baseline wheels zip** (`mu/wheels/<version>.zip`), so the learner's
  baseline packages install without the network: the core's (`ipykernel`)
  plus the bundled plugins' `learner-env` packages (Pygame Zero's `pgzero`
  and `pygame`; CircuitPython declares none, as its code runs on the board).
- A relocatable **CPython** (the python-build-standalone build uv itself would
  install, matching the app's Python X.Y and the runner's platform) plus a
  **pip wheel**, in `mu/wheels/python/`.

`python -m mu.wheels --package` fetches all three before packaging (it needs
`uv` installed, to look up the CPython download, and the bundled plugins
installed, to read their `learner-env` needs; CI's build job installs them
with `pip install --no-deps ./plugins/circuitpython ./plugins/pygamezero`,
which needs no PyQt6).

At first launch Nu extracts the bundled CPython into its data directory (a
stable, writable path: the app bundle may be read-only, and an AppImage is
mounted somewhere new on every launch) and creates the learner's environment
with `uv venv --python <that interpreter> --seed --no-index --find-links
mu/wheels/python`. Nothing touches the network. The app's own interpreter
can't be the base: in a packaged app `sys.executable` is Briefcase's launcher
stub, which uv can't inspect. In a dev checkout without the bundled CPython,
Nu falls back to `uv venv --python <X.Y>`, letting uv find or download a
matching Python.

This adds about 25 MB to each installer.

### Signing

CI builds are **unsigned** (macOS uses an ad-hoc signature). Users will see a
SmartScreen (Windows) or Gatekeeper (macOS) warning until code-signing secrets
(Authenticode / Apple notarization) are wired into `build.yml` — tracked as a
follow-up in `TODO.md` (Phase 4d).

### Linux desktop integration

Briefcase generates the AppImage's Linux `.desktop` entry itself, from
`formal_name` and `description` in `pyproject.toml`, named after the app id:
`bundle` + app name, i.e. **`org.kovir.mu.desktop`**. (Briefcase's AppImage
template ships no AppStream metainfo; add one only if we target software
centres.) `mu/app.py` passes
the same id to `QApplication.setDesktopFileName()` so the running window
(the Wayland app id) matches the installed `.desktop` file, which keeps the
taskbar icon and window grouping working. If `bundle` or the app key ever
changes, update that call to match.

The pre-Briefcase hand-written metadata (`conf/`) and the upstream Debian
packaging (`debian/`) were removed along with the `pup` pipeline (Phase 4e).
