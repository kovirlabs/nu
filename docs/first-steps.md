# Suggested first steps

We love helpful, collaborative and friendly contributions!

If you'd like to ease into contributing to Nu, here are some things to try,
depending on your skills and interests. If your contribution changes code or
documentation, read [contributing](contributing.md) first, to learn what we
expect of a pull request.

## Reporting a problem

If you think you've found a problem, we want to hear about it. Issues are
tracked on GitHub at
[github.com/kovirlabs/nu/issues](https://github.com/kovirlabs/nu/issues);
you'll need a (free) GitHub account to
[open one](https://github.com/kovirlabs/nu/issues/new). Please tell us:

* What you were doing, with the steps needed to make it happen again.
* What you expected to happen, what happened instead, and why the difference
  matters.
* Which version of Nu (the log says it near the top of each start, e.g.
  `Starting Mu 2.0.0b3`; or the installer's name), and your operating system.
* Nu's log. Click the **cog** at the right of the status bar (or press
  Ctrl+Shift+D), open the **Current Log** tab, click in it, select everything
  with Ctrl+A, copy with Ctrl+C and paste it into the issue.
* If Nu crashed, the details it showed you: its crash window has a **Copy to
  clipboard** button. Nu never sends reports by itself.
* If it's about running a program or adding a package, what the **What Nu
  Ran** list on the Environment tab says (see
  [Your Python environment](environment.md#what-nu-ran)).

The more precise you are, the faster it can be fixed. "When I click this
button, it breaks" is hard to act on.

## Coding

1. Follow the [developer setup](setup.md): `uv sync --extra dev` gets you a
   working checkout, and `uv run python -m mu` runs it.
2. Read the [architecture overview](architecture.md) to learn where things
   live and why. The non-GUI logic is in `mu/logic.py`, the Qt code in
   `mu/interface/`, and every mode except Python 3 and the Debugger is a
   [plugin](plugins.md) under `plugins/`.
3. Run the [tests](tests.md) before you change anything, so you know they
   pass for you.

A gentle first change: the status bar shows a "message of the day" when Nu
starts. The messages are the `MOTD` list near the top of `mu/logic.py`; add
a better one (it needs to be short, friendly and translatable, so wrap it in
`_()` like the others).

Something bigger: pick an open
[issue](https://github.com/kovirlabs/nu/issues), say you're working on it,
and open a pull request with the fix and its tests. Or write a
[plugin](plugins.md): `plugins/example` is a template to copy.

## Translations

Nu uses Python's standard `gettext` tools to translate its interface. If you
speak a language Nu's translation is missing or out of date in, we'd love your
help: see [translations](translations.md).

## Documentation

These pages are the only documentation Nu has, for learners and teachers as
well as developers (see [the documentation site](docs-site.md)). If a page is
unclear, out of date or missing something you had to find out the hard way,
a pull request that fixes it is as welcome as a code change.

## User experience research

Our users are at the centre of everything we do. We have two sorts of user in
mind:

* Beginner programmers with little or no experience using a development
  environment.
* Those who support beginner programmers: teachers, club leaders, parents and
  other mentors.

When it comes to teaching and learning, sometimes you just have to do what the
experienced person says: the professional musician explaining to the beginner
how to hold an instrument "correctly", for example. There is some notion of
correctness that the experienced person understands is the best way to do
something.

This also applies to learning to write code: we need to find ways to introduce
the practice and conventions of programming in an effective manner. As Alan Kay
said of Papert:

> "He realized, 'Oh, we could take the real content out here as a version in
> the child's world that is still the real thing.' It's not a fake version of
> math. It's kind of like little league, or even T-ball. In sports they do
> this all the time. In music, they do it all the time. The idea is, you never
> let the child do something that isn't the real thing -- but you have to work
> your ass off to figure out what the real thing is in the context of the way
> their minds are working at that developmental level."
> -- [Alan Kay](https://www.fastcompany.com/40435064/what-alan-kay-thinks-about-the-iphone-and-technology-now)

How do we know what "the real thing" is in the context of a code editor for a
beginner programmer? That's where [user experience](user-experience.md) comes
in, and we would love contributions from developers, beginner programmers and
teachers to make sure Nu is an effective educational tool. If you teach with
Nu, telling us what worked and what didn't (in an issue) is research too.
