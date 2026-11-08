# nu-example-plugin

The smallest useful Nu plugin. It adds an **Example** mode, with its own
icons, and one button that counts the lines in the current tab and remembers
how many times it has been pressed.

Use it as the template for your own plugin:

1. Copy this directory and rename `nu_example` and the project `name`.
2. Point the `mu.plugins` entry point in `pyproject.toml` at your `Plugin`
   subclass.
3. Rename the images in `nu_example/images/`, keeping your plugin's name as a
   prefix so they can't clash with Nu's or another plugin's, and use those
   names for the mode's `icon` and the actions' `name`s.
4. List any packages your mode needs in the learner's environment under the
   `learner-env` extra.
5. Import only from `mu.plugin`. Everything else in `mu` is internal and can
   change between releases.

For a bigger worked example, see `plugins/pygamezero`.

See [Writing a Nu plugin](../../docs/plugins.md) for the full API.
