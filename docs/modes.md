# Modes in Nu

Nu, like Mu before it, is a modal editor: it behaves differently depending on
the currently selected mode. The name of the current mode is always displayed
in the bottom right hand corner of Nu's window. Clicking the **Mode** button
opens a dialog box to allow users to select a new mode.

## What Are Modes?

Modes are a way to customise how Nu should behave. This simplifies Nu: rather
than trying to provide every possible feature at once (and thus become a
nightmare of complexity for the user), modes bring related features together in
a simple and easy to use manner.

Modes are able to add buttons to the user interface, handle certain events
(such as when one of the mode's buttons is clicked) and provide contextual
information for Nu (such as where files should be saved or what API metadata
is available). It's also possible for one mode to transition to another and
some modes are only available as transitional modes (i.e. they may not be
selected by the user). A good example of such a "transitional" mode is the
Python 3 debugger, which can only be accessed from the standard Python 3 mode.

Nu's **core** has just two modes: **Python 3** and the **Debugger**. Every
other mode is a [plugin](plugins.md). **CircuitPython** and **Pygame Zero** are
*bundled* plugins, shipped and switched on by default, that live in this repo
under `plugins/circuitpython/` and `plugins/pygamezero/`. **BBC micro:bit** is
a plugin in this repo too (`plugins/microbit/`), but opt-in until it has been
tried on real micro:bits. Learners switch plugins on and off on the
**Plugins** tab. The images are used with permission, see
[copyright](copyright.md).

### CircuitPython Mode

![](circuit_playground.jpg)

!!! note
    CircuitPython is a bundled plugin: the `nu-circuitpython` package in
    `plugins/circuitpython/`, built on the public [plugin API](plugins.md) only.
    It's the worked example of a mode for a board with a serial REPL.

[Adafruit](http://adafruit.com/) make extraordinarily awesome boards for
embedded development. Many of these boards run Adafruit's own flavour of
[MicroPython](http://micropython.org/) called
[CircuitPython](https://circuitpython.org/).

The CircuitPython mode
inherits from a base MicroPython mode that provides USB/serial connectivity to
the board. Because source code is stored directly on the CircuitPython boards,
this mode ensures that filesystem based operations actually happen on the
connected device. If no such device is found, the mode will warn you.

### BBC micro:bit Mode

![](microbit.png)

The [BBC micro:bit](http://microbit.org/) is a small computing device for
young coders that is capable of running MicroPython. Mu was originally created
as volunteer led effort as part of the Python Software Foundation's
contribution to the project.

!!! note
    micro:bit is an opt-in plugin: the `nu-microbit` package in
    `plugins/microbit/`, installed with `uv sync --extra microbit` and not yet
    in the installers. Mu's micro:bit mode and its unmaintained tools (uFlash,
    microfs) were removed; this one is new, built on
    [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html).
    See [The BBC micro:bit](microbit.md).

Just like the CircuitPython mode, micro:bit mode inherits from the base
MicroPython mode, so there's a REPL based interface to the device. **Flash**
puts the current file on the micro:bit as `main.py` (putting MicroPython on
first, if it isn't there). Mu's Files pane, for the micro:bit's file system,
isn't back yet (see [plugins](plugins.md#roadmap-the-microbit-files-pane)).

### Pygame Zero / PyGame Mode

![](pygame.png)

!!! note
    Pygame Zero is a bundled plugin: the `nu-pygamezero` package in
    `plugins/pygamezero/`, built on the public [plugin API](plugins.md) only.
    It's the best worked example of a full mode as a plugin.

[PyGame](http://pygame.org/) (or, more correctly: "pygame") is a cross
platform set of Python libraries for writing games.
[Pygame Zero](https://pygame-zero.readthedocs.io/en/stable/) is a wrapper for
pygame that makes it easy for beginners to make games. If both pygame and
Pygame Zero are installed in the learner's environment (Nu does this itself:
the plugin lists them as its `learner-env` packages), Nu's Pygame Zero mode
makes it easy for beginner programmers to create games.

This mode provides a **Play** button that uses Pygame Zero's game-runner to
launch the user's games. Four further buttons, **Images**, **Fonts**,
**Sounds** and **Music**, open the operating system's file manager on the
folders for those game assets. This makes it easy for the user to copy and
paste new game assets into the right place.

The standard Python3 mode (see below) is probably a better environment for more
advanced pygame-only development. Nu ensures that all the game assets required
by the [Pygame Zero introductory tutorial](https://pygame-zero.readthedocs.io/en/stable/introduction.html)
are available by default.

### Standard Python3 Mode

![](python.png)

This mode is for creating simple Python 3 programs. As with the other modes,
there is a REPL for live programming, but in this case it is an iPython based
REPL that uses [project Jupyter](http://jupyter.org/). As with other Jupyter
notebooks, it's possible to embed graphics and charts into the REPL so it
becomes a interesting to read and work with.

There are two ways to run your script in this mode:

1. Click the "Run" button: will launch the script using Python's interactive
   mode (so you'll be dropped into a basic interactive Python shell upon the
   script's completion). A script that lists the packages it needs in a
   [PEP 723](environment.md#programs-that-list-the-packages-they-need)
   `# /// script` block is run with `uv run` instead, which fetches them
   first (and can't drop into the shell).
2. Click the "Debug" button: Python mode transitions to the debug mode - a
   graphical way to inspect and watch your code execute.
   
Because of the overhead needed to start the graphical debugger it takes longer
to start running your script. This is especially noticeable on the Raspberry Pi.

Python 2 isn't supported by Nu and never will be.

### Debug Mode

It's only possible to enter debug mode from standard Python mode. It's purpose
is to manage the execution and inspection of your code.

Clicking the margin of the editor toggles "break points" that tell the debugger
where to pause. Once paused it's possible to inspect the state of various
objects at that moment in the code's execution and step over, into and out of
lines of code. You're able to watch Python execute your code, allowing you to
discover where there may be bugs.

Once the code has finished the debug mode transitions back to standard
Python mode.

## Create a New Mode

A new mode is a [plugin](plugins.md): a Python package with a `mu.plugins`
entry point, whose mode class subclasses `mu.plugin.Mode` (or
`mu.plugin.MicroPythonMode` for a board with a serial REPL) and which imports
nothing from Nu except `mu.plugin`. [Writing a Nu plugin](plugins.md) is the
contract; this section is about the mode itself. Start from the template in
`plugins/example/`, and use the two bundled plugins as worked examples:

* **Pygame Zero** (`plugins/pygamezero/nu_pygamezero/mode.py`) runs the
  learner's program in their Python environment, toggles a toolbar button
  while it runs, opens folders, puts demo files in the workspace and needs
  packages in the learner's environment.
* **CircuitPython** (`plugins/circuitpython/nu_circuitpython/mode.py`) is a
  `MicroPythonMode`: it recognises its boards when they're plugged in, keeps
  the learner's files on the board's drive, and gets Serial and Plotter
  buttons that talk to the board's REPL.

The core's own two modes, Python 3 and the Debugger (`mu/modes/python3.py`
and `mu/modes/debugger.py`), are the exception: they're built in, registered
in `setup_modes` in `mu/app.py`, and use Nu's internals directly. Don't add
another mode that way.

### Create a Class

The most important aspects of a mode are encapsulated in a class that
represents the mode. It **must** inherit from `mu.plugin.Mode` (Nu's
`BaseMode`). If your new mode is for a MicroPython based device, inherit from
`mu.plugin.MicroPythonMode` instead, since this includes various helpful
utilities for such things as finding a connected device and running a REPL
over a USB-serial connection.

The convention is a module of its own for the mode, next to the plugin that
registers it. For example, the Pygame Zero plugin's `nu_pygamezero/mode.py`
holds the `PyGameZeroMode` class, and `nu_pygamezero/__init__.py` the
`PygameZeroPlugin` that registers it.

### Integrate the Mode

Nu needs to know that the new mode is available to use. A plugin does this in
two steps:

* Register the mode from the plugin: a `ModePlugin` with `mode = YourMode`
  does it for you (and `images` registers the folder of icons your mode
  uses).
* Advertise the plugin with a `mu.plugins` entry point in your package's
  `pyproject.toml`, and install the package into the environment Nu runs
  from. Nu finds it the next time it starts.

Nu creates the mode with its internal `editor` and `view` objects and sets
`self.host` to the `Host` that registered it. Reach the editor through
`self.host`: `self.editor` and `self.view` are internal and can change in
any release.

### Update the Class's Behaviour

The core elements of your new mode's class that need updating include some
attributes and three methods.

The attributes that must be changed are:

* `name` -- the full name of the mode, for example, "Pygame Zero".
* `short_name` -- a stable, unique id, used as a key in the settings and
  saved sessions. Don't change it once people use your mode.
* `description` -- a short description of the mode to be displayed in the
  mode picker. For example, "Make games with Pygame Zero".
* `icon` -- an icon used to represent the mode in the mode picker: the name
  of a `.png` (or `.svg`) image in your plugin's registered images folder
  (or one of Nu's own in `mu/resources/images`).

Additional attributes with safe default values set in the `Mode` class
which may be of value for you to change are:

* `save_timeout` -- the number of seconds to wait before auto-saving work. If
  this value is 0 (zero) Nu will not auto-save changed files when in this mode
  (CircuitPython sets it: a board restarts whenever a file on it is saved).
* `builtins` -- a list of strings defining symbols that Nu's code checker
  must assume are builtins (above and beyond Python's standard builtins).
* `star_imports` -- a dict mapping a module to the names its `import *` brings
  in (the micro:bit lists `from microbit import *`'s). The code checker reads
  such an import as naming them, so it can still spot undefined names.
* `module_names` -- the module names the learner mustn't use for their own
  files, because they'd hide a real module (CircuitPython lists the modules
  built into CircuitPython).
* `uses_user_environment` -- set it to `True` if the mode runs the learner's
  programs in Nu's Python environment, so the admin dialog shows that
  environment's variables and third-party packages.

A mode may also override `ensure_workspace_assets(workspace_dir)`, which Nu
calls the first time the mode is used in a session (including the mode Nu
starts in) to put what it needs into the workspace (Pygame Zero creates its
`images`, `fonts`, `sounds` and `music` folders with the tutorials' demo files).
It must leave anything already there alone.

!!! note
    When creating strings that will be seen by users please remember to use
    the conventions for internationalization (i18n). Put simply, enclose your
    strings in a call to `_` like this:

    ```
    _('This string will be translated automatically')
    ```

    Please see [translations](translations.md) for more details. (Only the
    bundled plugins' strings are translated today: they share Nu's catalog.)

You should pay attention to three methods of your class: `actions`,
`api` and `workspace_dir`. You must override `actions` and `api` (see
below) and *may* want to override `workspace_dir`.

The purpose of the `workspace_dir` method is to return a string
representation of the path to the directory containing the code created with
this mode. The default implementation is generally safe to use, but a board
that stores the learner's code on itself may want to point to the connected
device (if attached) or a safe default on the user's filesystem (if no device
is attached). See how the CircuitPython mode does it. If in doubt, just use
the inherited method.

However, you **must** override the `actions` method. It must return a list
of dictionaries that describe the buttons to be added to Nu's user interface.
Each dictionary must contain the following key/value pairs:

* `name` -- the name of the button, which doubles as the name of its icon
  (in your plugin's images folder, or one of Nu's) and as its id, so it must
  be unique. Prefix your own icons' names with your plugin's name (the
  CircuitPython mode's Serial button is `circuitpython-serial`). To create a
  new button start with the blank `button.png` image in `mu/resources/images`
  and use either an icon from the
  [FontAwesome](https://fontawesome.bootstrapcheatsheets.com/) set of icons,
  or some other graphical device that looks visually similar. Make sure that
  the colour of the image is correct blue of (hex value) #336699. Please
  remember to centre it within the button and make sure it has the same sort
  of scale as the existing buttons.
* `display_name` -- the string displayed immediately underneath the button
  in Nu's user interface.
* `description` -- the string displayed as a tool-top when the mouse
  pointer hovers over the button, but the button remains unclicked.
* `handler` -- a reference to a method you have created in your mode's class
  that is called, with an event object, when the button is clicked.
* `shortcut` -- a string representation of the keyboard shortcut for the
  button. Valid examples include, `'F5'` (for function key 5) or,
  `'Ctrl+Shift+I'` (for control-shift-I).

By way of illustration, here's the list of dictionaries returned in the
CircuitPython mode. It only offers a Plotter button when Nu can show the
plotter, and that button uses Nu's own `plotter` icon:

```
buttons = [
    {
        "name": "circuitpython-serial",
        "display_name": _("Serial"),
        "description": _("Open a serial connection to your device."),
        "handler": self.toggle_repl,
        "shortcut": "CTRL+Shift+U",
    }
]
if self.host.plotter_available:
    buttons.append(
        {
            "name": "plotter",
            "display_name": _("Plotter"),
            "description": _("Plot incoming REPL data."),
            "handler": self.toggle_plotter,
            "shortcut": "CTRL+Shift+P",
        }
    )
return buttons
```

Notice how the handlers are references to methods of the mode (here,
`toggle_repl` and `toggle_plotter` come with `MicroPythonMode`); the details
of your own are left to you. Nu simply calls the handler and expects the
author of the mode to know what they're doing. Errors in handlers are
reported to the learner rather than crashing Nu (see
[plugins](plugins.md#when-a-plugin-has-an-error)).

Interactions with the editor go through `self.host`, the `mu.plugin.Host`
that registered the mode: showing messages, the current tab, saving it,
running the learner's program, changing a toolbar button, and so on. Its
methods are listed in [plugins](plugins.md#host), and its docstrings are in
the [api](api.md#muplugin) reference.

Finally, you **must** also override the `api` method, whose role is to
provide a list of strings that conform to Scintilla's protocol for defining
and documenting API's to be used with autocomplete and call-tips. The protocol
is:

```
'foo.bar(arg1, args2="baz") \nMulti line\n\nEnglish description.`
```

Happily, various scripts in the `utils` directory can be used, cloned and
modified to autogenerate this documentation from source code. The reason the
extraction of such API related information is automated is so it makes it
very quick and easy to revise such data as APIs change in the future.

Take a look at the `pgzero_api.py` file and you'll find a simple recipe for
extracting such information from Python modules. Three modules for Python's
standard library (`json`, `inspect` and `importlib`) are used to import
the modules we're interested in, inspect the signatures of the callable objects
found therein and emit a JSON based output (called `pgzero_api.json`).
(`adafruit_api.py` does the same for CircuitPython by reading its online
documentation.)

The resulting JSON is a list of JSON objects containing three attributes:

* `name` -- the module name + object name.
* `args` -- a list of the arguments taken by the callable Python object
  being described.
* `description` -- the docstring associated with the Python object.

Here's an example of such an object from the emitted `pgzero_api.json`
file:

```
{
    "description": "Interface to the screen.",
    "name": "screen.Screen",
    "args": [
        "surface"
    ]
}
```

Given such JSON serialised data, the `mkapi.py` command will take such a file
as input and emit to stdout a list of strings for the API that conform to
Scintilla's protocol to be used by autocomplete and call-tips.

In the case of the Pygame Zero mode, the output from the `mkapi.py` command
ended up in `PYGAMEZERO_APIS`. The list itself is in the plugin's
`nu_pygamezero/api/pygamezero.py` file, and the `__init__.py` found therein
exposes it via the `__all__` list. (CircuitPython's is `ADAFRUIT_APIS`, in
`nu_circuitpython/api/adafruit.py`.)

The mode's `api` method then returns the APIs that a user of the mode may
use: the entries it gets from its host, plus its own. A mode whose programs
run in Python 3 starts from `self.host.python_apis()` (Python's built-ins and
standard library); a MicroPython-family mode starts from
`self.host.shared_apis()` (just what every Python has):

```
from .api import PYGAMEZERO_APIS

... later in the PyGameZeroMode class ...

def api(self):
    return self.host.python_apis() + PYGAMEZERO_APIS

... and in the CircuitPythonMode class ...

def api(self):
    return self.host.shared_apis() + ADAFRUIT_APIS
```

With these relatively simple steps, it's possible to create quite powerful
modes. Most importantly, taking a look at the bundled plugins in `plugins/`
will reveal how to do most of the things you'll need.

However, there is one final aspect of creating a mode that we need to address.

### Unit Test the Mode

**We will not accept any new modes without 100% unit test coverage.**

A bundled plugin keeps its tests in `plugins/<name>/tests`, where they run
with Nu's own (each bundled plugin's tests show how to test a mode through a
mock `Host`).

Please read the guide about [tests](tests.md) for how Nu is tested and the various
expectations we have when it comes to writing tests.

If you are unsure about the best way to go about testing your mode please feel
free to ask for help. We would much rather get a pull request for a "spike"
(draft) version of a new mode and work with the original author on testing the
code, than have no pull request at all.

If in doubt, ask. We're a friendly bunch and [contributing](contributing.md) is easy.
