"""
Recover translations for strings whose only change was the app's rename.

Nu's user-facing name used to be "Mu". Renaming it changed every gettext
msgid that mentioned the app ("Mu Administration" -> "Nu Administration"),
so after `make translate_begin` those entries come back fuzzy, and a fuzzy
entry is ignored at runtime: the learner sees English.

This script repairs only the entries where that rename is the *whole* story,
by applying the same rename to the existing translation. For each active
message in a locale's mu.po it:

1. Reverses the rename on the msgid (whole-word "Nu" -> "Mu") and looks the
   result up in the catalogue as it was *before* the update (read from git,
   see --before). No exact old msgid, no recovery. The new entry is usually
   fuzzy (babel matched it to the old one), but a very short one such as
   "Nu" falls below babel's similarity cutoff and arrives untranslated
   instead; both are handled the same way.
2. Skips the entry if it is already translated (not fuzzy), if the msgid
   still contains a whole-word "Mu" as well (a heritage credit mixed with
   the new name: which "Mu" in the translation to change would be a guess),
   if the old entry was itself fuzzy (it was never a reviewed translation),
   or if it was untranslated.
3. Looks for the name written literally as "Mu" in the old translation. A
   "Mu" counts only when it is not glued to other letters or digits of a
   cased script (Latin, Cyrillic, ...), so the Japanese "Muを" or Chinese
   "改变Mu的" count, but a declined form like the Swedish genitive "Mus" or a
   transliteration like the Ukrainian "М'ю" does not. If there is no such
   "Mu", the entry stays fuzzy: English is a better fallback than a guess.
4. Otherwise replaces every such "Mu" with "Nu" and clears the fuzzy flag.

Anything else that is fuzzy stays fuzzy, and nothing is ever translated.

Only the recovered entries' flag and msgstr lines are rewritten in the .po
text (serialised the way `pybabel update` does; renaming keeps the length, so
nothing rewraps). Everything else is left byte for byte, and the result is
re-parsed and checked, so the diff holds exactly the recovered entries.

Usage (from the repository root, after `pybabel update`)::

    python utils/recover_renamed_translations.py --before <git-rev> [-v]

where <git-rev> is a commit whose catalogues predate the update.
"""

import argparse
import glob
import io
import os
import re
import subprocess
import sys
import unicodedata

from babel.messages.pofile import normalize, read_po

LOCALE_DIR = os.path.join("mu", "locale")
OLD_NAME = "Mu"
NEW_NAME = "Nu"
# Unicode categories that join with "Mu" into one word: cased letters,
# digits and the underscore. Uncased letters (Lo: Chinese, Japanese kana)
# and punctuation are boundaries.
_JOINING_CATEGORIES = {"Lu", "Ll", "Lt", "Nd"}
# The line width `pybabel update` wraps at (its default).
PO_WIDTH = 76


def _joins(char):
    return char == "_" or unicodedata.category(char) in _JOINING_CATEGORIES


def name_spans(text, name=OLD_NAME):
    """Return the (start, end) spans where `name` stands alone in `text`."""
    spans = []
    for match in re.finditer(re.escape(name), text):
        start, end = match.span()
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        if (not before or not _joins(before)) and (not after or not _joins(after)):
            spans.append((start, end))
    return spans


def rename(text, old=OLD_NAME, new=NEW_NAME):
    """Replace every standalone `old` with `new` in `text`."""
    for start, end in reversed(name_spans(text, old)):
        text = text[:start] + new + text[end:]
    return text


def _whole_word(name):
    return re.compile(r"\b{}\b".format(name))


def plan(before, after):
    """
    Decide what to do with each renamed entry of one locale.

    `before` and `after` are babel catalogues: the locale before and after
    `pybabel update`. Returns (recover, skipped): `recover` maps a msgid to
    its new msgstr; `skipped` lists (msgid, reason) for renamed entries
    that stay as they are.
    """
    old_messages = {m.id: m for m in before if m.id}
    recover, skipped = {}, []
    for message in after:
        msgid = message.id
        if not msgid or not isinstance(msgid, str):
            continue
        if not _whole_word(NEW_NAME).search(msgid):
            continue
        old_id = _whole_word(NEW_NAME).sub(OLD_NAME, msgid)
        old = old_messages.get(old_id)
        if old is None:
            continue  # a genuinely new string, not a rename
        if message.string and not message.fuzzy:
            skipped.append((msgid, "already translated"))
        elif _whole_word(OLD_NAME).search(msgid):
            skipped.append((msgid, "also keeps a heritage 'Mu'"))
        elif not old.string:
            skipped.append((msgid, "was untranslated"))
        elif old.fuzzy:
            skipped.append((msgid, "was already fuzzy"))
        elif not name_spans(old.string):
            skipped.append((msgid, "translation doesn't write the name as 'Mu'"))
        else:
            recover[msgid] = rename(old.string)
    return recover, skipped


def _block_msgid(block):
    """The msgid of one .po entry block, or None for the header/obsolete."""
    catalog = read_po(io.StringIO(block))
    ids = [m.id for m in catalog if m.id]
    return ids[0] if ids else None


def apply(text, recover):
    """Return `text` (a .po file) with the `recover` entries rewritten."""
    blocks = text.split("\n\n")
    done = set()
    for index, block in enumerate(blocks):
        if "\nmsgstr" not in "\n" + block or block.lstrip().startswith("#~"):
            continue
        msgid = _block_msgid(block)
        if msgid not in recover:
            continue
        out = []
        for line in block.split("\n"):
            if line.startswith("msgstr"):
                break  # the msgstr runs to the end of the block
            if line.startswith("#,"):
                flags = [f.strip() for f in line[2:].split(",")]
                flags = [f for f in flags if f != "fuzzy"]
                if flags:
                    out.append("#, " + ", ".join(flags))
                continue
            out.append(line)
        # Serialise exactly as `pybabel update` does. Renaming keeps the
        # length, so a translation that was already there wraps the same.
        out.append("msgstr " + normalize(recover[msgid], width=PO_WIDTH))
        blocks[index] = "\n".join(out)
        done.add(msgid)
    missing = set(recover) - done
    if missing:
        raise RuntimeError("Entries not found in the file: {!r}".format(missing))
    return "\n\n".join(blocks)


def check(original, updated, recover):
    """Assert `updated` differs from `original` exactly by `recover`."""
    old = {m.id: m for m in read_po(io.StringIO(original)) if m.id}
    new = {m.id: m for m in read_po(io.StringIO(updated)) if m.id}
    assert old.keys() == new.keys()
    for msgid, message in new.items():
        before = old[msgid]
        if msgid in recover:
            assert message.string == recover[msgid], msgid
            assert not message.fuzzy, msgid
            assert message.flags == before.flags - {"fuzzy"}, msgid
        else:
            assert message.string == before.string, msgid
            assert message.flags == before.flags, msgid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--before",
        required=True,
        help="git revision whose catalogues predate the pybabel update",
    )
    parser.add_argument("locales", nargs="*", help="default: all of them")
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show each decision"
    )
    args = parser.parse_args(argv)

    paths = sorted(glob.glob(os.path.join(LOCALE_DIR, "*", "LC_MESSAGES", "mu.po")))
    if args.locales:
        paths = [p for p in paths if p.split(os.sep)[-3] in args.locales]
    print("| Locale | Recovered | Renamed, left fuzzy |")
    print("| --- | ---: | ---: |")
    for path in paths:
        locale = path.split(os.sep)[-3]
        git_path = path.replace(os.sep, "/")
        old_bytes = subprocess.run(
            ["git", "show", "{}:{}".format(args.before, git_path)],
            capture_output=True,
            check=True,
        ).stdout
        with open(path, encoding="utf-8", newline="") as po_file:
            text = po_file.read()
        before = read_po(io.BytesIO(old_bytes))
        after = read_po(io.StringIO(text))
        recover, skipped = plan(before, after)
        updated = apply(text, recover)
        check(text, updated, recover)
        if not args.dry_run:
            with open(path, "w", encoding="utf-8", newline="") as po_file:
                po_file.write(updated)
        left_fuzzy = sum(1 for _, why in skipped if why != "was untranslated")
        print("| {} | {} | {} |".format(locale, len(recover), left_fuzzy))
        if args.verbose:
            old_strings = {m.id: m.string for m in before if m.id}
            for msgid, msgstr in recover.items():
                old_id = _whole_word(NEW_NAME).sub(OLD_NAME, msgid)
                print("    +", repr(old_strings[old_id]), "->", repr(msgstr))
            for msgid, why in skipped:
                print("    -", repr(msgid[:50]), "--", why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
