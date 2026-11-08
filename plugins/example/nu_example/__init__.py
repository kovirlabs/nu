"""
A minimal example plugin for Nu: the template for writing your own.

It contributes one mode, "Example", with a single toolbar button that counts
the lines in the current tab. Everything it uses comes from `mu.plugin`, and
its icons are in its own `images` folder.
"""

import os

from mu.plugin import Mode, ModePlugin


class ExampleMode(Mode):
    """A mode with one button that reports the current tab's line count."""

    name = "Example"
    short_name = "example"  # stable id: used as a settings and session key
    description = "An example plugin mode. Copy it to write your own."
    # An image name: images/example-mode.svg (registered by ExamplePlugin).
    # Prefix your image names with your plugin's name, so they can't clash
    # with Nu's own images or another plugin's.
    icon = "example-mode"

    def actions(self):
        return [
            {
                # The action's name is also its icon (images/example-count.svg)
                # and its toolbar button's id, so keep it unique too.
                "name": "example-count",
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
    # One sentence for the Plugins tab: what the plugin adds.
    description = "An example plugin to copy when you write your own."
    # The plugin API version this was written against. Always a literal: Nu
    # compares it with the API it provides and skips the plugin if they clash.
    api_version = "0.4"
    mode = ExampleMode
    # The folder of images the mode uses, registered before the mode.
    images = os.path.join(os.path.dirname(__file__), "images")
