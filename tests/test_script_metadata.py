"""
Tests for the GUI-free PEP 723 inline script metadata helpers
(mu/script_metadata.py).
"""

import pytest

from mu import script_metadata as SM


COWSAY = """\
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "cowsay",
# ]
# ///

import cowsay
cowsay.cow("Hello")
"""


#
# find_script_block
#
def test_no_block():
    assert SM.find_script_block("print('hello')\n") is None
    assert SM.wants_uv_run("print('hello')\n") is False


def test_empty_file():
    assert SM.find_script_block("") is None


def test_block():
    block = SM.find_script_block(COWSAY)
    assert block.line == 1
    assert block.content == (
        'requires-python = ">=3.11"\ndependencies = [\n  "cowsay",\n]\n'
    )
    assert SM.wants_uv_run(COWSAY) is True


def test_block_after_other_code():
    """The block can be anywhere at the top level, not just the first line."""
    text = "#!/usr/bin/env python\n\n" + COWSAY
    assert SM.find_script_block(text).line == 3


def test_empty_block():
    """An empty block is still a block (uv runs it in a bare environment)."""
    block = SM.find_script_block("# /// script\n# ///\nprint(1)\n")
    assert block is not None
    assert block.content == ""


def test_bare_hash_lines_inside_block():
    """A line of just `#` is an empty line of TOML (per the PEP's regex)."""
    text = "# /// script\n# dependencies = []\n#\n# ///\n"
    assert SM.find_script_block(text).content == "dependencies = []\n\n"


def test_windows_line_endings():
    text = COWSAY.replace("\n", "\r\n")
    block = SM.find_script_block(text)
    assert block is not None
    assert "cowsay" in block.content
    assert "\r" not in block.content


def test_old_mac_line_endings():
    assert SM.find_script_block(COWSAY.replace("\n", "\r")) is not None


def test_closing_line_without_trailing_newline():
    assert SM.find_script_block("# /// script\n# dependencies = []\n# ///") is not None


def test_block_inside_a_string_is_not_a_block():
    """The PEP's regex matches text inside a triple-quoted string too, but
    that's not a comment block, so it doesn't count."""
    text = 's = """\n# /// script\n# dependencies = ["cowsay"]\n# ///\n"""\nprint(s)\n'
    assert SM.find_script_block(text) is None
    assert SM.wants_uv_run(text) is False


def test_block_inside_a_string_in_a_file_that_does_not_tokenize():
    """If the file isn't valid Python (it won't run anyway), fall back to the
    PEP's regex alone."""
    text = COWSAY + "print((\n"
    assert SM.find_script_block(text) is not None


def test_other_block_types_are_ignored():
    text = "# /// pyproject\n# [tool.x]\n# ///\nprint(1)\n"
    assert SM.find_script_block(text) is None


def test_indented_block_is_not_a_block():
    text = "if True:\n    # /// script\n    # dependencies = []\n    # ///\n    pass\n"
    assert SM.find_script_block(text) is None


def test_two_script_blocks_is_an_error():
    """PEP 723: more than one `script` block is an error."""
    text = COWSAY + "\n" + COWSAY
    with pytest.raises(SM.ScriptMetadataError):
        SM.find_script_block(text)
    assert SM.wants_uv_run(text) is True  # uv explains the problem.


def test_opening_line_without_closing_line_is_an_error():
    text = "# /// script\n# dependencies = ['cowsay']\nimport cowsay\n"
    with pytest.raises(SM.ScriptMetadataError):
        SM.find_script_block(text)
    assert SM.wants_uv_run(text) is True


def test_a_line_without_hash_breaks_the_block():
    """Every line in the block must start with `#`; a blank line ends it, so
    the opening line has no closing line."""
    text = "# /// script\n\n# dependencies = []\n# ///\n"
    with pytest.raises(SM.ScriptMetadataError):
        SM.find_script_block(text)


def test_unclosed_opening_line_inside_a_string_is_fine():
    text = 'HELP = """\n# /// script\n"""\nprint(HELP)\n'
    assert SM.find_script_block(text) is None


#
# read_script_metadata
#
def test_read_script_metadata():
    assert SM.read_script_metadata(COWSAY) == {
        "requires-python": ">=3.11",
        "dependencies": ["cowsay"],
    }


def test_read_script_metadata_no_block():
    assert SM.read_script_metadata("print(1)\n") is None


def test_read_script_metadata_malformed_toml():
    """A block whose TOML is broken is malformed, but still a block: uv
    reports the mistake when it runs."""
    text = "# /// script\n# dependencies = [\n# ///\nprint(1)\n"
    with pytest.raises(SM.ScriptMetadataError):
        SM.read_script_metadata(text)
    assert SM.wants_uv_run(text) is True


#
# uv_run_hint: a one-line, beginner-readable hint for uv's error text
#
@pytest.mark.parametrize(
    "output, words",
    [
        (
            "error: Request failed after 3 retries in 7.5s\n"
            "  cause: Failed to fetch: https://pypi.org/simple/cowsay/\n"
            "  cause: tcp connect error\n",
            "internet",
        ),
        (
            "error: No solution found when resolving script dependencies\n"
            "  cause: Because cowsay was not found in the cache and you require "
            "cowsay, we can conclude that your requirements are unsatisfiable.\n\n"
            "hint: Packages were unavailable because the network was disabled.",
            "internet",
        ),
        ("error: dns error: failed to lookup address information", "internet"),
        (
            "error: No solution found when resolving script dependencies\n"
            "  cause: Because cowsayzzz was not found in the package registry and "
            "you require cowsayzzz, ...",
            "spelling",
        ),
        (
            "warning: The requested interpreter resolved to Python 3.11.15, which "
            "is incompatible with the script's Python requirement: `>=3.13`",
            "requires-python",
        ),
        ("error: TOML parse error at line 1, column 17", "brackets"),
        (
            "error: An opening tag (`# /// script`) was found without a closing "
            "tag (`# ///`).",
            "# ///",
        ),
        ("error: No interpreter found at path `/x/bin/python`", "restart"),
    ],
)
def test_uv_run_hint(output, words):
    hint = SM.uv_run_hint(output)
    assert hint.startswith("Hint: ")
    assert "\n" not in hint
    assert words in hint


def test_uv_run_hint_none_for_ordinary_output():
    assert SM.uv_run_hint("Installed 1 package in 5ms\nHello\n") is None
    # A program's own error isn't uv's to explain.
    assert SM.uv_run_hint("Traceback ...\nNameError: name 'x' is not defined") is None
