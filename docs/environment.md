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

**Environment Variables** (also on the Environment tab) are set each time you
run a program, one `NAME=value` per line.

## What Nu Ran

The **What Nu Ran** section lists every command Nu has run for you since it
started, newest last: when it ran, where, whether it worked (`exit
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
the admin dialog shows **What Nu Ran** as a tab of its own there instead. In
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

**Debug**, and Pygame Zero's **Play**, also use `uv run` for a program with
the block, a little differently: uv adds the packages the block lists *on
top of* your environment, so the debugger and Pygame Zero (and the packages
you added) are still there. The first line in the output pane shows that
command too:

```text
$ uv run --python /home/you/…/bin/python --no-project --with-requirements /home/you/mu_code/game.py python -m pgzero /home/you/mu_code/game.py
```

The debugger waits for uv to fetch the packages before it starts (up to five
minutes). Such a game, or a program you're debugging, stops when you click
**Stop**, as usual.

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

## More than one environment (advanced)

Most people only ever need the one environment Nu makes. But if you work on
more than one project, you might want a **separate set of packages for each
project**, so that what you add for one doesn't affect the others. That's what
extra environments are for.

At the bottom of the Environment tab, click **Advanced: more environments**
(it's closed until you open it). It lists your environments: their name, their
Python, and which one Nu uses. The one Nu made for you is marked
**(default)**.

- **New environment…** asks for a name (letters, digits, `-` and `_`, e.g.
  `project-a`) and makes the environment the same way Nu made the first one,
  with the same Python and the packages Nu needs. It shows each command as it
  runs, starting with `uv venv`, and takes a minute or so. The commands are in
  **What Nu Ran** too.
- **Use this one** chooses the selected environment. Click **OK**, and Nu uses
  it **from when you restart Nu** (the status bar says so); until then it
  keeps the one it has. After the restart the status bar shows the new name
  (`Environment: project-a · Python 3.11`), and the Packages tab lists that
  environment's packages. To go back, choose the default one the same way.

Nu keeps the extra environments in a folder called `envs` next to the default
one, one folder each, named after the environment:

| System | Where they are |
|---|---|
| Windows | `%LOCALAPPDATA%\python\mu\envs\<name>` |
| macOS | `~/Library/Application Support/mu/envs/<name>` |
| Linux | `~/.local/share/mu/envs/<name>` |

Making one is the same as typing this in a terminal (on Linux; the Advanced
section shows the real command, and Nu then adds the packages it needs):

```bash
uv venv --python 3.11 --seed ~/.local/share/mu/envs/project-a
uv pip install --python ~/.local/share/mu/envs/project-a/bin/python ipykernel
```

An environment you make yourself in the `envs` folder shows up in the list
too. Nu only switches to it if it can use it: it needs the same Python version
as Nu and the packages Nu needs to run your programs (the REPL's `ipykernel`,
and Pygame Zero's packages); if not, Nu tells you what's missing and keeps the
environment it has. Using one from a terminal works as above: the Advanced
section shows the command to activate the selected one.

To delete an environment you've made, select it and click **Delete…**. Nu
asks first, then removes its folder with every package in it (your programs
aren't in it, so they stay). You can't delete the default environment, the
one Nu is using, or the one you've chosen for the next start: choose another
and restart Nu first. If Windows says a file in the folder is in use, close
the program using it (or restart your computer) and try again.

Each environment remembers which version of Nu made it (in a
`nu-environment.json` file inside it). When you start Nu with an environment
an older Nu made, Nu brings it up to date first, keeping the packages you
added, just as it does with the default one after an upgrade.

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
same is in **What Nu Ran**. Nu's full log (the **Current Log** tab) has every
command with uv's full path.
