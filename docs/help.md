# Using Nu

Nu is a simple Python editor for people learning to code. This page is what
opens when you click **Help** in Nu.

## The buttons

These are always on the toolbar:

| Button | Does | Shortcut |
|---|---|---|
| **Mode** | Switch between modes (see below). | Ctrl+Shift+M |
| **New** | Open a new, empty tab. | Ctrl+N |
| **Load** | Open a file. | Ctrl+O |
| **Save** | Save the current tab. Nu also saves your work every few seconds once a file has a name. | Ctrl+S |
| **Zoom-in** / **Zoom-out** | Make the text bigger or smaller. | Ctrl++ / Ctrl+- |
| **Theme** | Switch between the day, night and high-contrast looks. | F1 |
| **Check** | Look for mistakes in your code and mark them in the margin. | F2 |
| **Tidy** | Neatly reformat your code. | F10 |
| **Help** | Open this page. | Ctrl+H |
| **Quit** | Close Nu. It asks first if you have unsaved work. | Ctrl+Q |

On a Mac, use Cmd instead of Ctrl.

## Modes

Each mode adds its own buttons, between **Save** and **Zoom-in**.

### Python 3

Write and run ordinary Python programs.

- **Run** (F5) runs your program. Its output, and anything it asks you to type
  in, appear in a pane below your code.
- **Debug** (F6) runs your program step by step. Click a line number first to
  add a *breakpoint* where it should pause.
- **REPL** (Ctrl+Shift+I) opens a prompt where you can type Python and see the
  result straight away.
- **Plotter** (Ctrl+Shift+P) draws a graph of numbers your program prints as
  tuples, e.g. `print((temperature, humidity))`.

### Graphical Debugger

This mode opens when you click **Debug**. While your program is paused, the
panel on the right shows its variables. Use **Step Over** (F10), **Step In**
(F11) and **Step Out** (Shift+F11) to move through your code, **Continue**
(F5) to run to the next breakpoint, and **Stop** (Shift+F5) to finish.

### Pygame Zero

Make games with [Pygame Zero](https://pygame-zero.readthedocs.io/).

- **Play** (F5) runs your game.
- **Images**, **Fonts**, **Sounds** and **Music** open the folders your game's
  pictures and sounds go in. Nu starts you off with a few examples.

### CircuitPython

Write code for microcontroller boards running
[CircuitPython](https://circuitpython.org/). Plug your board in and save your
code as `code.py` on the board's `CIRCUITPY` drive; it runs every time you
save.

- **Serial** (Ctrl+Shift+U) shows what your board prints, and lets you type
  to it. Press Ctrl+C there to get a REPL on the board.
- **Plotter** (Ctrl+Shift+P) graphs tuples your board prints.

## Where your files go

Nu saves your work in a folder called `mu_code` in your home folder (the name
comes from Mu, the editor Nu continues). It's what **Load** and **Save** show
first.

## Adding Python packages

Your programs run in their own Python environment, separate from Nu. To use a
package such as `requests`, click the **cog** in the bottom-right corner, open
**Third Party Packages**, put the package's name on its own line, and click
**OK**. The cog also has Nu's log, environment variables, and the language
setting.

## Plugins

Plugins add new modes to Nu. To try one, put its `.py` file (or folder) in
Nu's plugins folder and restart Nu:

| System | Plugins folder |
|---|---|
| Windows | `%LOCALAPPDATA%\python\mu\plugins` |
| macOS | `~/Library/Application Support/mu/plugins` |
| Linux | `~/.local/share/mu/plugins` |

Plugins are Python code that runs inside Nu, so only add ones you trust. If a
plugin has a problem, Nu tells you and keeps running. To write one, see
[Writing a Nu plugin](plugins.md).

## Something went wrong?

- **Nu crashed:** it shows the details of what went wrong. Click **Copy to
  clipboard** and paste them into a report (below). Nu never sends anything
  anywhere by itself.
- **Report a problem or suggest an idea** at
  [github.com/kovirlabs/nu/issues](https://github.com/kovirlabs/nu/issues).
- **Learn more:** the original Mu's
  [tutorials](https://codewith.mu/en/tutorials/1.2/) still apply to most of
  Nu, though Nu no longer has the micro:bit, ESP, Pico or web modes.
