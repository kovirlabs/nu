# Nu's test suite

We have tests so we can make changes with confidence. We use:

* [pytest](https://docs.pytest.org/) for the unit tests, with
  [pytest-random-order](https://pypi.org/project/pytest-random-order/) so
  tests can't quietly depend on running in a particular order.
* [Coverage](https://coverage.readthedocs.io/) (through `pytest-cov`) to see
  which lines the tests exercise.
* [ruff](https://docs.astral.sh/ruff/) to lint and check the formatting (it
  replaced Mu's PyFlakes, pycodestyle and black). See [setup](setup.md#linting-and-formatting).

All of them come with the `dev` extra: `uv sync --extra dev`.

## Where the tests are

* **Nu's core:** `tests/`, mirroring the source tree. The tests for
  `mu/logic.py` are in `tests/test_logic.py`, those for `mu/modes/base.py` in
  `tests/modes/test_base.py`, and so on.
* **Bundled plugins:** each plugin keeps its own tests in
  `plugins/<name>/tests` (`plugins/pygamezero/tests`,
  `plugins/circuitpython/tests`, `plugins/microbit/tests`). `pyproject.toml`
  lists both places as `testpaths`, and puts each plugin's source on
  `sys.path`, so a plain `pytest` runs them all against this checkout.
  The micro:bit plugin is opt-in: without `uv sync --extra microbit` (or
  `--all-extras`) the tests that need its installed entry point are skipped.

The settings live in `pyproject.toml` under `[tool.pytest.ini_options]`, and
shared fixtures in `conftest.py` at the repository root.

## Running the tests

```
uv run pytest
```

or `make test` (verbose), or `make check`, the gate to pass before you open a
pull request: it checks formatting, lints, and runs the tests with coverage.

### Headless, the way CI does it

Qt needs a display. Without one (over SSH, in a container, in CI) use Qt's
`offscreen` platform:

```
QT_QPA_PLATFORM=offscreen LANG=en_GB.utf8 uv run --no-sync pytest -q --basetemp=$HOME/.cache/nu-pytest/bt
```

* `QT_QPA_PLATFORM=offscreen` draws windows in memory instead of on a screen.
  On a minimal Linux without Mesa, Qt still wants `libEGL.so.1`: install your
  distribution's `libegl1`, or put the library on `LD_LIBRARY_PATH`.
* `LANG=en_GB.utf8` gives the locale-sensitive tests the language they
  expect.
* `--no-sync` stops `uv run` re-syncing the environment first (run `uv sync`
  yourself when the dependencies change).
* `-q` is optional: one line of dots instead of a line per test.
* `--basetemp=...` puts pytest's own temporary folders (`tmp_path`) under a
  folder you choose (pytest empties it at the start of each run). You need it
  where `/tmp` is mounted `noexec`: one test makes a real environment in its
  `tmp_path` and runs its Python.

The whole suite takes under a minute.

### A single test, and a reproducible order

```
uv run pytest tests/test_logic.py::test_editor_init
```

Tests run in a random order by default (`addopts = "--random-order"`, from
[pytest-random-order](https://pypi.org/project/pytest-random-order/)). Each
run prints its seed at the top (`Using --random-order-seed=...`): when a
failure only happens in one order, repeat it with `--random-order-seed=<seed>`.
To run in file order instead, add `--random-order-bucket=none`.

!!! note
    `-p no:randomly`, which you may see in older instructions, switches off a
    *different* plugin (pytest-randomly) that Nu doesn't use, so it doesn't
    stop the shuffling.

### Your real Nu data is safe

Before anything imports `mu`, `conftest.py` points the whole test session at
a new temporary folder (removed when the run ends):

* `MU_DATA_DIR`: Nu's data folder (settings, session, `venv.json`, the
  learner's environments, the plugins folder) moves there, so no test reads
  or writes your real ones, even through objects created when a module is
  imported, such as `mu.virtual_environment.venv`.
* `MU_HOME_DIR`: the home folder, so the default workspace (`mu_code`) is a
  throwaway one too.
* `IPYTHONDIR`: the REPL tests start a real IPython.

A test checks that none of these point at the real folders. The same two
variables give you a throwaway profile when you run Nu by hand:

```
MU_DATA_DIR=/tmp/nu-data MU_HOME_DIR=/tmp/nu-home uv run python -m mu
```

## Coverage

```
make coverage
```

runs the tests with a line-by-line report for `mu/` (`--cov=mu`); add
`--cov=nu_pygamezero --cov=nu_circuitpython --cov=nu_microbit` to a `pytest`
run to include the plugins. Mu kept 100% coverage, and Nu is close to it
(99% of `mu/`). **New code should come with tests that cover every line of
it**, and a change shouldn't lower the total. Coverage only shows that a line
ran, not that it's right: it means we've written down how we expect every line
to behave.

## Writing a new test

Put it in the file that mirrors the code it tests, and write it like this:

```python
def test_MyClass_function_name_extra_info():
    """
    The INTENTION of the test: why it matters, any special context, and a
    link to the issue if there is one.
    """
    assert True  # Plain asserts, as is the pytest way.
```

* Test the non-GUI logic (`mu/logic.py`, `mu/virtual_environment.py`, ...)
  by giving it a mock `view`; that separation is what makes it testable.
* Mock what you don't own: subprocesses, `uv`, the network, serial ports,
  devices. No test may need the internet or hardware.
* A plugin's mode is tested through a mock `mu.plugin.Host`; the bundled
  plugins' tests show how.
* Qt threads: wait for a `QThread` to finish before a test lets it go, or Qt
  aborts the run when it's destroyed while still running.
* Run `ruff check` and `ruff format` on your tests too.

If in doubt, ask in the pull request. A draft with partial tests is welcome;
we'll help finish them.
