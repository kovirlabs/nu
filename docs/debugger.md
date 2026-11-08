# Python runner / debugger

An obvious requirement for a Python editor is to run your Python code. In the
Python 3 mode, Nu does this in two ways:

* With the Python runner (the **Run** button).
* With the graphical debugger (the **Debug** button).

!!! note
    In the board modes (CircuitPython, micro:bit) the code runs on the
    attached device, not on the computer. Saving `code.py` to a
    CircuitPython board restarts it with the new code; micro:bit's **Flash**
    copies it over. Pygame Zero's **Play** uses the same runner as **Run**,
    with Pygame Zero's game runner as the program.

Both the Python runner and graphical debugger were created for Mu with the
financial support of the Raspberry Pi Foundation.

Both work in the same way: they start a new child process with the
**learner's** Python (the environment described in
[Your Python environment](environment.md), never Nu's own) and connect its
stdin, stdout and stderr to the `PythonProcessPane` in `mu.interface.panes`,
so you can interact with it in a terminal-like pane.

The runner starts straight away, whereas the debugger has to set up its
scaffolding first, so it is slower to start (most noticeably on a Raspberry
Pi). If you just want to run your script, use the runner.

## Python Runner

Modes don't create the pane themselves: they call
`Window.add_python3_runner` (in `mu.interface.main`, or `Host.run_program`
from a [plugin](plugins.md)), which adds the pane and calls its
`start_process` method. The new `QProcess` becomes the pane's `process`
attribute. You control it with:

* `interpreter`: the Python to run, normally `venv.interpreter` (the
  learner's environment).
* `script_name`: the script to run.
* `working_directory`: where it runs (the Python 3 mode uses the script's
  own folder).
* `interactive`: when `True`, Python is started with `-i`, so the learner
  drops into a simple Python prompt when the script ends, to explore what it
  left behind (at the request of the Raspberry Pi Foundation). The Python 3
  mode's **Run** turns it on.
* `debugger`: when `True`, the debug runner (see below) is started instead,
  and `interactive` is ignored.
* `command_args`: a list of strings passed to the script.
* `envars`: environment variables the learner set on the Environment tab.
  The pane also *activates* the learner's environment for the child
  (`VIRTUAL_ENV`, and its `bin`/`Scripts` folder first on `PATH`), sets
  `PYTHONUNBUFFERED` and `PYTHONIOENCODING=utf-8`, and drops any
  `PYTHONPATH`.
* `python_args`: arguments for the program being started, before the
  script. **Run** uses this for a script with a
  [PEP 723](environment.md#programs-that-list-the-packages-they-need)
  `# /// script` block: the "interpreter" is then `uv`, with
  `run --python <the learner's Python> --script` as its arguments, and
  `interactive` is off (`uv run --script` can't pass `-i`).
* `echo`: a line shown first in the pane, such as the `uv run ...` command,
  so the learner sees what's really running.

The pane then handles the process's events: output arriving (read in chunks,
so a chatty program doesn't freeze Nu), the learner typing, and the process
finishing (it prints `FINISHED` with the exit code).

The `PythonProcessPane` includes basic command history and input editing
features. It'll also respond to CTRL-C and CTRL-D. Copy and paste can be
accessed via a context menu.

## Graphical Debugger

The graphical debugger exists to give beginner programmers an easy way to
observe their code while it is running and allows you to use breakpoints, step
over and into code as well as use a simple object inspector to view the status
of objects in scope.

![](mu-debugger.png)

When the learner clicks **Debug**, Nu switches to the debugger mode and saves
the script, whose buttons drive the debugger client,
which in turn talks to the debug runner process that actually runs the
learner's script.

The debugger is designed to be as simple as possible in order to introduce
beginner programmers to the basic concepts of a debugger in the easiest way. It
does **NOT** strive to be extensive or particularly powerful. Rather, its aim
is to encourage beginner programmers to explore their code while it is running.

In this sense it follows Mu's outlook, which Nu keeps: provide the first
steps for a beginner programmer, with a view to them graduating to a "proper"
development environment once they've found their feet.

Most of the debugger's functionality can be found in the `mu.debugger`
namespace. Coordination is done in the `mu.modes.debugger.DebugMode` class.

### How a debug session starts

1. **Debug** in the Python 3 mode (`PythonMode.debug` in
   `mu/modes/python3.py`) switches to the debugger mode and calls
   `DebugMode.start` (`mu/modes/debugger.py`).
2. `DebugMode.start` saves the script, then calls `add_python3_runner` with
   `debugger=True`, the learner's interpreter and the script's folder.
3. With `debugger=True`, `PythonProcessPane.start_process` runs
   `mu/mu_debug.py <script> <args>` with the learner's Python. The learner's
   environment doesn't contain Nu (by design), so for this one process
   `PYTHONPATH` points at the folder that contains the `mu` package.
4. `mu_debug.py` calls `mu.debugger.runner.run`, which listens on
   `localhost` port `DEBUGGER_PORT` (31415, in `mu/debugger/config.py`) and
   runs the script under a `mu.debugger.runner.Debugger`.
5. Meanwhile `DebugMode.start` creates a `mu.debugger.client.Debugger` for
   the same host and port and starts it, which connects to the runner (see
   below), and shows the variables inspector.
6. The debugger mode's buttons call methods on the client (`do_run`,
   `do_next`, `do_step`, `do_return` for **Continue**, **Step Over**, **Step
   In** and **Step Out**), which send `continue`, `next`, `step` and `return`
   to the runner over the socket.

### Debug Client

The debug client lives in Nu's process. `Debugger.start` moves a
`mu.debugger.client.CommandBufferHandler` onto its own `QThread` (the
"listener thread"), so the UI thread never blocks on the socket. The handler
tries to connect to the runner for up to 10 seconds (the runner may be slow
to start), then turns what arrives into complete messages and emits them as
signals.

The `mu.debugger.client.Debugger` class reacts to those events, and is the
API for Nu to issue commands to the runner. It updates the user interface
through a reference to a `view` object (the debugger mode).

When the session is over (the script finished, the connection failed, or
**Stop** was clicked) the handler quits the listener thread, and
`DebugMode.stop` waits for it (up to 2 seconds) after stopping the runner.
Without that, the thread was still in its event loop when Nu quit, and Qt
aborted Nu as it destroyed it ("QThread: Destroyed while thread is still
running"), a bug Nu inherited from Mu and fixed in 2.0.0.

### Debug Runner

The debug runner runs in the child process and uses Python's
[bdb debugger framework](https://docs.python.org/3/library/bdb.html).

The most interesting part is the `mu.debugger.runner.Debugger` class, which
inherits from `bdb.Bdb`. It responds to commands from the client and sends
messages when things happen during the debugging session (a breakpoint is
hit, a line is reached, the script ends). The client picks these up and Nu's
UI reflects them.

Commands from the client are read by the `command_buffer` function on a
separate thread and queued for `Debugger.interact`, which runs whenever the
debugged script stops. The script stops before its first line, and the first
time `interact` runs there is no client yet: the resulting error takes it to
the branch that waits for the client to connect, starts the
`command_buffer` thread and sends a `bootstrap` message with the current
breakpoints. A later connection problem takes the same path.

`mu.debugger.runner.run(hostname, port, filename, args)` is the runner's
entry point, called by `mu/mu_debug.py` with the script's path as its first
command-line argument; any further arguments are passed on to the script.
