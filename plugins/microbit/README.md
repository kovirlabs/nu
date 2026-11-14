# nu-microbit

The **BBC micro:bit** mode for [Nu](https://github.com/kovirlabs/nu): write
MicroPython for the [micro:bit](https://microbit.org/) (V1 and V2), put it on
the board with one button, and use the board's REPL and plotter. The learner's
guide is [docs/microbit.md](../../docs/microbit.md).

It replaces upstream Mu's micro:bit mode, which Nu dropped because its tools
(`uflash`, `microfs`) were frozen. This plugin uses maintained tooling only:

- **[mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html)**
  (MicroPython's own tool, used through its Python API) copies the code onto
  the board as `main.py` and resets it.
- **DAPLink drag-and-drop**: MicroPython itself is flashed by copying its
  `.hex` onto the board's `MICROBIT` drive. No drivers or extra packages.
- **Firmware is pinned and fetched, never vendored**: the official V1 1.1.1 and
  V2 2.1.2 releases, by URL + SHA-256 (`nu_microbit/firmware.py`), downloaded
  into Nu's data folder the first time they're needed.

Status: **opt-in, not yet validated on hardware.** It's a member of Nu's uv
workspace but not one of Nu's dependencies: install it with Nu's `microbit`
extra (`uv sync --extra microbit`, or `--all-extras`). It becomes a
default-enabled bundled plugin (Phase 6c in `TODO.md`) once the checklist
below has passed on real boards.

- **Entry point:** `mu.plugins` → `microbit = "nu_microbit:MicrobitPlugin"`;
  the mode's id is `microbit`, as in Mu, so old sessions keep working.
- **Plugin API:** 0.6 (`Host.log_command`, `Host.current_device`,
  `Host.data_dir`; `Host.add_pane`, `remove_pane` and `open_file` for the
  Files pane).
- **Dependencies:** `mpremote` (and pyserial, which Nu has). No
  `learner-env` extra: the code runs on the board.
- **Tests:** `plugins/microbit/tests/`, run with Nu's suite. Everything that
  touches a board is faked there; the checklist below is the real thing.

## How it's built

| Module | What it does |
|---|---|
| `board.py` | Board IDs (9900/9901 → V1, 9903–9906 → V2), `DETAILS.TXT`, finding the `MICROBIT` drive and the serial port, asking the REPL for its banner. GUI-free. |
| `firmware.py` | The pinned releases; a checked local copy, or a download. GUI-free. |
| `flash.py` | The flash state machine (below). GUI-free; all I/O injected. |
| `files.py` | The Files pane's jobs: list, copy each way, delete, through mpremote. GUI-free; all I/O injected. |
| `files_pane.py` | The Files pane widget: the board's files and the learner's `microbit` folder, side by side. |
| `worker.py` | Runs a flash or files job on a `QThread`, reporting back through signals. |
| `mode.py` | `MicrobitMode`: buttons, board detection, wiring. |
| `api/` | Autocomplete stubs for micro:bit MicroPython 2.x (and 1.x). |

```
FIND_DRIVE → READ_DETAILS → FIND_PORT → PROBE ─(MicroPython running)──────────────┐
                                          └─(not, or Shift+Flash) → FIRMWARE      │
                       → COPY_HEX → WAIT_REMOUNT → WAIT_REPL ──────────────→ COPY_MAIN → DONE
```

Each step shows a status line; downloading the firmware, copying it to the
drive and the mpremote copy are logged as the commands a learner could type
(see **What Nu Ran** in the admin dialog).

## Hardware validation checklist (≈15 minutes)

You need: a **V2** micro:bit and a **V1** micro:bit (if you have one), a data
USB cable, Nu from this branch with the extra (`uv sync --all-extras`), and
internet for the first flash. Start Nu with `uv run python -m mu`, switch to
**BBC micro:bit** mode, and keep the admin dialog's **Current Log** handy
(the cog, bottom-right). For each step, note what you saw if it differs.

**Setup checks (1 min)**

1. With the micro:bit plugged in, the device selector (bottom-right) shows
   **BBC micro:bit V2** (or V1). Paste the board's `DETAILS.TXT` (on the
   MICROBIT drive) into your notes: the parser was written against DAPLink's
   documented format, not a real file from your boards.
2. The Plugins tab lists **BBC micro:bit** as *On*, *Installed package*.

**A. Fresh V2, no MicroPython (3 min).** Flash a MakeCode program (or the
out-of-box demo) onto the V2 first, so it has no MicroPython.

3. Open a new tab, type `from microbit import *` and `display.scroll("hi")`,
   save it as `hello.py`, click **Flash**.
4. The status bar shows, in order: Looking for the micro:bit… → Checking for
   MicroPython… → Downloading MicroPython for the micro:bit V2… N% (first
   time only) → Copying MicroPython onto the micro:bit… N% → Waiting for the
   micro:bit to restart… → Waiting for MicroPython to start… → Copying your
   code… → **Done! Your code is on the micro:bit.** The board scrolls "hi".
5. The admin dialog's **What Nu Ran** tab shows a `curl …` download, a
   `cp …hex …/MICROBIT/`, and `mpremote connect <port> fs cp …/hello.py
   :main.py + reset`.
6. The firmware is in Nu's data folder under `microbit/firmware/`.
7. Time from click to "Done": ______ s (the remount timeouts are 30 s + 60 s;
   the REPL wait 20 s; tell us if any was too short or long).

**B. V2 that already has MicroPython (2 min)**

8. Change the text to `display.scroll("again")`, click Flash: it goes straight
   from "Checking for MicroPython" to "Copying your code" (no drive copy, a
   few seconds) and the board scrolls "again".
9. Unplug the board and plug it back in: it runs the program again (it's
   `main.py`).
10. Hold **Shift** and click Flash: Nu asks "Put MicroPython back on your
    micro:bit?"; OK re-flashes MicroPython and then the code.

**C. REPL then Flash (2 min)**

11. Click **REPL**: the MicroPython banner and `>>>` appear. Type
    `display.show(Image.HEART)`: the heart shows.
12. With the REPL still open, click **Flash**. The status bar says Nu closed
    the REPL; the flash works; the REPL **reopens** afterwards and shows the
    program's output. Flash, REPL and Plotter are greyed out while flashing.
13. Click **Plotter**, flash a program that does
    `while True: print((accelerometer.get_x(),)); sleep(100)`: tilting the
    board moves the graph.

**D. Unplug mid-flash (2 min)**

14. Make the V2 lose MicroPython again (MakeCode, or hold Shift + Flash), click
    Flash and **unplug the board while "Copying MicroPython…" shows**. Nu says
    "Copying MicroPython onto the micro:bit didn't finish." (or "didn't come
    back"), and Nu stays usable.
15. Plug it back in (it may show a sad face, or nothing): Flash again
    recovers it. If it comes back as **MAINTENANCE**, Flash says so; unplug
    and replug.

**G. Files (3 min)** — on the V2 with MicroPython and `hello.py` flashed:

16. Click **Files** (F4): the REPL/plotter close if open and their buttons go
    grey; the pane lists `main.py` (with its size on hover) on the left and
    your `microbit` folder on the right. The board's program stops (the
    display goes blank): the pane says to press reset to run it again.
17. Select `hello.py` on the right, **Copy to micro:bit ▶**: it appears on the
    left. Again: Nu asks before replacing it.
18. Flash a program that writes a file (`with open("log.txt", "w") as f:
    f.write("hi")`), press reset, then **Refresh**: `log.txt` is listed.
    Double-click it: it's copied into your folder; open it with **Open**.
19. Select `log.txt` on the left, **Delete from micro:bit**: Nu asks, then
    it's gone. **What Nu Ran** shows `mpremote connect <port> fs ls`, `fs cp`
    and `fs rm`.
20. With the pane open, click Flash: the pane greys, then lists the files
    again; the REPL stays off until you close the pane (Files again).
21. On a V1, step 16: the list appears (it uses `os.listdir`/`os.size`, not
    mpremote's `fs ls`, which needs `os.ilistdir`).

**E. V1 (3 min)** — repeat 3–4 and 8 on a V1: the status bar says
"…micro:bit V1", the V1 firmware (1.1.1) is downloaded, and `hello.py` runs.
Note whether mpremote's copy works on the V1 (its MicroPython is older and
has no raw-paste mode; mpremote should fall back by itself).

**F. Offline (1 min, optional)** — delete `microbit/firmware/` from Nu's data
folder, disconnect from the network, flash a board without MicroPython: Nu
names the file, the URL and the folder. Put the file there (from step 6's
copy) and Flash works.

**Other platforms**, if you can: on Windows check the drive (`E:\`) and COM
port are found and the command shows `copy …hex E:\`; on macOS
`/Volumes/MICROBIT` and `/dev/cu.usbmodem…`; on Linux without the `dialout`
group, the "isn't allowed" message.

Report anything that differs, with the Current Log, on the PR.
