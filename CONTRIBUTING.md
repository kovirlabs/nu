# Contributing to Nu

Hey! Many thanks for wanting to improve Nu, the maintained continuation of
the [Mu editor](https://github.com/mu-editor/mu). This guide is adapted from
Mu's.

Contributions are welcome without prejudice from *anyone* irrespective of
age, gender, religion, race or sexuality. If you're thinking, "but they don't
mean me", *then we especially mean YOU*. Good quality code and engagement
with respect, humour and intelligence wins every time.

* If you're from a background which isn't well-represented in most geeky
  groups, get involved - *we want to help you make a difference*.
* If you're from a background which *is* well-represented in most geeky
  groups, get involved - *we want your help making a difference*.
* If you're worried about not being technical enough, get involved - *your
  fresh perspective will be invaluable*.
* If you think you're an imposter, get involved.
* If your day job isn't code, get involved.
* This isn't a group of experts, just people. Get involved!
* We are interested in educational, social and technical problems. If you are
  too, get involved.
* This is a new community. *No-one knows what they are doing*, so, get involved.

We expect contributors to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

Check out our
[developer setup](https://kovirlabs.github.io/nu/setup/)
documentation (source: [`docs/setup.md`](docs/setup.md)) for instructions to
configure a working development environment for Nu. In short, with
[uv](https://docs.astral.sh/uv/):

```
uv sync --extra dev
uv run python -m mu
```

New to the project? The [first steps](https://kovirlabs.github.io/nu/first-steps/)
page suggests where to start, and how to report a problem well. Issues and
pull requests go to <https://github.com/kovirlabs/nu>.

Feedback may be given for contributions and, where necessary, changes will
be politely requested and discussed with the originating author. Respectful
yet robust argument is most welcome.

> [!WARNING]
> **Contributions are subject to the following caveats**: the contribution
> was created by the contributor who, by submitting the contribution, is
> confirming that they have the authority to submit the contribution and
> place it under the license as defined in the LICENSE file found within
> this repository (see the [LICENSE](LICENSE) file). If this is a significant contribution
> the contributor should add themselves to the AUTHORS file found in the
> root of Mu's repository, otherwise they agree, for the sake of convenience,
> that copyright passes exclusively to Nicholas H.Tollervey on behalf of the
> Mu project.

## Checklist

* If your contribution includes non-obvious technical decision making please
  make sure you document this in the
  [design decisions](docs/design.md)
  section.
* If it changes what learners or teachers see, update the pages for them in
  `docs/` ([Using Nu](docs/help.md), [Your Python environment](docs/environment.md),
  ...) in the same pull request, and add a line to [`CHANGES.md`](CHANGES.md).
* Your code should be commented in *plain English* (British spelling).
* If your contribution is for a major block of work and you've not done so
  already, add yourself to the AUTHORS file following the convention found
  therein.
* Include tests that cover every line of your change. Mu kept 100% test
  coverage and Nu is close to it; don't let it drop. See
  [tests](https://kovirlabs.github.io/nu/tests/).
* **Before submitting code ensure coding standards and test coverage by running**
  (formatting and lint with ruff, then the tests with coverage):

```
make check
```

  and, if you changed the docs, `uv run --no-sync mkdocs build --strict`.

* If in doubt, ask a question. The only stupid question is the one that's never asked.
* Most importantly, **Have fun!** :-)
