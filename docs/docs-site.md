# The documentation site

Nu has no website of its own beyond these pages. They're published at
[kovirlabs.github.io/nu](https://kovirlabs.github.io/nu/) with GitHub Pages,
and serve both kinds of reader:

- **Learners and teachers:** [Using Nu](help.md) (what Nu's **Help** button
  opens), [Your Python environment](environment.md), [The BBC
  micro:bit](microbit.md) and the managing part of [Plugins](plugins.md#managing-plugins).
- **Developers:** everything else, from [developer setup](setup.md) to the
  generated [API reference](api.md).

!!! note
    Mu had a separate website, codewith.mu, with tutorials and how-to guides,
    built with Jekyll from its own repository. Nu doesn't: what learners need
    from Nu lives here, next to the code it describes, so it changes in the
    same pull request as the feature.

## How it's built

The pages are Markdown files in `docs/`, built with
[MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. `mkdocs.yml`
at the repository root holds the site settings and the navigation (`nav:`):
a page that isn't listed there is still built, but nobody will find it.

The [API reference](api.md) is generated from the docstrings in `mu/` and in
the bundled plugins, by [mkdocstrings](https://mkdocstrings.github.io/). Each
`::: module.name` line in `api.md` becomes that module's documentation;
`mkdocs.yml` tells it where to import the plugins from
(`plugins/circuitpython`, `plugins/pygamezero`, `plugins/microbit`).

The tools come with the `docs` extra (part of `dev`):

```
uv sync --extra dev
make docs           # build into site/ (python -m mkdocs build)
make docs-serve     # preview at http://127.0.0.1:8000, rebuilding as you edit
```

Before you open a pull request that touches the docs, build them strictly,
so a broken link or anchor fails the build instead of only warning:

```
uv run --no-sync mkdocs build --strict
```

## How it's published

`.github/workflows/docs.yml` runs on every push to `master` that changes
`docs/`, `mkdocs.yml`, `mu/` or `plugins/` (the API reference comes from the
code), and can be run by hand. It installs Nu, its three workspace plugins
and the `docs` extra, then runs `mkdocs gh-deploy --force`, which builds the
site and pushes it to the `gh-pages` branch. GitHub Pages serves that branch.
Pull requests don't publish anything.

## Writing for it

- **Match the reader.** Pages for learners and teachers are plain and short,
  and say what to click. Developer pages are precise: name the module, the
  setting, the command.
- **Check against the code.** Don't describe what Nu used to do, or what it
  might do. If you're not sure something still exists, look.
- **Nu or Mu?** Write "Nu" for this app. Write "Mu" where you mean the
  original editor, its history or its authors; that credit stays.
- **Links:** link between pages with relative Markdown links
  (`[plugins](plugins.md#managing-plugins)`), so `--strict` checks them.
  Nu's own code links to two pages, `help/` and `plugins/`
  (`HELP_URL` and `PLUGINS_HELP_URL` in `mu/logic.py`): don't rename those.
- **Images** go in `docs/` next to the pages. If an image isn't ours, say
  where it came from in [Copyright & image credits](copyright.md).
