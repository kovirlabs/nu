# Developer Setup

The source code is hosted on GitHub. Clone the repository with:

```
git clone https://github.com/kovirlabs/nu.git
cd nu
```

**Nu does not and never will use or support Python 2.** Nu targets **PyQt6**
and **Python 3.11+** (verified through 3.14).

## Setting up with uv (recommended)

Nu uses [uv](https://docs.astral.sh/uv/) to manage its development environment.
`uv sync` downloads a managed CPython, creates a `.venv`, and installs the
project (editable) with its runtime dependencies:

```
uv sync                 # runtime deps only
uv sync --extra dev     # + tests, docs, packaging, i18n and lint tooling
```

Run things through the environment with `uv run`:

```
uv run python run.py    # launch Nu
uv run python -m mu     # equivalent
uv run pytest           # run the test suite
```

!!! note
    The canonical packaging definition lives in `pyproject.toml` (hatchling
    backend); `setup.py`/`setup.cfg` were retired. The `[dev]` extra aggregates
    the `[tests]`, `[docs]`, `[package]`, `[i18n]` and `[lint]` extras. `[utils]`
    (scrapers under `utils/`) and `[all]` are defined separately.

## Setting up with a plain virtualenv

If you prefer not to use uv, any Python 3.11+ virtual environment works:

```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Running the tests

```
uv run pytest
```

Qt tests need a platform plugin. To run headlessly (no display) set
`QT_QPA_PLATFORM=offscreen`:

```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -p no:randomly -q
```

Note that `--random-order` is enabled by default (see `pyproject.toml`), so add
`-p no:randomly` or `--random-order-seed=...` when you need a reproducible order
while debugging.

## Linting and formatting

Nu uses [ruff](https://docs.astral.sh/ruff/) for both linting and formatting
(config in `pyproject.toml` `[tool.ruff]`, wrapping at 88 columns):

```
uv run --no-sync python -m ruff check     # lint
uv run --no-sync python -m ruff format    # reformat in place
```

## Using `make`

A `Makefile` (delegating to `make.py`) wraps the common workflows. Typing `make`
on its own lists the available targets. The most useful are:

```
make run       - run the local development version of Nu.
make test      - run the test suite.
make coverage  - run the tests with a coverage report.
make lint      - lint with ruff.
make format    - check formatting; `make tidy` reformats in place.
make check     - format + lint + coverage (the pre-commit gate).
make dist      - build an sdist and wheel.
make docs      - build the documentation with MkDocs.
```

!!! note
    On Windows there is a `make.cmd` file that works in a similar way to the
    `make` command on Unix-like operating systems.

## Before submitting

Before contributing code please make sure you've read
[contributing](contributing.md) and follow its checklist. We expect everyone
participating in the development of Nu to act in accordance with the PSF's
[Code of Conduct](code_of_conduct.md).
