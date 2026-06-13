# Packaging Mu

Our target users (beginner programmers and those who support them) may not be
confident with installing software, so obtaining and setting up Mu needs to be
as simple as possible — and producing the installers needs to be automatic, so
cutting a release doesn't depend on one volunteer's time.

Since **Phase 4** (see `TODO.md`) the native installers are built with
**[Briefcase](https://briefcase.readthedocs.io/)** (part of the BeeWare suite),
replacing the previous `pup` pipeline. A single definition in
`pyproject.toml`'s `[tool.briefcase]` drives all three platforms:

| OS | Format | CI runner |
|---|---|---|
| Windows | `.msi` | `windows-latest` |
| macOS | `.dmg` (ad-hoc signed) | `macos-13` (Intel) |
| Linux | `.AppImage` | `ubuntu-latest` |

## Building installers (Briefcase)

CI is the release path: `.github/workflows/build.yml` builds one OS per job and
uploads the installer as a downloadable artifact. **Trigger it from the GitHub
Actions tab** ("Build installers" → *Run workflow*), or it runs on a push to
`master` / a `v*` tag. Download the artifact for your OS from the run.

Locally (inside a pip-enabled virtualenv with the `package` extra,
`pip install -e ".[package]"`):

```
$ make win64     # 64-bit Windows MSI
$ make macos     # macOS .app/.dmg (ad-hoc signed)
$ make linux     # Linux AppImage
```

Each target fetches the offline baseline wheels and runs the Briefcase
create → build → package cycle (see `make.py`). The build is mostly self-driving
once the build tools are present (Briefcase fetches WiX for the Windows MSI on
demand).

### What ships inside the app

- The editor (`mu`) plus its third-party dependencies (PyQt6, etc.), installed
  into the bundle by Briefcase from `[tool.briefcase.app.mu].requires`.
- A pinned **`uv`** binary — it rides in via the PyPI `uv` wheel, and
  `find_uv()` locates it at runtime through `uv.find_uv_bin()` (no `PATH` or
  `MU_UV` needed in the packaged app).
- The **baseline wheels zip** (`mu/wheels/<version>.zip`, built by
  `python -m mu.wheels --package` before packaging), so the first-run
  `uv venv` sets up the learner's environment **offline**.

At first launch Mu creates the user's environment with
`uv venv --python <the bundled interpreter>`, so the packaged Python is reused
for the learner's code — no separate CPython download is required.

### Signing

CI builds are **unsigned** (macOS uses an ad-hoc signature). Users will see a
SmartScreen (Windows) or Gatekeeper (macOS) warning until code-signing secrets
(Authenticode / Apple notarization) are wired into `build.yml` — tracked as a
follow-up in `TODO.md` (Phase 4d).

!!! warning "The sections below are historical"
    Everything from "Python Package" down is **inherited from upstream Mu** and
    describes the **retired** toolchain (Appveyor, `pynsist`/NSIS, Travis, the
    `pup` builder, tkinter assets, `setup.py`). It is kept for reference while
    the docs are modernized and **does not reflect how this fork builds today** —
    see the Briefcase flow above. The legacy `pup` `make` targets survive as
    `win32`, `win64-pup`, `macos-pup`, `linux-pup`, and `linux-docker` until the
    Briefcase builds are confirmed on all three OSes (Phase 4e).

## Python Package

If you have Python 3.5 or later installed on Windows, OSX or 64-bit Linux and
you are familiar with Python's built-in packaging system, you can install Mu
into a virtual environment with `pip`:

```
$ pip install mu-editor
```

!!! note
    By design, `pip` will not create any shortcuts for applications that it
    installs.

    If you want to add a shortcut for Mu to your desktop/start menu you can
    use Martin O'Hanlon's amazingly useful
    [Shortcut tool](https://shortcut.readthedocs.io/en/latest/) like this:

        $ pip install shortcut
        $ shortcut mu

As per conventions, the `setup.py` file contains all the details used by
`pip` to install it. We use [twine](https://github.com/pypa/twine) to push
releases to PyPI and I (Nicholas - maintainer) simply use a Makefile to
automate this:

```
$ make publish-test
$ make publish-live
```

The `make publish-live` command is what updates PyPI. The
`make publish-test` command uses the test instance of PyPI so we can confirm
the release looks, behaves and works as expected before pushing to live.

## Raspberry Pi

Raspberry Pi OS (previously called Raspbian) is the official operating system
for the Raspberry Pi and features Mu as Recommended Software. Raspberry Pi OS
uses the Mu packages contributed to Debian by
[Nick Morrott](https://twitter.com/nickmorrott).

To install Mu on Raspberry Pi OS from the command line, type:

```
$ sudo apt install mu-editor
```

Alternatively, Mu can be installed from the Recommended Software menu in the
Programming section.

!!! warning
    Since Mu for Raspberry Pi OS is packaged by a third party, our latest
    releases may not be immediately available.

## Windows Installer

Packaging for Windows is essential for the widespread use of Mu since most
computers in schools run this operating system. Furthermore, feedback from
school network administrators tells us that they prefer installers since these
are easier to install "in bulk" to computing labs.

There are two versions of the installer: one for 32bit Windows and the other
for 64bit Windows. The 32bit version has been tested on Windows 7 and the 64bit
version has been tested on Windows 10. Support for anything other than Windows
10 is important, but a "best effort" affair. If you find you're having problems
please [submit a bug report](https://github.com/mu-editor/mu/issues/new).

The latest *unsigned* builds for Mu on Windows
[can be found here](http://mu-builds.s3-website.eu-west-2.amazonaws.com/?prefix=windows/).

Mu for Windows contains its own version of Python packaged in such a way that
makes it only usable within the context of Mu (Python's so-called 
[isolated mode](https://docs.python.org/3.4/whatsnew/3.4.html#whatsnew-isolated-mode)).
Of course, the version of Python in Mu will have as much or little
access to computing resources as the host operating system will allow.

Packaging is automated using the [Appveyor](https://www.appveyor.com/) cloud
based continuous integration solution for Windows. The 
[.appveyor.yml](https://github.com/mu-editor/mu/blob/master/.appveyor.yml)
file found in the root of Mu's repository, configures and describes this
process. You can see the history of such builds
[here](https://ci.appveyor.com/project/carlosperate/mu/history).

We use the [NSIS](http://nsis.sourceforge.net/Main%5FPage) tool to build the
installers. This process if coordinated by the amazing
[pynsist](https://pynsist.readthedocs.io/en/latest/) utility.

!!! note
    Pynsist is the creation of
    [Thomas Kluyver](https://twitter.com/takluyver), who has done an amazing
    job creating many useful tools and utilities for the wider Python
    community (for example, Thomas is also responsible for the Jupyter
    widget Mu uses for the REPL in Python 3 mode).

    On several occasions Thomas has volunteered his time to help Mu. Like
    Carlos, Thomas is another example of the invaluable efforts that go into
    making Mu. Once again, if you find Mu useful, please don't hesitate to
    thank Thomas via Twitter.

    Thank you Thomas!

The required configuration file for `pynsist` is automatically generated at
packaging time, under a temporary working directory.
The motive for that arises from the need to ensure that Mu's dependencies are
sourced from a single place, which is `setup.py`.
The `win_installer.py` script handles that,
runs `pynsist`,
moves the resulting installer executable to the `dist` directory,
and cleans up.
If you're interested in learning more,
the script includes comments with detailed notes
(also, check out the `pynsist`
[specification for configuration files](https://pynsist.readthedocs.io/en/latest/cfgfile.html)).

The automated builds are unsigned, so Windows will complain about the software
coming from an untrusted source. The official releases will be signed by
me (Nicholas Tollervey - the current maintainer) on my local machine using
a private key and uploaded to GitHub and associated with the relevant release.
[The instructions for cryptographically signing installers](https://pynsist.readthedocs.io/en/latest/faq.html#code-signing)
explain this process more fully
(the details of which are described
[by Mozilla](https://developer.mozilla.org.cach3.com/en-US/docs/Mozilla/Developer_guide/Build_Instructions/Signing_an_executable_with_Authenticode)).

Use the `make` command to build your own installers:

```
$ make win32
$ make win64
```

This will clean the repository before running the `win_installer.py` command
for the requested bitness.

Because Mu depends on the availability of tkinter, part of the build process is
to download the appropriate tkinter-related resources from
[Mu's tkinter assets repository](https://github.com/mu-editor/mu_tkinter).

If asked, the command for automatically installing Mu, system wide, should use
the following flags:

```
mu-editor_win64.exe /S /AllUsers
```

The `/S` flag tells the installer to work in "silent" mode (i.e. you won't
see the windows shown in the screenshots above) and the `/AllUsers` flag
makes Mu available to all users of the system (i.e. it's installed "system
wide").

## OSX App Installer

We use Travis to automate the building of the .app and .dmg installer (see the
`.travis` file in the root of Mu's GIT repository for the steps involved). 
This process is controlled by
[Briefcase (part of the BeeWare suite of tools](https://briefcase.readthedocs.io/en/latest/))
which piggy-backs onto the `setup.py` script to build the necessary assets.
To ensure Mu has Python 3 available for it to both run and use for evaluating
users' scripts, we have created a portable/embeddable Python runtime whose
automated build scripts can be found
[in this repository](https://github.com/mu-editor/mu_portable_python_macos).
This is the Python version used by Mu (not the one on the user's machine).

The end result of submitting a commit to Mu's master branch is an
automatically generated installable for OSX. These assets are un-signed, so OSX
will complain about Mu coming from an unknown developer. However, for full
releases we sign the .app with our Apple developer key (a manual process).

## Linux Packages

We don't automatically create packages for Linux distros. However, we liaise
with upstream developers to ensure that Mu finds its way into both Debian and
Fedora based distributions.

### Debian

Mu (and the MicroPython runtime) were packaged for Debian and Ubuntu by
[Nick Morrott](https://twitter.com/nickmorrott) and have been available to
install since the releases of Debian 10 "buster" and Ubuntu 19.04 "Disco Dingo".

To install Mu on Debian/Ubuntu from the command line, type:

```
$ sudo apt install mu-editor
```

!!! warning
    Since Mu for Debian/Ubuntu is packaged by a third party, our latest
    releases may not be immediately available.

### Fedora

Mu was packaged by [Kushal Das](https://twitter.com/kushaldas) for Fedora.
However this is an old version of Mu and, as with the Raspberry Pi version,
relies on a third party to package it so may lag behind the latest version.

!!! note
    Last, but not least, Kushal does a huge amount of work for both the
    Fedora and Python communities and is passionate about sustaining our
    Python community through education outreach. With people like Kushal
    putting in the time and effort to package tools like Mu and mentor
    beginner programmers who use Mu our community would flourish less. If you
    find Mu useful, please don't hesitate to thank Kushal via Twitter.

    Thank you Kushal.
