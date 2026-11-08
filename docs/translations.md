# Translating Nu

Nu is used by beginner programmers all over the world, and many of them are
learning to code before they are comfortable reading English. Translating
Nu's user interface into your language is one of the most useful ways to help
them, and you don't need to be a programmer to do it.

You can contribute in three ways:

* **Review and complete an existing translation.** Every language below has
  messages still showing in English, and some marked *needs review*.
* **Improve an existing translation** that reads awkwardly or is wrong.
* **Add a new language.**

All of it happens in one file per language, `mu/locale/<code>/LC_MESSAGES/mu.po`,
which pairs each English message with its translation. Nu uses the standard
[gettext](https://docs.python.org/3/library/gettext.html) system, so you can
edit that file with a friendly tool such as [Poedit](https://poedit.net/), or
with any plain text editor.

If you are not a technical user, or anything in this guide is unclear, please
[open an issue](https://github.com/kovirlabs/nu/issues/new) saying which
language you'd like to help with. We'll help you get set up, or take your
translations and add them ourselves. We welcome translations from everyone!

## Current status

<!-- Regenerate with `make translate_status` after `make translate_begin`. -->

As of November 2026, Nu has 314 messages to translate:

| Language | In English | Code | Translated | Needs review | Untranslated |
| --- | --- | --- | ---: | ---: | ---: |
| Deutsch (Deutschland) | German (Germany) | `de_DE` | 191 (61%) | 20 | 103 |
| español | Spanish | `es` | 191 (61%) | 20 | 103 |
| français | French | `fr` | 188 (60%) | 21 | 105 |
| 日本語 | Japanese | `ja` | 202 (64%) | 16 | 96 |
| Nederlands | Dutch | `nl` | 213 (68%) | 18 | 83 |
| polski | Polish | `pl` | 190 (61%) | 20 | 104 |
| português (Brasil) | Portuguese (Brazil) | `pt_BR` | 214 (68%) | 17 | 83 |
| português (Portugal) | Portuguese (Portugal) | `pt_PT` | 212 (68%) | 18 | 84 |
| русский (Россия) | Russian (Russia) | `ru_RU` | 211 (67%) | 19 | 84 |
| slovenčina (Slovensko) | Slovak (Slovakia) | `sk_SK` | 200 (64%) | 17 | 97 |
| svenska | Swedish | `sv` | 189 (60%) | 22 | 103 |
| українська (Україна) | Ukrainian (Ukraine) | `uk_UA` | 193 (61%) | 36 | 85 |
| Tiếng Việt | Vietnamese | `vi` | 191 (61%) | 20 | 103 |
| 中文 (简体, 中国) | Chinese (Simplified, China) | `zh_CN` | 210 (67%) | 19 | 85 |

* **Translated** messages appear in your language.
* **Needs review** messages (marked `fuzzy` in the file, and highlighted by
  Poedit) were matched to a similar older message, and its translation was
  copied in as a starting point. Nu doesn't trust a guess, so these still
  appear in English until someone checks the translation, corrects it, and
  removes the `fuzzy` mark.
* **Untranslated** messages appear in English. Most are recent additions: the
  Environment and Plugins tabs of the administration dialog, the list of
  commands Nu has run, and the hints for programs that list their own
  packages.

### About the name "Nu"

Nu continues the [Mu editor](https://github.com/mu-editor/mu), and the editor's
own name changed from "Mu" to "Nu". Please write **Nu** wherever the English
says Nu, adapted to your language the way you would any name. Where the English
still says "Mu" (for example "Mu was created by Nicholas H.Tollervey."), it
means the original project, so keep "Mu" there.

Messages whose only change was the new name were updated automatically where
the translation wrote the name as "Mu". Where a translation adapted the name
(the Ukrainian translation writes "М'ю", and Swedish uses "Mus" for "Mu's"),
those messages are waiting for review, so a native speaker can choose the
right form of "Nu".

## How to translate

You'll need [a development environment](setup.md) first. With
[uv](https://docs.astral.sh/uv/), from the root of your copy of the repository:

```
uv sync --extra dev
```

The commands below are written as `uv run python make.py …`, which works on
Linux, macOS and Windows. On Linux and macOS, with the environment activated
(`source .venv/bin/activate`), you can use `make …` instead: for example
`make translate_begin LANG=xx_XX`.

In each command, replace `xx_XX` with your language's code from the table
above, such as `de_DE` or `ja`. Always give the code explicitly: `LANG` is
also the name of your system's language setting, so leaving it out can pick up
the wrong value.

### 1. Bring your language's `mu.po` up to date

```
uv run python make.py translate_begin LANG=xx_XX
```

This collects every message from Nu (including its bundled CircuitPython and
Pygame Zero plugins, which share Nu's translations) and merges any new or
changed ones into `mu/locale/xx_XX/LC_MESSAGES/mu.po`. If the language doesn't
exist yet, the file is created.

### 2. Translate

Open `mu.po` in [Poedit](https://poedit.net/) or a text editor, and fill in or
correct the translations. Some tips:

* Keep anything in curly brackets, such as `{}` or `{0}`, exactly as it is:
  Nu replaces it with a file name, a number and so on. You can move it to
  where it fits in your sentence. Keep `<strong>`-style tags and `\n` (a new
  line) too.
* When you've checked a *needs review* message, remove its `fuzzy` mark (in
  Poedit, toggle "Needs work"), otherwise Nu will keep showing it in English.
* Nu's users are often young beginners. Friendly, plain words are better than
  technical ones.

### 3. See your translation in Nu

```
uv run python make.py translate_test LANG=xx_XX
```

This compiles your translation and starts Nu in your language. If you've
chosen a language in Nu's administration dialog (the cog in the bottom-right
corner, then **Select Language**), that choice wins, so set it back to
"Automatically detect" while you test. Quit Nu, and go back to step 2 as often
as you need.

To see how far a translation has got, run:

```
uv run python make.py translate_status
```

### 4. Send us your work

Steps 1 to 3 change two files in `mu/locale/xx_XX/LC_MESSAGES/`:

* `mu.po`, the translations themselves, which you edited.
* `mu.mo`, a compiled copy that Nu reads when it runs.

Commit **both** files and
[create a pull request](https://github.com/kovirlabs/nu/pulls). If you've
changed `mu.po` since you last ran step 3, compile it again first with
`uv run python make.py translate_done LANG=xx_XX`: Nu's tests check that
`mu.mo` matches `mu.po`, and that translations keep their `{}` placeholders.
If git or pull requests are new to you, open an issue and attach your `mu.po`
instead. That's fine!

### Adding a new language

Step 1 creates the new language's `mu.po`. Use the code your language goes by
on computers, such as `it` for Italian or `pt_BR` for Brazilian Portuguese. To
let people choose it in Nu, add it to `LANGUAGES` in the `LocaleWidget` class
in `mu/interface/dialogs.py`, labelled with the language's name in that
language (for example `"Italiano": "it"`). A test checks that every language
in `mu/locale` is listed there.

Thank you!

## Notes for developers

* Only strings wrapped in `_()` are translated, and they must be plain string
  literals (adjacent literals and `+` between literals are fine): babel can't
  extract an f-string or a variable. The messages are collected from `mu/` and
  the bundled plugin packages (`_TRANSLATE_PLUGIN_PACKAGES` in `make.py`),
  skipping the generated API stubs.
* The `mu/locale/messages.pot` template that `translate_begin` writes is
  generated, not committed (it's in `.gitignore`, and `make clean` removes
  it).
* After changing user-facing strings, bring every catalogue up to date by
  running `translate_begin` for each locale, then `translate_done` for each,
  and commit the `.po` and `.mo` files, so translators start from the current
  messages.
* `utils/recover_renamed_translations.py` carried the existing translations
  across the "Mu" to "Nu" rename. It's kept as a record of how that was done,
  and as a starting point if Nu is ever renamed again.
