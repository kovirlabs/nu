# nu-circuitpython

The **CircuitPython** mode for [Nu](https://github.com/kovirlabs/nu): write
code for boards running [CircuitPython](https://circuitpython.org/). Nu opens
and saves files on the board's `CIRCUITPY` drive, spots the board when it's
plugged in, and its Serial and Plotter buttons talk to the board's REPL.

This is one of Nu's *bundled* plugins: it ships with Nu and is switched on by
default. It's built only on Nu's public plugin API (`mu.plugin`, see
[Writing a Nu plugin](../../docs/plugins.md)), so it's also the worked example
of a `MicroPythonMode` plugin, for a board with a serial REPL.

- **Entry point:** `mu.plugins` → `circuitpython = "nu_circuitpython:CircuitPythonPlugin"`.
  The mode's id is `circuitpython`, as it was when the mode was built into Nu,
  so saved sessions keep working.
- **Dependencies:** `adafruit-board-toolkit`, which recognises CircuitPython
  REPL ports. No `learner-env` extra: CircuitPython code runs on the board.
- **Tests:** `plugins/circuitpython/tests/`, run with Nu's test suite.
