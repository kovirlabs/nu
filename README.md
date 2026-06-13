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
* **Pygame Zero** — make games the beginner-friendly way.
* **CircuitPython** — work with Adafruit CircuitPython boards via the
  `CIRCUITPY` drive and serial REPL.
* **Debugger** — a visual debugger for stepping through Python code.

To keep Nu nimble and easy to maintain, the more niche, hardware-specific modes
inherited from upstream Mu (micro:bit, ESP, Pyboard, Lego, Pico, Snek and the
Flask/web deploy mode) — along with their vendored, unmaintained device tooling —
have been removed.

## Project status

Nu is under active modernization. It now runs on **PyQt6** and **Python 3.11+**
(verified through 3.14), with development managed by
[uv](https://docs.astral.sh/uv/). The remaining work — uv-driven user
environments and consolidated [Briefcase](https://briefcase.readthedocs.io/)
installers — is tracked in [`TODO.md`](TODO.md). Guidance for working in this
repository lives in [`CLAUDE.md`](CLAUDE.md).

## Running from source

Nu uses [uv](https://docs.astral.sh/uv/) for development. With uv installed:

```
git clone https://github.com/kovirlabs/nu.git
cd nu
uv sync                  # downloads a managed CPython and the pinned deps
uv run python -m mu      # launch Nu
```

## Development

Run the test suite (add `QT_QPA_PLATFORM=offscreen` to run the Qt tests
headlessly, without a display):

```
uv run pytest
```

Lint and format with [ruff](https://docs.astral.sh/ruff/) (config lives in
`pyproject.toml`):

```
uv run --no-sync python -m ruff check     # lint
uv run --no-sync python -m ruff format    # reformat in place
```

## Documentation

The developer documentation lives in [`docs/`](docs/), is built with
[MkDocs](https://www.mkdocs.org/) and is published with GitHub Pages at
<https://kovirlabs.github.io/nu/>. Build it locally with `make docs` (or
`make docs-serve` for a live preview).

Note that much of this documentation is inherited from upstream Mu and predates
this fork — it is being modernized incrementally.

## Code of Conduct

We want this to be a friendly place. Contributors and collaborators are expected
to follow the Code of Conduct in [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

Nu is free software, licensed under the GNU General Public License v3 (see
[`LICENSE`](LICENSE)). It derives from Mu, Copyright (c) Nicholas H. Tollervey
and contributors.
