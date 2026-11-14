# Publishing to PyPI

How Nu gets to [PyPI](https://pypi.org). Nothing is published yet: the
workflow is in place, and the one-time setup below is what's left. As of
2026-11-09, the names `nu-editor`, `nu-circuitpython`, `nu-pygamezero`,
`nu-microbit` and `nu-example-plugin` were all unclaimed.

## What gets published

| Package | When | Why |
|---|---|---|
| `nu-pygamezero`, `nu-circuitpython` | With every release that changes them | `nu-editor` depends on them, so they must be on PyPI first |
| `nu-editor` | Every release | Gives `pip install nu-editor` / `pipx install nu-editor` as an install route, and plugin authors develop against it |
| `nu-microbit` | Once it is promoted to a bundled plugin (Phase 6c) | Doubles as the worked example for community plugin authors |

`nu-example-plugin` is a copy-me template; it isn't published.

The installers don't need PyPI: they carry the bundled plugins as wheels, so a
first launch stays offline. PyPI is for `pip` installs and for the Plugins
tab's **Add a plugin…**.

!!! warning "Don't hold names with empty packages"
    PyPI's name policy (PEP 541) treats empty placeholder packages as name
    squatting, and PyPI can hand those names to someone else. Publish each
    plugin only once it has real code.

## One-time setup: Trusted Publishing

Trusted Publishing lets PyPI accept uploads straight from a GitHub Actions
workflow, so there is no API token to store or leak.

1. **pypi.org** (2FA required): Account → **Publishing** → **Add a new pending
   publisher** → GitHub. Do this **three times**, once per project name
   (`nu-editor`, `nu-pygamezero`, `nu-circuitpython`), each with:
    - Owner: `kovirlabs`
    - Repository: `nu`
    - Workflow filename: `publish.yml`
    - Environment: `pypi`

    A *pending* publisher creates the project on its first upload.
2. **test.pypi.org** (a separate site with its own account): add the same
   three pending publishers, with environment `testpypi`. This is what a dry
   run uploads to.
3. **GitHub:** repo **Settings → Environments**: create `pypi` and add
   yourself as a required reviewer, so no upload goes out until you approve
   it. Create `testpypi` too (no reviewer needed).

When another plugin is ready to publish, add a pending publisher for its
project name (same owner, repo, workflow and environment) and add its folder
to the build step in `publish.yml`, and to `BUNDLED_PLUGINS` in `make.py` and
the `Makefile`.

## The workflow

`.github/workflows/publish.yml` builds the sdist and wheel of `nu-editor` and
of each bundled plugin (the same builds as `make dist`), runs `twine check`,
and uploads the plugins and then `nu-editor`. A plugin version the index
already has is skipped; `nu-editor`'s version must be new.

- **A release tag** (`vX.Y.Z`) uploads to PyPI, after checking that the tag
  matches the version in `mu/__init__.py`. The run waits for your approval in
  the `pypi` environment.
- **A manual run** (Actions → *Publish to PyPI* → *Run workflow*) uploads to
  TestPyPI by default, or to PyPI if you choose it.

Do a TestPyPI run before the first real release: it exercises the whole path,
and it hasn't been run yet.

## Releasing

Pushing a `vX.Y.Z` tag runs `build.yml`, which builds the installers and
creates the GitHub Release, and `publish.yml`, which uploads to PyPI once you
approve it. Then check the result in a fresh venv:

```
python -m venv /tmp/nu-check && /tmp/nu-check/bin/pip install nu-editor
/tmp/nu-check/bin/nu-editor
```

To check a TestPyPI upload the same way, let pip find Nu's dependencies on
PyPI:

```
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ nu-editor
```

!!! danger "An uploaded version can never be reused"
    Once a version is uploaded, that number is taken for good, even if you
    delete the release. That holds on TestPyPI too, so a second dry run of
    the same version fails at `nu-editor`. This matches the numeric-only
    policy: ship any fix as the next patch.

## Fallback: manual upload with a token

Create an API token (PyPI → Account → API tokens), then run
`make publish-live` (or `make publish-test` for TestPyPI). It runs
`make check`, builds everything and uploads in the same order as the workflow.

Use `__token__` as the username and the token as the password. Once the
project exists, switch to a token scoped to just this project.

## Note

The author name and `kovirlabs@kovir.org` from `pyproject.toml` appear
publicly on the PyPI page.
