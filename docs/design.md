# Design decisions

These pages record *why* things are the way they are: the decision, the
situation that led to it, and how it was implemented. Mu started the practice
(Tim Golden wrote the first ones), so the pages below are Mu's decisions,
with the links to Mu's pull requests and issues where they were discussed.
Where Nu has since changed the picture, each page ends with a **Nu today**
section; the original decision is kept as it was written, as history.

* [File reading and writing](design/file_reading_and_writing.md): how the
  editor decodes and encodes learners' files.
* [Line endings](design/line-endings.md): what the editor does with `\r\n`
  and `\n`, and the repository's own LF rule.
* [Runtime virtual environment](design/runtime_virtual_environment.md): why
  learners' programs run in an environment of their own (now made with uv).
* [Settings and sessions](design/settings-and-sessions.md): `settings.json`,
  `session.json` and `venv.json`, and what's in them.

Some of Nu's later decisions are recorded on the pages for the features
themselves: [plugins](plugins.md) (why plugins, versioning, trust),
[Your Python environment](environment.md) (a visible environment) and
[packaging](packaging.md) (the uv workspace, Briefcase).

## Writing a new one

When a change involves a non-obvious technical decision, add a page in
`docs/design/`, link it here and in `mkdocs.yml`'s nav, and use this shape:

```markdown
# Meaningful title

## Decision

A brief summary of what Nu does, given the context of the title.

## Background

As many paragraphs as needed to describe the situation that made the
decision necessary.

## Discussion and implementation

As many paragraphs as needed to explain the approach taken and how it was
implemented.

### Implemented via

* (Links to the pull requests or commits.)

### Discussion in

* (Links to the issues or other discussions.)
```
