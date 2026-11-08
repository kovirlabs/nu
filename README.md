<p align="center">
  <img src="nu_icon.png" alt="Nu" width="200">
</p>

# Nu — A Simple Python Code Editor

Nu is a maintained, modernized continuation of the
[Mu editor](https://github.com/mu-editor/mu) — a simple code editor for beginner
programmers, shaped by extensive feedback from teachers and learners. It is also
a pleasant "no frills" editor for anyone who wants one. Most importantly: have
fun!

## Why Nu?

The original Mu was archived by its maintainers and is no longer developed.
Nu exists so that beginners — and the wider community — can keep using the
editor safely into the future. The goal is simple: **maintain and modernize**.

Nu is a friendly fork. It builds directly on the work of Nicholas Tollervey and
the many Mu contributors (see [`AUTHORS.md`](AUTHORS.md)) and remains free
software under the GPLv3.

## What Nu is

Like Mu, Nu is a *modal* editor written in Python and built on the Qt toolkit:
a small editor whose behaviour changes depending on the selected mode. The text
area is a Scintilla-based widget with syntax highlighting, and there is a
built-in Jupyter REPL and a data plotter. Nu runs on Windows, macOS, Linux and
Raspberry Pi.

Nu currently ships these modes:

* **Python 3** — write and run desktop Python, with a built-in REPL and plotter.
* **Debugger** — a visual debugger for stepping through Python code.
* **Pygame Zero** — make games the beginner-friendly way.
* **CircuitPython** — work with Adafruit CircuitPython boards via the
  `CIRCUITPY` drive and serial REPL.
* **BBC micro:bit** (opt-in for now) — flash MicroPython programs to a
  micro:bit and use its REPL and plotter. It's new, built on maintained tools,
  and not in the installers until it has been tried on real micro:bits: run
  from source with `uv sync --extra microbit`.

Python 3 and the Debugger are Nu's core. The other modes are **plugins**:
Pygame Zero and CircuitPython come with Nu and are switched on, and anyone
can write more. Learners see and switch them on the **Plugins** tab.

Your programs run in a **Python environment** of their own, made with
[uv](https://docs.astral.sh/uv/), and Nu shows it rather than hiding it: the
status bar names it, and one click shows where it is, how to use it from a
terminal, and every command Nu ran in it.

To keep Nu nimble and easy to maintain, the more niche, hardware-specific modes
inherited from upstream Mu (ESP, Pyboard, Lego, Pico, Snek and the Flask/web
deploy mode), Mu's old micro:bit mode, and their vendored, unmaintained device
tooling have been removed.

## Project status

Nu **2.0.0** is in beta: native installers for Windows, macOS and Linux are
published with each [GitHub release](https://github.com/kovirlabs/nu/releases).
It runs on **PyQt6** and **Python 3.11+** (verified through 3.14). The plan and
what's left (installer signing, installing plugins from the app, the micro:bit
hardware pass) are tracked in [`TODO.md`](TODO.md); what changed since Mu is in
[`CHANGES.md`](CHANGES.md). Guidance for working in this repository lives in
[`CLAUDE.md`](CLAUDE.md).

## Running from source

Nu uses [uv](https://docs.astral.sh/uv/) for development. With uv installed:

```
git clone https://github.com/kovirlabs/nu.git
cd nu
uv sync                  # downloads a managed CPython and the pinned deps
uv run python -m mu      # launch Nu
```

Add `--extra dev` to `uv sync` for the test, lint, docs and translation tools,
or `--all-extras` to include the opt-in micro:bit plugin.

## Development

Run the test suite (add `QT_QPA_PLATFORM=offscreen` to run the Qt tests
headlessly, without a display):

```
uv run pytest
```

The tests never touch your real Nu settings or `mu_code` folder. See
[Tests](https://kovirlabs.github.io/nu/tests/) for the full headless command.

Lint and format with [ruff](https://docs.astral.sh/ruff/) (config lives in
`pyproject.toml`):

```
uv run --no-sync python -m ruff check     # lint
uv run --no-sync python -m ruff format    # reformat in place
```

## Documentation

Nu's documentation, for learners and teachers as well as developers, is at
<https://kovirlabs.github.io/nu/>: start with
[Using Nu](https://kovirlabs.github.io/nu/help/) (what Nu's **Help** button
opens) or the [developer setup](https://kovirlabs.github.io/nu/setup/). Its
source is in [`docs/`](docs/), built with [MkDocs](https://www.mkdocs.org/);
build it locally with `make docs` (or `make docs-serve` for a live preview).

## Reporting problems

Please report bugs and suggest ideas at
<https://github.com/kovirlabs/nu/issues>. Nu's log (the cog in the status bar,
then **Current Log**) helps us a lot; if Nu crashed, its crash window has a
**Copy to clipboard** button for the details. Nu never sends anything by
itself. Contributions are welcome: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Code of Conduct

We want this to be a friendly place. Contributors and collaborators are expected
to follow the Code of Conduct in [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

Nu is free software, licensed under the GNU General Public License v3 (see
[`LICENSE`](LICENSE)). It derives from Mu, Copyright (c) Nicholas H. Tollervey
and contributors.
