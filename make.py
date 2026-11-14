#!python3
import os
import sys
import fnmatch
import re
import shutil
import subprocess

PYTEST = "pytest"
RUFF = "ruff"
# Paths ruff lints and formats. Excludes (the API stubs, docs) are
# configured in pyproject.toml's [tool.ruff].
RUFF_TARGETS = [
    "make.py",
    "run.py",
    "conftest.py",
    "mu",
    "package",
    "plugins",
    "tests",
    "utils",
]
PYGETTEXT = os.path.join(sys.base_prefix, "tools", "i18n", "pygettext.py")

INCLUDE_PATTERNS = {"*.py"}
EXCLUDE_PATTERNS = {
    "build/*",
    "docs/*",
    "mu/modes/api/*",
    "utils/*",
}
_exported = {}


def _walk(start_from=".", include_patterns=None, exclude_patterns=None, recurse=True):
    if include_patterns:
        _include_patterns = set(os.path.normpath(p) for p in include_patterns)
    else:
        _include_patterns = set()
    if exclude_patterns:
        _exclude_patterns = set(os.path.normpath(p) for p in exclude_patterns)
    else:
        _exclude_patterns = set()

    for dirpath, dirnames, filenames in os.walk(start_from):
        for filename in filenames:
            filepath = os.path.normpath(os.path.join(dirpath, filename))

            if not any(
                fnmatch.fnmatch(filepath, pattern) for pattern in _include_patterns
            ):
                continue

            if any(fnmatch.fnmatch(filepath, pattern) for pattern in _exclude_patterns):
                continue

            yield filepath

        if not recurse:
            break


def _rmtree(dirpath, cascade_errors=False):
    try:
        shutil.rmtree(dirpath)
    except OSError:
        if cascade_errors:
            raise


def _rmfiles(start_from, pattern):
    """Remove files from a directory and its descendants

    Starting from `start_from` directory and working downwards,
    remove all files which match `pattern`, eg *.pyc
    """
    for filepath in _walk(start_from, {pattern}):
        os.remove(filepath)


def export(function):
    """Decorator to tag certain functions as exported, meaning
    that they show up as a command, with arguments, when this
    file is run.
    """
    _exported[function.__name__] = function
    return function


@export
def test(*pytest_args):
    """Run the test suite

    Call py.test to run the test suite with additional args.
    The subprocess runner will raise an exception if py.test exits
    with a failure value. This forces things to stop if tests fail.
    """
    print("\ntest")
    os.environ["LANG"] = "en_GB.utf8"
    return subprocess.run([sys.executable, "-m", PYTEST] + list(pytest_args)).returncode


@export
def coverage():
    """View a report on test coverage

    Call py.test with coverage turned on
    """
    print("\ncoverage")
    os.environ["LANG"] = "en_GB.utf8"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            PYTEST,
            "-v",
            "--cov-config",
            "pyproject.toml",
            "--cov-report",
            "term-missing",
            "--cov=mu",
            # The bundled plugins (their tests are omitted in pyproject.toml).
            "--cov=plugins",
            "tests/",
            "plugins/",
        ]
    ).returncode


@export
def lint(*ruff_args):
    """Run the ruff code checker."""
    print("\nlint")
    return subprocess.run(
        [sys.executable, "-m", RUFF, "check", *RUFF_TARGETS, *ruff_args]
    ).returncode


@export
def tidy():
    """Reformat code with the 'ruff' formatter."""
    clean()
    print("\nTidy")
    return subprocess.run(
        [sys.executable, "-m", RUFF, "format", *RUFF_TARGETS]
    ).returncode


@export
def format():
    """Check code formatting with 'ruff' (makes no changes)."""
    clean()
    print("\nformat")
    return subprocess.run(
        [sys.executable, "-m", RUFF, "format", "--check", *RUFF_TARGETS]
    ).returncode


@export
def check():
    """Run all the checkers and tests"""
    print("\nCheck")
    funcs = [clean, format, lint, coverage]
    for func in funcs:
        return_code = func()
        if return_code != 0:
            return return_code
    return 0


@export
def clean():
    """Reset the project and remove auto-generated assets"""
    print("\nClean")
    _rmtree("build")
    _rmtree("dist")
    _rmtree(".eggs")
    _rmtree("site")  # MkDocs build output
    _rmtree(".pytest_cache")
    _rmtree("lib")
    # TODO: recursive __pycache__ directories
    _rmfiles(".", ".coverage")
    _rmfiles(".", "*.egg-info")
    _rmfiles(".", "*.pyc")
    _rmfiles("mu/locale", "*.pot")
    _rmfiles("mu/wheels", "*.zip")
    return 0


def _translate_lang(lang):
    """Returns `value` from `lang` expected to be like 'LANG=value'."""
    match = re.search(r"^LANG=(.*)$", lang)
    if not match:
        raise RuntimeError("Need LANG=xx_XX argument.")
    value = match.group(1)
    if not value:
        raise RuntimeError("Need LANG=xx_XX argument.")
    return value


_MU_LOCALE_DIRNAME = os.path.join("mu", "locale")
_MESSAGES_POT_FILENAME = os.path.join(_MU_LOCALE_DIRNAME, "messages.pot")


@export
def translate_begin(lang=""):
    """Create/update a mu.po file for translation."""
    lang = _translate_lang(lang)
    result = _translate_extract()
    if result != 0:
        raise RuntimeError("Failed creating the messages catalog file.")

    mu_po_filename = os.path.join(
        _MU_LOCALE_DIRNAME,
        lang,
        "LC_MESSAGES",
        "mu.po",
    )
    update = os.path.exists(mu_po_filename)
    cmd = [
        "pybabel",
        "update" if update else "init",
        "-i",
        _MESSAGES_POT_FILENAME,
        "-o",
        mu_po_filename,
        "--locale={locale}".format(locale=lang),
    ]
    if update:
        # Don't keep translations of strings Nu no longer has (#~ entries):
        # git keeps the history, see utils/recover_renamed_translations.py.
        cmd.append("--ignore-obsolete")
    result = subprocess.run(cmd).returncode

    print(
        "{action} {mu_po_filename}.".format(
            action="Updated" if update else "Created",
            mu_po_filename=repr(mu_po_filename),
        )
    )
    print("Review its translation strings and finalize with 'make translate_done'.")

    return result


_TRANSLATE_IGNORE_DIRNAMES = {
    os.path.join("mu", "modes", "api"),
}
# Bundled plugins use Nu's own message catalog, so their packages are
# extracted too (but not their API stubs or tests).
_TRANSLATE_PLUGIN_PACKAGES = [
    os.path.join("plugins", "circuitpython", "nu_circuitpython"),
    os.path.join("plugins", "pygamezero", "nu_pygamezero"),
    os.path.join("plugins", "microbit", "nu_microbit"),
]


def _translate_ignore(dirname):
    """Return True if `dirname` files should be excluded from translation."""
    if os.path.basename(dirname) == "api":
        return True  # generated API stubs (mu/modes/api, plugins' api)
    return any(dirname.startswith(dn) for dn in _TRANSLATE_IGNORE_DIRNAMES)


def _translate_filenames():
    """Returns a sorted list of filenames with translatable strings."""
    py_filenames = []
    for top in ["mu"] + _TRANSLATE_PLUGIN_PACKAGES:
        for dirname, _, filenames in os.walk(top):
            if _translate_ignore(dirname):
                continue
            py_filenames.extend(
                os.path.join(dirname, fn) for fn in filenames if fn.endswith(".py")
            )
    return sorted(py_filenames)


def _translate_extract():
    """Creates the message catalog template messages.pot file."""
    cmd = [
        "pybabel",
        "extract",
        "-o",
        _MESSAGES_POT_FILENAME,
        *_translate_filenames(),
    ]
    return subprocess.run(cmd).returncode


@export
def translate_done(lang=""):
    """Compile translation strings in mu.po to mu.mo file."""
    lang = _translate_lang(lang)

    lc_messages_dirname = os.path.join(
        _MU_LOCALE_DIRNAME,
        lang,
        "LC_MESSAGES",
    )
    mu_po_filename = os.path.join(lc_messages_dirname, "mu.po")
    mu_mo_filename = os.path.join(lc_messages_dirname, "mu.mo")
    cmd = [
        "pybabel",
        "compile",
        "-i",
        mu_po_filename,
        "-o",
        mu_mo_filename,
        "--locale={locale}".format(locale=lang),
    ]
    return subprocess.run(cmd).returncode


@export
def translate_status():
    """Print a Markdown table of how complete each translation is."""
    from babel import Locale
    from babel.messages.pofile import read_po

    print("| Language | In English | Code | Translated | Needs review | Untranslated |")
    print("| --- | --- | --- | ---: | ---: | ---: |")
    for lang in sorted(os.listdir(_MU_LOCALE_DIRNAME)):
        mu_po_filename = os.path.join(_MU_LOCALE_DIRNAME, lang, "LC_MESSAGES", "mu.po")
        if not os.path.isfile(mu_po_filename):
            continue
        with open(mu_po_filename, "rb") as po_file:
            messages = [m for m in read_po(po_file) if m.id]
        fuzzy = sum(1 for m in messages if m.fuzzy)
        translated = sum(1 for m in messages if m.string and not m.fuzzy)
        untranslated = len(messages) - fuzzy - translated
        locale = Locale.parse(lang)
        print(
            "| {} | {} | `{}` | {} ({:.0%}) | {} | {} |".format(
                locale.get_display_name(lang),
                locale.get_display_name("en"),
                lang,
                translated,
                translated / len(messages),
                fuzzy,
                untranslated,
            )
        )
    return 0


@export
def translate_test(lang=""):
    """Run translate_done and launch Nu in the given LANG."""
    result = translate_done(lang)
    if result != 0:
        raise RuntimeError("Failed compiling the mu.po file.")

    local_env = dict(os.environ)
    local_env["LANG"] = _translate_lang(lang)
    return subprocess.run([sys.executable, "-m", "mu"], env=local_env).returncode


@export
def run():
    """Run Nu from within a virtual environment"""
    clean()
    if not os.environ.get("VIRTUAL_ENV"):
        raise RuntimeError("Cannot run Nu; your Python virtualenv is not activated")
    return subprocess.run([sys.executable, "-m", "mu"]).returncode


# The plugins nu-editor depends on (and so bundles), built and published with
# it. They go up to PyPI first: nu-editor's wheel requires them. The opt-in
# plugins/microbit and the plugins/example template aren't published.
BUNDLED_PLUGINS = ["plugins/pygamezero", "plugins/circuitpython"]


def _build():
    """
    Build the sdist and wheel of nu-editor and of each bundled plugin into
    dist/. Return the first non-zero exit code, or 0.
    """
    for project in [".", *BUNDLED_PLUGINS]:
        return_code = subprocess.run(
            [sys.executable, "-m", "build", "--outdir", "dist", project]
        ).returncode
        if return_code != 0:
            return return_code
    return 0


@export
def dist():
    """Build nu-editor and its bundled plugins (sdists and wheels) in dist/"""
    if check() != 0:
        raise RuntimeError("Check failed")
    print("Checks pass; good to package")
    return _build()


def _publish(*repository):
    """
    Build everything, then upload the bundled plugins to PyPI (or the
    `repository` given as twine options) before nu-editor, which depends on
    them. A plugin version that's already there (it didn't change this
    release) is skipped; nu-editor's must be new.
    """
    return_code = dist()
    if return_code != 0:
        return return_code
    print("Packaging complete; upload to PyPI")
    twine = [sys.executable, "-m", "twine", "upload", *repository]
    plugins = [
        os.path.join("dist", _dist_name(plugin) + "-*") for plugin in BUNDLED_PLUGINS
    ]
    return_code = subprocess.run([*twine, "--skip-existing", *plugins]).returncode
    if return_code != 0:
        return return_code
    return subprocess.run([*twine, os.path.join("dist", "nu_editor-*")]).returncode


def _dist_name(plugin):
    """The file-name prefix of a bundled plugin's dists: nu_<folder name>."""
    return "nu_" + os.path.basename(plugin)


@export
def publish_test():
    """Upload nu-editor and its bundled plugins to the test PyPI"""
    return _publish("-r", "test")


@export
def publish_live():
    """Upload nu-editor and its bundled plugins to PyPI"""
    return _publish()


#
# Briefcase-driven installers (Phase 4d, see TODO.md). These mirror
# .github/workflows/build.yml so local and CI builds stay in step; CI is the
# release path, these are for local/dev convenience.
#
def _briefcase(platform, fmt=None, *package_args):
    """Build a native installer for `platform` with Briefcase.

    Fetches the offline baseline wheels, then runs the Briefcase
    create/build/package cycle. `fmt` is the output format (e.g. "appimage");
    `package_args` are passed to `briefcase package` (e.g. "--adhoc-sign").
    """
    print("\nFetching baseline wheels")
    subprocess.check_call([sys.executable, "-m", "mu.wheels", "--package"])
    _build_plugin_wheels()
    fmt_args = [fmt] if fmt else []
    for step in ("create", "build", "package"):
        cmd = [sys.executable, "-m", "briefcase", step, platform, *fmt_args]
        if step == "package":
            cmd.extend(package_args)
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)


#: Where Briefcase's pip finds the bundled plugins' wheels: the folder named
#: by `requirement_installer_args` in pyproject.toml.
PLUGIN_WHEELS_DIR = os.path.join("build", "plugin-wheels")


def _build_plugin_wheels():
    """
    Build a wheel of each bundled plugin from the checkout for Briefcase to
    install into the app (nu-editor's dependencies name them, and they
    needn't be on PyPI). Wheels left from an earlier build are removed, so
    that pip can't pick a stale one.
    """
    print("\nBuilding the bundled plugins' wheels")
    shutil.rmtree(PLUGIN_WHEELS_DIR, ignore_errors=True)
    for plugin in BUNDLED_PLUGINS:
        subprocess.check_call(
            [sys.executable, "-m", "build", "--wheel", "--outdir", PLUGIN_WHEELS_DIR]
            + [plugin]
        )


@export
def win64():
    """Build a 64-bit Windows MSI installer (Briefcase)"""
    _briefcase("windows")


@export
def macos():
    """Build a macOS .app/.dmg (Briefcase, ad-hoc signed)"""
    _briefcase("macOS", None, "--adhoc-sign")


@export
def linux():
    """Build a Linux AppImage (Briefcase)"""
    _briefcase("linux", "appimage")


@export
def docs():
    """Build the docs with MkDocs"""
    return subprocess.run([sys.executable, "-m", "mkdocs", "build"]).returncode


@export
def help():
    """Display all commands with their description in alphabetical order"""
    module_doc = sys.modules["__main__"].__doc__ or "check"
    print(module_doc + "\n" + "=" * len(module_doc) + "\n")

    for command, function in sorted(_exported.items()):
        doc = function.__doc__
        if doc:
            first_line = doc.splitlines()[0]
        else:
            first_line = ""
        print("make {} - {}".format(command, first_line))


def main(command="help", *args):
    """Dispatch on command name, passing all remaining parameters to the
    module-level function.
    """
    try:
        function = _exported[command]
    except KeyError:
        raise RuntimeError("No such command: %s" % command)
    else:
        return function(*args)


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
