# Nu's architecture

This section provides a high level overview of how the various parts of Nu
fit together. Nu keeps Mu's architecture; what's new is mostly the plugin
host and the uv-managed learner environment.

## Key Concepts

The key concepts you should know are:

* Nu uses the [PyQt6 framework](https://riverbankcomputing.com/software/pyqt/intro) (that makes the [Qt](https://www.qt.io/) GUI toolkit available to Python) for making its user interface.
* Nu is a modal editor: the behaviour of Nu changes, depending on mode.
* There are a number of core features and behaviours that are always available and never vary, no matter the mode.
* The text area into which users type code is based on a [Scintilla](http://www.scintilla.org/) based widget.
* Nu is easy to internationalise using Python's standard `gettext` based modules and tools.
* Nu's code base is small and well documented, and its tests cover almost every line (see [tests](tests.md)).

## Code Structure

The code is found in the `mu` directory and organised in the following way:

* The application is created and configured in `app.py`.
* Most of the fundamental logic for Nu is in `logic.py` (the `Editor` class). It
  never touches Qt directly: it drives the user interface through the `view`
  it's given, which is what makes it testable.
* The Python3 debugger consists of a debug client and debug runner found in the `debugger` namespace. A description of how the debugger works can be found in [debugger](debugger.md).
* Interacting with the UI layer is done via the `Window` class in the `interface.main` module. The rest of the UI code used by the `Window` class is in the other modules in the namespace (`editor`, `panes`, `dialogs`, `themes`, `workers`).
* Internationalization (I18n) related assets are found under `locale`. Learn how this works via [translations](translations.md).
* Modes are found under the `modes` namespace. They all inherit from a `BaseMode` class and there's a tutorial for [modes](modes.md). The core's modes are Python 3 and the Debugger; every other mode comes from a plugin.
* The learner's Python environment (where Python 3 and Pygame Zero programs
  run) is managed in `virtual_environment.py`: `VirtualEnvironment` (the `venv`
  singleton) and the `Uv` wrapper around [uv](https://docs.astral.sh/uv/).
  Every uv command goes through `Uv`, which records it in the GUI-free
  `command_log.py` (shown to the learner as "What Nu Ran", and logged at
  INFO). `script_metadata.py` finds [PEP 723](https://peps.python.org/pep-0723/)
  `# /// script` blocks: the Python 3 mode's **Run** uses
  `uv run --python <env python> --script <file>` for a file with one. The
  status bar's environment indicator and the admin dialog's Environment tab
  show it all; see [Your Python environment](environment.md).
* The plugin host is the `plugin` namespace: the public, versioned `mu.plugin` API, plugin discovery (`plugin.loader`) and error isolation (`plugin.errors`). See [plugins](plugins.md).
* Settings (`settings.json`, `session.json`, `venv.json`) are read and written by `settings.py`; where they live is in `config.py`. See [settings and sessions](design/settings-and-sessions.md#nu-today).
* Graphical assets, fonts and CSS descriptions for the themes are all found under `resources`.

Bundled plugins live outside `mu`, under `plugins/<name>/`
(`plugins/circuitpython` and `plugins/pygamezero`, the CircuitPython and Pygame
Zero modes): each is its own package, a member
of the repo's uv workspace, installed with Nu and found through its
`mu.plugins` entry point exactly like a community plugin.
`plugins/microbit` (BBC micro:bit) is a workspace member too, but opt-in for
now. `plugins/example` is the template for writing one. See
[plugins](plugins.md) and [packaging](packaging.md).

All classes, methods and functions have documentation *written for humans*.
These are extracted into the [api](api.md).

[tests](tests.md) is in the `tests` directory (and each bundled plugin's in
`plugins/<name>/tests`) and filenames for tests relate
directly to the file they test in the code base. The module / directory
structure mirrors the organisation of the code base. We use PyTest's assert
based unit testing. All tests have a comment describing their intent.

The documentation you're reading right now (i.e. that written for developers)
is found in the `docs` directory. We use [MkDocs](https://www.mkdocs.org/) with
the [Material](https://squidfunk.github.io/mkdocs-material/) theme to write our
docs and publish them with GitHub Pages. The same site holds the pages for
learners and teachers (what **Help** opens); see
[the documentation site](docs-site.md).

The `utils` directory contains various scripts used to scrape and / or build
the API data used by the autocomplete and call tip functionality, and
`utils/recover_renamed_translations.py` (see [translations](translations.md)).

The other assets in the root directory of the project are mainly for
documentation (such as our Code of Conduct), configuration (for testing) or
packaging for various platforms (see [packaging](packaging.md)).

If you want to make changes please read [contributing](contributing.md).

## How Nu starts

`mu.app.run` (reached through `python -m mu`, `run.py`, the `nu-editor`
command or an installer's launcher):

1. Sets up logging and the crash handler, and makes sure only one Nu is
   running.
2. Loads the settings (`settings.init()`), and creates the `QApplication`.
3. Shows the splash screen while a `StartupWorker` thread checks the
   learner's environment, creating or repairing it if needed
   (`venv.ensure_and_create`); its progress is the text on the splash screen.
4. Creates the `Window` (the view) and the `Editor` (the logic), handing it
   the window.
5. `setup_modes` registers the core's two modes through a plugin `Host`,
   then loads every installed or dropped-in plugin that's switched on
   (`mu.plugin.loader.load_plugins`), and installs the plugin error handler.
6. Connects the status bar, restores the last session (open files, mode,
   theme, window; or asks for a mode on the very first start) and opens any
   files named on the command line.
7. Runs Qt's event loop until Nu quits, when the settings are saved.
