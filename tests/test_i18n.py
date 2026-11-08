"""
Tests for Nu's translations: the catalogues in mu/locale and mu/i18n.py.
"""

import builtins
import collections
import gettext
import importlib
import io
import os
import string
from unittest import mock

import pytest

import mu.i18n
from mu.interface.dialogs import LocaleWidget

LOCALE_DIR = mu.i18n.localedir
LOCALES = sorted(
    name
    for name in os.listdir(LOCALE_DIR)
    if os.path.isfile(os.path.join(LOCALE_DIR, name, "LC_MESSAGES", "mu.po"))
)


def _path(locale, extension):
    return os.path.join(LOCALE_DIR, locale, "LC_MESSAGES", "mu." + extension)


def _read_po(locale):
    """Parse a locale's mu.po with babel (the i18n extra), failing on errors."""
    pofile = pytest.importorskip("babel.messages.pofile")
    with open(_path(locale, "po"), "rb") as po_file:
        return pofile.read_po(po_file, locale=locale, abort_invalid=True)


def _compile(catalog):
    """What `make translate_done` would write for `catalog`, loaded."""
    mofile = pytest.importorskip("babel.messages.mofile")
    buffer = io.BytesIO()
    mofile.write_mo(buffer, catalog)
    buffer.seek(0)
    return gettext.GNUTranslations(buffer)


def _fields(text):
    """The replacement fields in a str.format() template, counted."""
    return collections.Counter(
        name for _, name, _, _ in string.Formatter().parse(text) if name is not None
    )


@pytest.fixture
def restore_gettext():
    """Put the test session's `_` (and mu.i18n's state) back afterwards."""
    original = builtins.__dict__.get("_")
    yield
    if original is None:
        builtins.__dict__.pop("_", None)
    else:
        builtins._ = original


def test_locales_found():
    """
    Guard the parametrised tests below against silently testing nothing.
    """
    assert "de_DE" in LOCALES
    assert len(LOCALES) >= 14


@pytest.mark.parametrize("locale", LOCALES)
def test_po_compiles(locale):
    """
    Every mu.po parses cleanly and compiles to a loadable catalogue.
    """
    translations = _compile(_read_po(locale))
    assert translations.info()["content-type"] == "text/plain; charset=utf-8"
    assert len(translations._catalog) > 1  # more than just the header


@pytest.mark.parametrize("locale", LOCALES)
def test_mo_in_sync_with_po(locale):
    """
    The committed mu.mo holds exactly what compiling mu.po gives, so a
    translation fix can't sit in a .po without reaching learners (or a stale
    binary ship with strings the .po no longer has). If this fails, run
    `make translate_done LANG=<locale>` and commit the mu.mo.
    """
    expected = _compile(_read_po(locale))
    with open(_path(locale, "mo"), "rb") as mo_file:
        committed = gettext.GNUTranslations(mo_file)
    assert committed._catalog == expected._catalog


@pytest.mark.parametrize("locale", LOCALES)
def test_translations_keep_placeholders(locale):
    """
    A reviewed translation uses the same {} fields as its English source:
    the app fills them with .format(), so a dropped or misnamed field would
    show the wrong value or raise an error.
    """
    mismatched = [
        message.id
        for message in _read_po(locale)
        if message.id
        and message.string
        and not message.fuzzy
        and _fields(message.id) != _fields(message.string)
    ]
    assert mismatched == []


def test_every_locale_has_a_picker_entry():
    """
    Each language Nu ships can be chosen in the admin dialog, and every
    language offered there ships (English is the source, not a catalogue).
    """
    offered = set(LocaleWidget.LANGUAGES.values()) - {"", "en"}
    assert offered == set(LOCALES)


def test_set_language_translates_renamed_string(restore_gettext):
    """
    Choosing German gives German for a string the Mu -> Nu rename touched.
    """
    mu.i18n.set_language("de_DE")
    assert _("Quit Nu.") == "Nu beenden."
    assert _("Nu was not able to open this file") == (
        "Nu konnte die Datei nicht öffnen"
    )
    # A heritage credit still says "Mu", and keeps its translation.
    assert _("Mu was created by Nicholas H.Tollervey.") == (
        "Mu wurde von Nicholas H.Tollervey erstellt."
    )


def test_system_locale_is_used(restore_gettext):
    """
    On import, mu.i18n uses the system's language (as Qt reports it).
    """
    system = mock.MagicMock()
    system.name.return_value = "de_DE"
    try:
        with mock.patch("PyQt6.QtCore.QLocale") as qlocale:
            qlocale.system.return_value = system
            importlib.reload(mu.i18n)
            assert mu.i18n.language_code == "de_DE"
            assert _("Quit Nu.") == "Nu beenden."
    finally:
        importlib.reload(mu.i18n)


def test_unknown_language_falls_back_to_english(restore_gettext):
    """
    A language with no catalogue leaves the English source strings.
    """
    mu.i18n.set_language("xx_XX")
    assert _("Quit Nu.") == "Quit Nu."
