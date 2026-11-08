"""
Inline script metadata (PEP 723) for the Run button.

A Python file can list the packages it needs in a comment block at the top::

    # /// script
    # dependencies = ["cowsay"]
    # ///

`uv run` reads that block, fetches the packages into a cached environment of
their own, and runs the program there. Nu's Run button does the same for a
file with such a block (see `PythonMode.run_script`); files without one run
exactly as before. This module is the GUI-free part: finding the block (with
the PEP's reference regular expression), reading it, and turning uv's error
text into a one-line hint for a beginner.

See https://peps.python.org/pep-0723/

Copyright (c) 2026 the Nu contributors (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import collections
import io
import re
import tokenize
import tomllib

#: The reference implementation's regular expression, from PEP 723.
REGEX = r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
#: An opening `script` line (to spot one that's never closed).
OPENING_REGEX = r"(?m)^# /// script$"
#: An empty block, which the reference regex misses (it needs a line of
#: content) but uv accepts.
EMPTY_REGEX = r"(?m)^# /// script\n# ///$"

#: A `# /// script` block: its TOML `content` and the 1-based `line` it
#: starts on.
ScriptBlock = collections.namedtuple("ScriptBlock", ["content", "line"])


class ScriptMetadataError(ValueError):
    """The file has a `# /// script` block, but it's malformed."""


def _normalise(text):
    """Use `\\n` line endings (files from Windows, or old Macs, too)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _line_of(text, offset):
    """The 1-based line number of `offset` in `text`."""
    return text.count("\n", 0, offset) + 1


def _comment_lines(text):
    """
    The 1-based numbers of the lines that start with a real comment (not,
    say, a line of a triple-quoted string), or None if `text` isn't Python
    the tokenizer can read.
    """
    lines = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT and token.start[1] == 0:
                lines.add(token.start[0])
    except (tokenize.TokenError, SyntaxError):
        return None
    return lines


def find_script_block(text):
    """
    Return the `ScriptBlock` in the Python source `text`, or None if it has
    none. Found with PEP 723's reference regex, but only where the block is
    made of real comments: one inside a string doesn't count (unless the
    file can't be tokenized, when the regex alone decides).

    Raise `ScriptMetadataError` for more than one `script` block, or for an
    opening `# /// script` line with no closing `# ///` (e.g. a line in
    between that doesn't start with `#`).
    """
    text = _normalise(text)
    comments = _comment_lines(text)

    def is_comment(offset):
        return comments is None or _line_of(text, offset) in comments

    blocks = [
        match
        for match in re.finditer(REGEX, text)
        if match.group("type") == "script" and is_comment(match.start())
    ]
    if len(blocks) > 1:
        raise ScriptMetadataError("There is more than one `# /// script` block.")
    if blocks:
        match = blocks[0]
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in match.group("content").splitlines(keepends=True)
        )
        return ScriptBlock(content, _line_of(text, match.start()))
    for match in re.finditer(EMPTY_REGEX, text):
        if is_comment(match.start()):
            return ScriptBlock("", _line_of(text, match.start()))
    for match in re.finditer(OPENING_REGEX, text):
        if is_comment(match.start()):
            raise ScriptMetadataError(
                "A `# /// script` line has no closing `# ///` line."
            )
    return None


def read_script_metadata(text):
    """
    Return the inline script metadata in `text` as a dict (e.g.
    ``{"dependencies": ["cowsay"]}``), or None if it has no block. Raise
    `ScriptMetadataError` if the block is malformed (see `find_script_block`)
    or isn't valid TOML.
    """
    block = find_script_block(text)
    if block is None:
        return None
    try:
        return tomllib.loads(block.content)
    except tomllib.TOMLDecodeError as exc:
        raise ScriptMetadataError("The `# /// script` block isn't valid TOML: %s" % exc)


def wants_uv_run(text):
    """
    True if Run should use `uv run` for the Python source `text`: it has a
    `# /// script` block — even a malformed one, so uv's own error (and
    `uv_run_hint`) can explain what's wrong rather than the program failing
    later on a missing import.
    """
    try:
        return find_script_block(text) is not None
    except ScriptMetadataError:
        return True


#: (text uv prints, the hint for it); the first match wins.
_HINTS = [
    (
        ("TOML parse error",),
        lambda: _(
            "Hint: the “# /// script” block at the top of this program isn't "
            "written correctly. Check its brackets, quotes and commas."
        ),
    ),
    (
        ("without a closing tag",),
        lambda: _(
            "Hint: every line of the “# /// script” block must start with "
            "“#”, and the block must end with a “# ///” line."
        ),
    ),
    (
        ("was not found in the package registry",),
        lambda: _(
            "Hint: a package in this program's “dependencies” wasn't found on "
            "PyPI. Check its spelling."
        ),
    ),
    (
        (
            "Failed to fetch",
            "error sending request",
            "network was disabled",
            "dns error",
            "tcp connect error",
            "Request failed after",
        ),
        lambda: _(
            "Hint: uv couldn't download the packages this program needs. Are "
            "you connected to the internet? (It only needs to download them "
            "once.)"
        ),
    ),
    (
        ("incompatible with the script's Python requirement",),
        lambda: _(
            "Hint: this program's “requires-python” asks for a different "
            "Python than your environment has, so it might not work."
        ),
    ),
    (
        ("No interpreter found",),
        lambda: _(
            "Hint: Nu couldn't find your environment's Python. Please "
            "restart Nu so it can repair your environment."
        ),
    ),
]


def uv_run_hint(output):
    """
    A one-line, beginner-readable hint about uv's own error (or warning) in
    the `output` of `uv run`, or None if there's nothing of uv's to explain
    (the program's own errors are the program's).
    """
    for needles, hint in _HINTS:
        if any(needle in output for needle in needles):
            return hint()
    return None
