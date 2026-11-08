# nu-pygamezero

The **Pygame Zero** mode for [Nu](https://github.com/kovirlabs/nu): write games
with [Pygame Zero](https://pygame-zero.readthedocs.io/) and play them with one
button. Images, fonts, sounds and music buttons open the folders your game loads
its assets from.

This is one of Nu's *bundled* plugins: it ships with Nu and is switched on by
default. It's built only on Nu's public plugin API (`mu.plugin`, see
[Writing a Nu plugin](../../docs/plugins.md)), so it's also a worked example of
a bigger plugin than `plugins/example`.

- **Entry point:** `mu.plugins` → `pygamezero = "nu_pygamezero:PygameZeroPlugin"`.
  The mode's id is `pygamezero`, as it was when the mode was built into Nu, so
  saved sessions keep working.
- **Learner's environment:** the `learner-env` extra (`pgzero`, `pygame`) is
  what Nu installs where the learner's games run.
- **Tests:** `plugins/pygamezero/tests/`, run with Nu's test suite.
