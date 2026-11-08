"""
The Pygame Zero mode for Nu.

Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import shutil

from mu.plugin import Mode

from .api import PYGAMEZERO_APIS

#: Demo images and sounds the Pygame Zero tutorials use, copied into the
#: learner's workspace (assets/images -> images/, assets/sounds -> sounds/).
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
#: The folders Pygame Zero loads a game's assets from, next to the game.
ASSET_TYPES = ("images", "fonts", "sounds", "music")


class PyGameZeroMode(Mode):
    """
    Represents the functionality required by the PyGameZero mode.
    """

    name = _("Pygame Zero")
    short_name = "pygamezero"
    description = _("Make games with Pygame Zero.")
    icon = "pygamezero"
    # Games run in the learner's environment, which has pgzero installed (the
    # plugin's learner-env extra).
    uses_user_environment = True
    #: True while a game started by the Play button is running.
    running = False
    builtins = [
        "clock",
        "music",
        "Actor",
        "keyboard",
        "animate",
        "Rect",
        "ZRect",
        "images",
        "sounds",
        "mouse",
        "keys",
        "keymods",
        "exit",
        "screen",
    ]

    def actions(self):
        """
        Return an ordered list of actions provided by this module. An action
        is a name (also used to identify the icon) , description, and handler.
        """
        return [
            {
                "name": "play",
                "display_name": _("Play"),
                "description": _("Play your Pygame Zero game."),
                "handler": self.play_toggle,
                "shortcut": "F5",
            },
            {
                "name": "images",
                "display_name": _("Images"),
                "description": _("Show the images used by Pygame Zero."),
                "handler": self.show_images,
                "shortcut": "Ctrl+Shift+I",
            },
            {
                "name": "fonts",
                "display_name": _("Fonts"),
                "description": _("Show the fonts used by Pygame Zero."),
                "handler": self.show_fonts,
                "shortcut": "Ctrl+Shift+F",
            },
            {
                "name": "sounds",
                "display_name": _("Sounds"),
                "description": _("Show the sounds used by Pygame Zero."),
                "handler": self.show_sounds,
                "shortcut": "Ctrl+Shift+N",
            },
            {
                "name": "music",
                "display_name": _("Music"),
                "description": _("Show the music used by Pygame Zero."),
                "handler": self.show_music,
                "shortcut": "Ctrl+Shift+M",
            },
        ]

    def api(self):
        """
        Return a list of API specifications to be used by auto-suggest and call
        tips.
        """
        return self.host.python_apis() + PYGAMEZERO_APIS

    def ensure_workspace_assets(self, workspace_dir):
        """
        Make the folders Pygame Zero looks in for a game's images, fonts,
        sounds and music. New images and sounds folders get the demo files
        the tutorials use; existing folders are left alone.
        """
        for asset_type in ASSET_TYPES:
            asset_path = os.path.join(workspace_dir, asset_type)
            if os.path.exists(asset_path):
                continue
            self.host.logger("pygamezero").debug("Creating directory: %s", asset_path)
            os.makedirs(asset_path)
            demo_path = os.path.join(ASSETS_DIR, asset_type)
            if os.path.isdir(demo_path):
                for filename in os.listdir(demo_path):
                    shutil.copy(os.path.join(demo_path, filename), asset_path)

    def play_toggle(self, event):
        """
        Handles the toggling of the play button to start/stop a script.
        """
        if self.running:
            self.stop_game()
            self.host.update_action(
                "play",
                display_name=_("Play"),
                description=_("Play your Pygame Zero game."),
                icon="play",
            )
            self.set_buttons(modes=True)
        else:
            self.run_game()
            if self.running:
                self.host.update_action(
                    "play",
                    display_name=_("Stop"),
                    description=_("Stop your Pygame Zero game."),
                    icon="stop",
                )
                self.set_buttons(modes=False)

    def run_game(self):
        """
        Run the current game.
        """
        if self.host.current_text() is None:
            self.host.logger("pygamezero").debug("There is no active text editor.")
            self.stop_game()
            return
        path = self.host.save_current()
        if path:
            self.running = self.host.run_program(path, python_args=["-m", "pgzero"])

    def stop_game(self):
        """
        Stop the currently running game.
        """
        self.host.logger("pygamezero").debug("Stopping script.")
        self.host.stop_program()
        self.running = False

    def show_images(self, event):
        """
        Open the directory containing the image assets used by Pygame Zero.

        This should open the host OS's file system explorer so users can drag
        new files into the opened folder.
        """
        self.host.open_directory(self.assets_dir("images"))

    def show_fonts(self, event):
        """
        Open the directory containing the font assets used by Pygame Zero.

        This should open the host OS's file system explorer so users can drag
        new files into the opened folder.
        """
        self.host.open_directory(self.assets_dir("fonts"))

    def show_sounds(self, event):
        """
        Open the directory containing the sound assets used by Pygame Zero.

        This should open the host OS's file system explorer so users can drag
        new files into the opened folder.
        """
        self.host.open_directory(self.assets_dir("sounds"))

    def show_music(self, event):
        """
        Open the directory containing the music assets used by Pygame Zero.

        This should open the host OS's file system explorer so users can drag
        new files into the opened folder.
        """
        self.host.open_directory(self.assets_dir("music"))
