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

Locally (inside a pip-enabled virtualenv with the `package` extra,
`pip install -e ".[package]"`):

```
$ make win64     # 64-bit Windows MSI
$ make macos     # macOS .app/.dmg (ad-hoc signed)
$ make linux     # Linux AppImage
```

Each target fetches the offline baseline wheels and runs the Briefcase
create → build → package cycle (see `make.py`). The build is mostly self-driving
once the build tools are present (Briefcase fetches WiX for the Windows MSI on
demand).

### What ships inside the app

- The editor (`mu`) plus its third-party dependencies (PyQt6, etc.), installed
  into the bundle by Briefcase from `[tool.briefcase.app.mu].requires`.
- A pinned **`uv`** binary — it rides in via the PyPI `uv` wheel, and
  `find_uv()` locates it at runtime through `uv.find_uv_bin()` (no `PATH` or
  `MU_UV` needed in the packaged app).
- The **baseline wheels zip** (`mu/wheels/<version>.zip`), so the learner's
  baseline packages install without the network.
- A relocatable **CPython** (the python-build-standalone build uv itself would
  install, matching the app's Python X.Y and the runner's platform) plus a
  **pip wheel**, in `mu/wheels/python/`.

`python -m mu.wheels --package` fetches all three before packaging (it needs
`uv` installed, to look up the CPython download).

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
