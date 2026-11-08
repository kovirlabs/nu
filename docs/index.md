# Nu developer documentation

Nu is a maintained, modernized continuation of the
[Mu editor](https://github.com/mu-editor/mu) — a simple Python code editor for
beginner programmers.

Most of these pages are for **developers** who want to work on Nu itself.
Learners and teachers want [Using Nu](help.md) (what Nu's **Help** button
opens), [Your Python environment](environment.md) and
[The BBC micro:bit](microbit.md).

Nu runs on **PyQt6** and **Python 3.11+**, is developed with **uv** and
**ruff**, and is packaged with **Briefcase**. Where a page describes Mu's
history or design, it says so; everything else describes Nu as it is now.

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
- Cutting a release? See [packaging](packaging.md) and the
  [release process](release.md).
- Wondering why something is the way it is? See the
  [design decisions](design.md).

## How the docs are built

These docs are written in Markdown and built with
[MkDocs](https://www.mkdocs.org/) using the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. The
[API reference](api.md) is generated from the source docstrings with
[mkdocstrings](https://mkdocstrings.github.io/). Build locally with
`make docs` (or live-preview with `make docs-serve`); see
[the documentation site](docs-site.md) for how it's published.

Found a problem, in Nu or in these pages? Please tell us at
[github.com/kovirlabs/nu/issues](https://github.com/kovirlabs/nu/issues).
