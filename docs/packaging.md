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
publishes a GitHub Release with the installers attached (a tag with a
pre-release segment such as `v2.0.0rc1` publishes as a pre-release). See
[Release process](release.md).

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
- The **baseline wheels zip** (`mu/wheels/<version>.zip`, built by
  `python -m mu.wheels --package` before packaging), so the learner's
  baseline packages install without the network.

At first launch Nu creates the user's environment with
`uv venv --python <X.Y> --seed`, pinned to the *version* of the bundled Python
rather than its path (in a packaged app `sys.executable` is Briefcase's launcher
stub, which uv can't inspect). uv then resolves a real interpreter of that
version: a system install, a uv-managed CPython, or a **download**. So on a
machine with no matching Python, first launch currently needs the network;
bundling a CPython for uv to find (with `UV_PYTHON_DOWNLOADS=never`) is an open
item in `TODO.md` (Phase 4c).

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
