"""
A minimal example plugin for Nu: the template for writing your own.

It contributes one mode, "Example", with a single toolbar button that counts
the lines in the current tab. Everything it uses comes from `mu.plugin`.
"""

from mu.plugin import Mode, ModePlugin


class ExampleMode(Mode):
    """A mode with one button that reports the current tab's line count."""

    name = "Example"
    short_name = "example"  # stable id: used as a settings and session key
    description = "An example plugin mode. Copy it to write your own."
    icon = "python"  # a built-in icon name

    def actions(self):
        return [
            {
                # Until plugins can ship their own icons, `name` must be a
                # built-in icon name that doesn't clash with a core button.
                "name": "snippets",
                "display_name": "Count",
                "description": "Count the lines in the current tab.",
                "handler": self.count_lines,
                "shortcut": "F6",
            }
        ]

    def api(self):
        """Autocomplete/call tip entries: "name(args)\\nDocumentation"."""
        return []

    def count_lines(self, event=None):
        text = self.host.current_text()
        if text is None:
            self.host.show_message("There's no tab open to count.")
            return
        settings = self.host.settings(self.short_name)
        presses = settings.get("presses", 0) + 1
        settings.set("presses", presses)
        lines = len(text.splitlines())
        self.host.show_status("{} lines (count #{})".format(lines, presses))
        self.host.logger("example").info("Counted %d lines", lines)


class ExamplePlugin(ModePlugin):
    name = "Example"
    # The plugin API version this was written against. Always a literal: Nu
    # compares it with the API it provides and skips the plugin if they clash.
    api_version = "0.1"
    mode = ExampleMode
