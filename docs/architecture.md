# Mu's Architecture

This section provides a high level overview of how the various parts of Mu
fit together.

## Key Concepts

The key concepts you should know are:

* Mu uses the [PyQt6 framework](https://riverbankcomputing.com/software/pyqt/intro) (that makes the [Qt](https://www.qt.io/) GUI toolkit available to Python) for making its user interface.
* Mu is a modal editor: the behaviour of Mu changes, depending on mode.
* There are a number of core features and behaviours that are always available and never vary, no matter the mode.
* The text area into which users type code is based on a [Scintilla](http://www.scintilla.org/) based widget.
* Mu is easy to internationalise using Python's standard `gettext` based modules and tools.
* Mu's code base is small, well documented and has 100% unit test coverage.

## Code Structure

The code is found in the `mu` directory and organised in the following way:

* The application is created and configured in `app.py`.
* Most of the fundamental logic for Mu is in `logic.py`.
* The Python3 debugger consists of a debug client and debug runner found in the `debugger` namespace. A description of how the debugger works can be found in [debugger](debugger.md).
* Interacting with the UI layer is done via the `Window` class in the `interface.main` module. Mu specific UI code used by the `Window` class found in the other modules in the namespace.
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
* Graphical assets, fonts and CSS descriptions for the themes are all found under `resources`.

Bundled plugins live outside `mu`, under `plugins/<name>/`
(`plugins/circuitpython` and `plugins/pygamezero`, the CircuitPython and Pygame
Zero modes): each is its own package, a member
of the repo's uv workspace, installed with Nu and found through its
`mu.plugins` entry point exactly like a community plugin. `plugins/example` is
the template for writing one. See [plugins](plugins.md) and
[packaging](packaging.md).

All classes, methods and functions have documentation *written for humans*.
These are extracted into the [api](api.md).

[tests](tests.md) is in the `tests` directory (and each bundled plugin's in
`plugins/<name>/tests`) and filenames for tests relate
directly to the file they test in the Mu code base. The module / directory
structure mirrors the organisation of the Mu code base. We use PyTest's assert
based unit testing. All tests have a comment describing their intent.

The documentation you're reading right now (i.e. that written for developers)
is found in the `docs` directory. We use [MkDocs](https://www.mkdocs.org/) with
the [Material](https://squidfunk.github.io/mkdocs-material/) theme to write our
docs and publish them with GitHub Pages.
Other documentation (tutorials, user help and so on) is on [website](website.md).

The `utils` directory contains various scripts used to scrape and / or build
the API documentation used by Mu's autocomplete and call tip functionality.

The other assets in the root directory of the project are mainly for
documentation (such as our Code of Conduct), configuration (for testing) or
packaging for various platforms (see [packaging](packaging.md)).

If you want to make changes please read [contributing](contributing.md).
