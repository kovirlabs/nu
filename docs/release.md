# Release process

This is the checklist for cutting a release of Nu. CI builds and publishes
the installers, but it doesn't make a release on its own: the checks, the
version numbers and the order of publishing are up to whoever cuts it.

## What CI does

* `test.yml` runs the tests on Windows, macOS and Linux for every push and
  pull request (Python 3.11 and 3.14 everywhere, plus 3.12 and 3.13 on
  Linux).
* CodeQL scans the code, through GitHub's *default setup* (configured in the
  repository's settings, not in a workflow file).
* `docs.yml` publishes these docs on every push to `master` (see
  [the documentation site](docs-site.md)).
* `build.yml` builds the installers with Briefcase (Windows `.msi`, macOS
  zipped `.app`, Linux `.AppImage`) when run by hand or when a `v*` tag is
  pushed. A tag also publishes a GitHub Release with the installers attached.
  See [packaging](packaging.md).

## Version numbers

Nu's versions are plain [PEP 440](https://peps.python.org/pep-0440/) numbers:
`2.0.0`, or `2.0.0b3`, `2.0.0rc1` for a pre-release. The tag is the version
with a `v` in front (`v2.0.0`). A tag with a pre-release segment publishes a
GitHub *pre-release*; a plain `vX.Y.Z` publishes a full release.

The version lives in **two** places, and both must change together:

1. `__version__` in `mu/__init__.py`: the canonical one, read by hatchling
   for the wheel and sdist, and shown in Nu's log.
2. `version` under `[tool.briefcase]` in `pyproject.toml`: Briefcase reads
   only this literal, and it **names the installer files**. Bump only the
   first and the installers come out labelled with the old version.

The bundled plugins (`plugins/pygamezero`, `plugins/circuitpython`) have
versions of their own, in their own `pyproject.toml`. Bump a plugin's version
when the plugin changes, independently of Nu's.

## Before the release

* **Translations.** If user-facing strings changed since the last release,
  bring every catalogue up to date (`make translate_begin LANG=xx_XX` then
  `make translate_done LANG=xx_XX` for each locale, as in
  [translations](translations.md#notes-for-developers)), commit the `.po` and
  `.mo` files, and check `make translate_status`. Give translators time
  before the release if you can.
* **Autocomplete data.** If a mode's API changed (a new Pygame Zero or
  CircuitPython version, say), regenerate its API stubs with the scripts in
  `utils/` (see [modes](modes.md)).
* **Changelog.** Make sure `CHANGES.md` describes what changed since the last
  release, for learners and teachers as well as developers, and give the
  section its version and date.
* **Docs.** Re-read the pages for learners ([Using Nu](help.md),
  [Your Python environment](environment.md), [The BBC micro:bit](microbit.md))
  against what you're releasing, and build the site with
  `uv run --no-sync mkdocs build --strict`.
* **Green.** `make check` passes locally and CI is green on `master`.

## Check it as a learner would

Do these on Windows, macOS and Linux, from a clean state: delete Nu's data
folder (see [Your Python environment](environment.md#where-it-is)) and the
`mu_code` folder first. Running from source with throwaway folders
(`MU_DATA_DIR=... MU_HOME_DIR=... uv run python -m mu`) is fine for a first
pass; the installers get the same checks after they're built (below).

* **First start:** Nu asks for a mode, makes `mu_code` and the learner's
  environment (offline too, from an installer), and doesn't ask again on the
  next start.
* **Files:** **New**, **Load** and **Save** behave; a file with a name is
  autosaved.
* **Python 3:** **Run** a script that uses `input()`; **Run** a script with a
  `# /// script` block and a dependency (the `uv run` command is the first
  line of the output); the **REPL** opens and toggles off; the **Plotter**
  graphs printed tuples.
* **Debugger:** with and without breakpoints; add and remove breakpoints
  while paused; **Stop**, **Continue**, **Step Over**, **Step In**, **Step
  Out** each do what they say, and the variables inspector updates. Quit Nu
  afterwards: it exits cleanly.
* **Environment:** the status bar shows the environment; clicking it opens
  the **Environment** tab; adding and removing a package works and shows the
  command; **What Nu Ran** lists the commands; making a second environment
  under **Advanced** works.
* **Plugins:** the **Plugins** tab lists Pygame Zero and CircuitPython as on;
  switching one off and restarting removes its mode; switching it back on
  restores it.
* **Pygame Zero:** **Play** runs an empty file (a blank window) and a working
  game; **Images**, **Fonts**, **Sounds** and **Music** open the right
  folders.
* **CircuitPython** (with a board): Nu offers to switch mode when the board
  is plugged in; saving `code.py` runs it; **Serial** shows the board, and
  Ctrl+C there gives the REPL; the **Plotter** graphs tuples.
* **micro:bit** (opt-in, from source with `uv sync --extra microbit`, with a
  board): the checklist in `plugins/microbit/README.md`.
* **Everywhere:** **Zoom-in**/**Zoom-out**, **Theme** cycles the looks,
  **Check** marks problems, **Tidy** reformats, **Help** opens
  [Using Nu](help.md), Ctrl+K toggles comments, Ctrl+F finds; **Quit** with
  unsaved work asks first; the cog opens the admin dialog on **Current Log**.

## Cutting the release

**The bundled plugins go to PyPI before `nu-editor`.** `nu-editor`'s wheel
says `Requires-Dist: nu-circuitpython>=…` and `nu-pygamezero>=…`, so if a
release needs a new plugin version, that version must be on PyPI before
`nu-editor` is, or `pip install nu-editor` can't resolve (see
[packaging](packaging.md#bundled-plugins-the-uv-workspace)).
`make publish-live` takes care of the order:

1. For each bundled plugin that changed, bump its version (in its own
   `pyproject.toml`). (`nu-microbit` stays unpublished until it's promoted;
   see [packaging](packaging.md#opt-in-workspace-plugins-microbit).)
2. Bump Nu's version in **both** places (above), finish `CHANGES.md`, and
   commit.
3. Push an annotated tag: `git tag -a v2.0.0 -m "Nu 2.0.0"` then
   `git push origin v2.0.0`. `build.yml` builds the three installers (from
   the plugins in the repository, not PyPI) and publishes the GitHub Release
   with them attached.
4. Download each installer from the release and run the learner checks above
   on real machines: at least current Windows 11, current macOS (Apple
   Silicon) and a current Ubuntu LTS.
5. Publish to PyPI with `make publish-live` (try `make publish-test` first to
   upload to test PyPI). It runs `make check`, builds the sdists and wheels of
   `nu-editor`, `nu-pygamezero` and `nu-circuitpython` into `dist/` (`make
   dist`), uploads the two plugins (a version PyPI already has, because the
   plugin didn't change, is skipped) and then `nu-editor`. It needs twine 7
   or later (the `package` extra) and your PyPI credentials. Check that
   `pip install nu-editor` in a fresh virtual environment installs Nu and its
   plugins and starts.

If the release went out wrong (say, the installers carry the old version):
delete the GitHub Release (`gh release delete vX.Y.Z --yes`) and the tag
(locally and on GitHub), fix it, and tag again. `build.yml`'s `gh release
create` fails if a release for that tag still exists.

The installers are currently **unsigned** (macOS is ad-hoc signed), so
learners see a SmartScreen or Gatekeeper warning; say so in the release
notes. Signing is tracked in `TODO.md` (Phase 4d).

## After the release

* Announce it where Nu's users are, with a link to the release and
  `CHANGES.md`.
* Start a new "unreleased" section at the top of `CHANGES.md`.
* Close the issues the release fixed, and answer reports about it at
  [github.com/kovirlabs/nu/issues](https://github.com/kovirlabs/nu/issues).
