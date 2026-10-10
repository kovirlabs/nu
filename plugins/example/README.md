# nu-example-plugin

The smallest useful Nu plugin. It adds an **Example** mode with one button
that counts the lines in the current tab, and remembers how many times it has
been pressed.

Use it as the template for your own plugin:

1. Copy this directory and rename `nu_example` and the project `name`.
2. Point the `mu.plugins` entry point in `pyproject.toml` at your `Plugin`
   subclass.
3. Import only from `mu.plugin`. Everything else in `mu` is internal and can
   change between releases.

See [Writing a Nu plugin](../../docs/plugins.md) for the full API.
