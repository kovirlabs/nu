# Run the user's code inside its own virtual environment

## Decision

Mu, whether pip-installed or via installer will maintain a separate virtual
environment for running the user's code. Initially this will contain all
the dependencies used by any of our modes, plus any packages the user
installs in addition.

The dependencies needed for the running of the editor itself (mostly PyQt
stuff but currently including some serial packages which have "leaked" from
the modes) will be kept in a separate environment, virtual or otherwise.

The installers will have to support this approach by bundling wheels (as
our assumption is that some schools at least will have restricted or no
internet access).

For now we're not breaking out modes into plugins or separate environments
although that's a natural extension of this work. If that were done later,
each mode could specify its own dependencies which could be installed on
demand.

## Background

* Getting Mu to unpack and run out of the box on the three main platforms:
  Windows, OS X & Linux has always proven challenging.
* In addition, within the Mu codebase, the code to run the user's code is
  scattered and contains a fragile re-implementation of a virtual environment.
* Installing 3rd-party modules was also a little fragile as we had to run
  `pip` with a `--target` parameter
* There are other issues, especially around the Jupyter console and, on
  Windows, its use of the pywin32 packages which have slightly odd path
  handling.

## Discussion and Implementation

This started off with work by @ntoll to have the 3rd-party apps installed
into a virtual environment rather than with the `--target` parameter which
would try to force them into a directory where Mu could find them. This
stalled somewhat, especially on Windows, and I (@tjguk) took over that
branch.

Having focused on the getting a virtual environment running for the 3rd-party
installs, I realised that having a venv for the whole of the code runtime
might help solve some of the other issues. After a few merges to get some
changes in, especially those by @tmontes to the installer, we started PR#1072
https://github.com/mu-editor/mu/pull/1072.

There is now a `virtual_environment.py` module which initially brings together
various pieces of code which were scattered around the codebase and adds
support for creating and installing into a virtual environment. The various
places where the user code is run (mostly within the `modes` package, but including
inside `panes.py`) have been updated to use this virtual environment logic.
Possible future work might involve adding a "run process" method to the class
itself.

As far as possible this should remove the need to hack up special `PYTHONPATH`,
`*.pth` and `site.py` logic.

### Implemented via:

* https://github.com/mu-editor/mu/pull/1068
* https://github.com/mu-editor/mu/pull/1072
* https://github.com/mu-editor/mu/pull/1056
* https://github.com/mu-editor/mu/pull/1058

### Discussion in:

* https://github.com/mu-editor/mu/issues/1061
* https://github.com/mu-editor/mu/issues/1070

## Nu today

The decision stands: learners' programs run in an environment of their own,
never in Nu's. What changed is how it's made, and that the learner can see it.
The learner-facing description is [Your Python environment](../environment.md);
this is the developer's summary.

* **Made and managed with [uv](https://docs.astral.sh/uv/)**, not `venv` and
  `pip`. `mu/virtual_environment.py` has the `VirtualEnvironment` class (the
  module-level `venv` singleton) and `Uv`, the one place uv is run. The
  environment is made with `uv venv --python <Python> --seed <folder>`, and
  packages are added and removed with `uv pip install` / `uv pip uninstall
  --python <the environment's Python>`.
* **Where:** in Nu's data folder (`mu.config.DATA_DIR`), as
  `mu_venv-<Python version>-<date and time>` (e.g.
  `mu_venv-311-20261108-030353`). Extra, named environments the learner makes
  are in `DATA_DIR/envs/<name>`. `venv.json` records which one is in use (see
  [settings and sessions](settings-and-sessions.md#nu-today)).
* **What goes in it:** the *baseline packages* from
  `mu.wheels.baseline_packages()`: the core's own (`ipykernel`, for the
  REPL) plus each installed plugin's `learner-env` extra (Pygame Zero's
  `pgzero` and `pygame`). The modes are now [plugins](../plugins.md), so a
  plugin declares what it needs, as this page's last paragraph foresaw.
* **Offline:** the installers carry a Python (unpacked on first start by
  `ensure_bundled_python`) and a wheelhouse of the baseline packages, so the
  environment can be made with no internet; see
  [packaging](../packaging.md#what-ships-inside-the-app).
* **Visible:** every uv command goes through `Uv`, which records it in
  `mu.command_log` (shown as **What Nu Ran**). The status bar shows the
  environment, and the Environment tab shows where it is and the commands to
  use it from a terminal.
* **Programs that list their packages:** a script with a
  [PEP 723](https://peps.python.org/pep-0723/) `# /// script` block is run
  with `uv run --python <the environment's Python> --script`, which adds what
  the block lists (`mu.script_metadata` finds the block).
* Running a program still activates the environment for the child process
  (`VirtualEnvironment.activation_vars`), and the debugger is the one place
  that still sets `PYTHONPATH`, so its runner can import Nu (see
  [debugger](../debugger.md#how-a-debug-session-starts)).
