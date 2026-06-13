# Nu developer documentation

Nu is a maintained, modernized continuation of the
[Mu editor](https://github.com/mu-editor/mu) — a simple Python code editor for
beginner programmers.

!!! note
    **This documentation is for developers** who want to work on Nu itself, not
    for end users. Much of it is inherited from upstream Mu and still describes
    the pre-fork toolchain (PyQt5, `setup.py`, Sphinx/ReadTheDocs, and the
    micro:bit/web modes). Nu has since moved to **PyQt6**, **Python 3.11+**,
    **uv** and **ruff**, and trimmed the mode set to Python 3, Pygame Zero,
    CircuitPython and the debugger. For the current, authoritative state of the
    project see
    [`README.md`](https://github.com/kovirlabs/nu/blob/master/README.md),
    `CLAUDE.md` and `TODO.md` in the repository root. These pages are being
    modernized incrementally.

## Where to start

- New here? Read the [developer setup](setup.md) and the
  [first steps](first-steps.md) for new contributors.
- Want the big picture? Start with the [architecture overview](architecture.md).
- Writing a mode? Follow the [modes tutorial](modes.md).
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
