# Nu developer documentation

Nu is a maintained, modernized continuation of the
[Mu editor](https://github.com/mu-editor/mu) — a simple Python code editor for
beginner programmers.

!!! note
    **This documentation is for developers** who want to work on Nu itself, not
    for end users (who want [Using Nu](help.md) and
    [Your Python environment](environment.md)). Some of it is inherited from
    upstream Mu and still describes the pre-fork toolchain (PyQt5, `setup.py`,
    Sphinx/ReadTheDocs, the web mode). Nu has since moved to **PyQt6**,
    **Python 3.11+**, **uv** and **ruff**. For the current, authoritative state
    of the project see
    [`README.md`](https://github.com/kovirlabs/nu/blob/master/README.md),
    `CLAUDE.md` and `TODO.md` in the repository root. These pages are being
    modernized incrementally.

## What Nu is made of

- **The core:** the editor, the Run pane, the REPL and plotter, the learner's
  Python environment (made and managed with uv, and shown to the learner: see
  [Your Python environment](environment.md)), and two modes, **Python 3** and
  the **Graphical Debugger**.
- **Plugins** add the other modes, through a versioned
  [plugin API](plugins.md). Three live in this repository, under `plugins/`:
    - **Pygame Zero** (`nu-pygamezero`) and **CircuitPython**
      (`nu-circuitpython`) are bundled: installed with Nu and switched on.
    - **BBC micro:bit** (`nu-microbit`) is opt-in (`uv sync --extra
      microbit`) until it has been tried on real micro:bits; see
      [The BBC micro:bit](microbit.md).

  Learners switch plugins on and off on the admin dialog's **Plugins** tab.

## Where to start

- New here? Read the [developer setup](setup.md) and the
  [first steps](first-steps.md) for new contributors.
- Want the big picture? Start with the [architecture overview](architecture.md).
- Writing a mode? Follow the [modes tutorial](modes.md), then make it a
  [plugin](plugins.md).
- Curious how the debugger works? See [debugger / runner](debugger.md).
- Adding tests or translations? See [tests](tests.md) and
  [translations](translations.md).

## How the docs are built

These docs are written in Markdown and built with
[MkDocs](https://www.mkdocs.org/) using the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. The
[API reference](api.md) is generated from the source docstrings with
[mkdocstrings](https://mkdocstrings.github.io/). Build locally with
`make docs` (or live-preview with `make docs-serve`).
