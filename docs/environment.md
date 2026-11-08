# Your Python environment

When you press **Run** in Python 3 or Pygame Zero mode, Nu doesn't run your
program with its own Python. It uses a **Python environment** made just for
your programs: a folder with its own copy of Python and the packages you add.
Nu doesn't hide it. You can see it, see every command Nu runs in it, and use
it yourself from a terminal.

## Where it is

The status bar at the bottom of Nu's window shows it:

```text
Environment: mu_venv · Python 3.11
```

`mu_venv` is its name (Mu, the editor Nu continues, chose it), and
`Python 3.11` is the version of Python your programs run with. Click it to
open the **Environment** tab, which shows:

- **Folder**: where the environment lives. The folder's full name ends in the
  Python version and the date Nu made it, e.g. `mu_venv-311-20261108-030353`.
- **Python**: the Python program inside it that runs your code.
- **Activate it**, **Add a package** and **Run a program**: the commands to do
  the same things yourself in a terminal (see below).
- **Nu's uv**: where the copy of `uv` that Nu uses is.

Each has a **Copy** button.

| System | Where the folder is |
|---|---|
| Windows | `%LOCALAPPDATA%\python\mu\mu_venv-…` |
| macOS | `~/Library/Application Support/mu/mu_venv-…` |
| Linux | `~/.local/share/mu/mu_venv-…` |

You'll only see the environment in modes that use it. CircuitPython runs
your code on the board, so it doesn't show it.

Some [plugins](plugins.md#managing-plugins) need packages in this
environment for their mode (Pygame Zero needs `pgzero` and `pygame`). Nu
installs those itself when it makes the environment.

## Adding and removing packages

On the Environment tab, open **Packages**, put each package's name on its own
line (e.g. `cowsay`), and click **OK**. To remove a package, delete its line.
Nu shows the real command it runs, then what that command prints:

```text
$ uv pip install --upgrade --python /home/you/.local/share/mu/mu_venv-311-…/bin/python cowsay
Resolved 1 package in 236ms
Installed 1 package in 13ms
 + cowsay==6.1
```

Packages come from [PyPI](https://pypi.org/), so adding one needs the
internet.

**Environment variables** (also on the Environment tab) are set each time you
run a program, one `NAME=value` per line.

## What Nu ran

The **What Nu ran** section lists every command Nu has run in your environment
since it started, newest last: when it ran, where, whether it worked (`exit
code 0` means it did), and the last few lines it printed. These are the
commands you'll see:

```text
uv venv --python 3.11 --seed /home/you/.local/share/mu/mu_venv-311-…
uv pip install --upgrade --python /home/you/…/bin/python cowsay
uv pip uninstall --python /home/you/…/bin/python cowsay
uv pip list --format=json --quiet --python /home/you/…/bin/python
uv run --python /home/you/…/bin/python --script /home/you/mu_code/hello.py
```

- `uv venv` made the environment (the first time Nu started).
- `uv pip install` / `uv pip uninstall` added or removed packages.
- `uv pip list` lists the packages; Nu runs it to show you yours.
- `uv run` ran a program that lists the packages it needs (next section).

Modes for boards don't use this environment, so they have no Environment tab;
the admin dialog shows **What Nu ran** as a tab of its own there instead. In
[micro:bit mode](microbit.md) that's where you'll see the `mpremote` command
that copied your program onto the micro:bit.

[uv](https://docs.astral.sh/uv/) is the tool Nu uses to manage Python
environments. `--python` tells it which environment to use: the Python inside
yours.

## Programs that list the packages they need

A program can list the packages it needs in a comment block at the top,
written the way [PEP 723](https://peps.python.org/pep-0723/) describes:

```python
# /// script
# dependencies = ["cowsay"]
# ///

import cowsay

cowsay.cow("Hello!")
```

When a program has this block, **Run** runs it with `uv run`, which fetches
the listed packages for you, so you don't have to add them on the Packages
tab first. The first line in the output pane shows the command:

```text
$ uv run --python /home/you/…/bin/python --script /home/you/mu_code/cow.py
```

Some things to know:

- The packages go into a separate environment that uv keeps just for that
  program (in uv's cache, built with your environment's Python), not into your
  environment. So the program can use what it lists and Python's standard
  library, but **not** packages you added on the Packages tab. List
  everything it needs.
- uv needs the internet the first time it fetches a package; after that it
  reuses its copy.
- When the program ends there's no `>>>` prompt, as there is after an
  ordinary Run. Use the **REPL** button for that.
- Files without the block run exactly as before, with your environment.

The same file works anywhere uv is installed: `uv run cow.py` in a terminal
does the same thing.

## Using it yourself from a terminal

Copy the commands from the Environment tab. To **activate** the environment,
so `python` and `pip` in that terminal are the environment's:

On macOS or Linux:

```bash
source /home/you/.local/share/mu/mu_venv-311-…/bin/activate
python hello.py
```

On Windows (Command Prompt or PowerShell):

```text
C:\Users\you\AppData\Local\python\mu\mu_venv-311-…\Scripts\activate
python hello.py
```

Type `deactivate` to stop. Or, without activating, tell uv which Python to
use:

```bash
uv pip install --python /home/you/…/bin/python cowsay
uv run --python /home/you/…/bin/python hello.py
```

If your terminal says `uv` isn't found, either
[install uv](https://docs.astral.sh/uv/getting-started/installation/), or
type the full path shown as **Nu's uv** on the Environment tab instead of
`uv` (Nu's installers come with their own copy, which isn't on your `PATH`).

## Troubleshooting

When `uv run` goes wrong, Nu puts a line starting with `Hint:` just above
uv's own message:

| You see | What to do |
|---|---|
| *uv couldn't download the packages this program needs* | Connect to the internet and Run again. |
| *a package in this program's "dependencies" wasn't found on PyPI* | Check the package's spelling in the `# /// script` block. |
| *the "# /// script" block … isn't written correctly* | Check the block's brackets, quotes and commas. |
| *every line of the "# /// script" block must start with "#"* | Every line inside the block starts with `#`, and the block ends with `# ///`. |
| *"requires-python" asks for a different Python* | The program wants another Python version than your environment's; it may not work. |
| *Nu can't find uv* | Reinstall Nu, or remove the block to run the program as an ordinary one. |

If installing a package fails, the package dialog shows uv's message; the
same is in **What Nu ran**. Nu's full log (the **Current Log** tab) has every
command with uv's full path.
