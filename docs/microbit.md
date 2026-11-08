# The BBC micro:bit

!!! warning "Early: needs testing on real boards"

    micro:bit mode is new in Nu and hasn't yet been tried on real micro:bits
    by Nu's maintainer. It's an **opt-in plugin** for now: it isn't in the
    downloadable installers yet, and you add it to a Nu you run from source
    with `uv sync --extra microbit` (or `--all-extras`). If something here
    doesn't match what your micro:bit does, please
    [tell us](https://github.com/kovirlabs/nu/issues).

The [BBC micro:bit](https://microbit.org/) is a small programmable board with
a grid of 25 lights, two buttons, sensors and a radio. Nu's **micro:bit mode**
lets you write [MicroPython](https://microbit-micropython.readthedocs.io/) for
it, put your program on it with one button, and talk to it while it runs.

It works with both versions of the micro:bit: the **V1** and the **V2** (the
one with a microphone, a speaker and a touch-sensitive logo).

## Getting started

1. Plug the micro:bit into the computer with a USB cable. (Some cables only
   charge: if nothing happens, try another.) A drive called **MICROBIT**
   appears, like a USB stick.
2. In Nu, click **Mode** and choose **BBC micro:bit**. Nu keeps your
   micro:bit programs in a `microbit` folder in your `mu_code` folder.
3. Write a program, for example:

    ```python
    from microbit import *

    display.scroll("Hello!")
    ```

4. Click **Flash**. After a few seconds the micro:bit runs your program.

As you type, Nu suggests what comes next: type `display.` and it lists what
the display can do. The suggestions cover the V2's extras too (sound, the
microphone, the logo, data logging); their descriptions end with
"(micro:bit V2)" so you know which ones a V1 can't do.

## The buttons

| Button | What it does |
|---|---|
| **Flash** (F3) | Puts the program in the current tab onto the micro:bit as `main.py`, and restarts the micro:bit so it runs. |
| **REPL** | Opens the micro:bit's MicroPython prompt in Nu, so you can type Python and the micro:bit runs it straight away. It also shows what your program `print`s. |
| **Plotter** | Draws a graph of numbers your program prints as tuples, e.g. `print((accelerometer.get_x(),))`. |

The REPL and the plotter use the micro:bit's USB connection, and so does
Flash. If the REPL or plotter is open when you click Flash, Nu closes it, puts
your program on the micro:bit, then opens it again.

## What Flash does

The status bar at the bottom of the window says what's happening at each step:

1. **Looking for the micro:bit.** Nu finds the MICROBIT drive and reads the
   `DETAILS.TXT` file on it, which says whether it's a V1 or a V2.
2. **Checking for MicroPython.** Nu asks the micro:bit whether MicroPython is
   running on it. A new micro:bit, or one that last ran a
   [MakeCode](https://makecode.microbit.org/) program, doesn't have it.
3. **Putting MicroPython on (only if needed).** Nu copies the right
   MicroPython for your micro:bit onto the MICROBIT drive. The light on the
   back of the micro:bit flashes, the drive disappears and comes back, and
   MicroPython starts. This takes about half a minute. **Don't unplug the
   micro:bit while it happens.**
4. **Copying your code.** Nu copies your program onto the micro:bit as
   `main.py` and restarts it. MicroPython runs `main.py` every time the
   micro:bit starts, even without a computer, from a battery pack.

Steps 3 and 4 are things you could do yourself in a terminal, and Nu shows the
commands under **What Nu ran** (the cog in the bottom-right corner → the Python
environment tab), for example:

```bash
cp micropython-microbit-v2.1.2.hex /media/you/MICROBIT/
mpremote connect /dev/ttyACM0 fs cp hello.py :main.py + reset
```

[mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) is
MicroPython's own tool for talking to boards; Nu uses it from the inside rather
than running it, but does exactly what that command does.

## Where MicroPython comes from

The first time Nu needs to put MicroPython on a micro:bit, it **downloads** the
official release for that version of the micro:bit:

| micro:bit | MicroPython | From |
|---|---|---|
| V2 | 2.1.2 | [micropython-microbit-v2 releases](https://github.com/microbit-foundation/micropython-microbit-v2/releases) |
| V1 | 1.1.1 | [bbcmicrobit/micropython releases](https://github.com/bbcmicrobit/micropython/releases) |

It checks the download's checksum (so a damaged or changed file is never put on
your micro:bit), and keeps it, so after the first time Flash works without the
internet.

### Offline (a classroom without internet)

If the computer can't download the file, Nu says which file it needs and which
folder to put it in. On a computer that is online:

1. Download the file for your micro:bit from the table above
   (`micropython-microbit-v2.1.2.hex` for a V2,
   `micropython-microbit-v1.1.1.hex` for a V1). It's on the release's page
   under **Assets**.
2. Copy it, with a USB stick for example, into the folder Nu named. That's
   the `microbit/firmware` folder in Nu's data folder:
    - Windows: `C:\Users\<you>\AppData\Local\python\mu\microbit\firmware`
    - macOS: `~/Library/Application Support/mu/microbit/firmware`
    - Linux: `~/.local/share/mu/microbit/firmware`
3. Click Flash again. Nu checks the file before using it.

Teachers can copy both files to every computer once, before the lesson.

## Putting MicroPython back on

Nu only puts MicroPython on when it isn't there. To put a fresh copy on
anyway (if the micro:bit is behaving oddly, or to update an older MicroPython,
which Nu mentions in the status bar after flashing), **hold Shift and click
Flash**. Nu asks first, then puts MicroPython on and then your program.

## When something goes wrong

**"Could not find an attached BBC micro:bit."**
: Check the cable is plugged in at both ends and carries data, wait a few
  seconds, and try again. Try another USB port.

**"Nu can't talk to the micro:bit."**
: Another program may be using the micro:bit's connection (a second copy of
  Nu, a browser tab using WebUSB, a serial terminal): close it. Then unplug the
  micro:bit, plug it back in, and try again.

**"Nu isn't allowed to use the micro:bit's serial connection."** (Linux)
: Your user needs to be in the group that can use serial ports. In a
  terminal, type `sudo usermod -a -G dialout $USER`, then log out and back in.

**"Nu can't find the micro:bit's MICROBIT drive."**
: Nu needs the drive to put MicroPython on. Wait for it to appear. On a Linux
  desktop that doesn't open USB drives by itself, open it in the file manager
  first. On a Chromebook, open the **Files** app, right-click **MICROBIT** and
  choose **Share with Linux**.

**"Your micro:bit is in maintenance mode."**
: The drive is called MAINTENANCE because the micro:bit was plugged in with
  its reset button held down. Unplug it and plug it back in without pressing
  anything.

**"Nu doesn't know this board."**
: The board isn't a micro:bit Nu knows about (it reads the board's number from
  `DETAILS.TXT`). A brand new micro:bit model may need a newer Nu.

**The micro:bit shows a sad face, or Flash stops part-way.**
: It was probably unplugged while MicroPython was being copied. Plug it back
  in, wait for the MICROBIT drive, and hold Shift and click Flash.

**"Your code is too big for the micro:bit."**
: The micro:bit has room for a few tens of kilobytes of code. Make the program
  shorter, or remove other files from the micro:bit.

Nu's log (the cog → the **Logs** tab) has the details of every step, which
help if you report a problem.

## Not yet

- A **Files** pane, to see, copy and delete the files on the micro:bit, as the
  old Mu had. It's planned (see the
  [plugin roadmap](plugins.md#roadmap-the-microbit-files-pane)).
- Flashing with [pyOCD](https://pyocd.io/) (faster, and works when the drive
  doesn't), and one "universal" MicroPython file for both V1 and V2.
- micro:bit mode in the installers, switched on by default, once it has been
  tested on real boards.
