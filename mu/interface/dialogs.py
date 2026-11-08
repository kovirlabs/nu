"""
UI related code for dialogs used by Mu.

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

import html
import logging
import os
import webbrowser

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtGui import QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QListWidget,
    QLabel,
    QListWidgetItem,
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QTabWidget,
    QWidget,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
)
from mu.resources import load_icon
from .themes import Font
from ..command_log import CommandLog
from ..virtual_environment import venv

logger = logging.getLogger(__name__)


class ModeItem(QListWidgetItem):
    """
    Represents an available mode listed for selection.
    """

    def __init__(self, name, description, icon, parent=None):
        super().__init__(parent)
        self.name = name
        self.description = description
        self.icon = icon
        text = "{}\n{}".format(name, description)
        self.setText(text)
        self.setIcon(load_icon(self.icon))


class ModeSelector(QDialog):
    """
    Defines a UI for selecting the mode for Mu.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup(self, modes, current_mode):
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Select Mode"))
        widget_layout = QVBoxLayout()
        label = QLabel(
            _(
                'Please select the desired mode then click "OK". '
                'Otherwise, click "Cancel".'
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.setLayout(widget_layout)
        self.mode_list = QListWidget()
        self.mode_list.itemDoubleClicked.connect(self.select_and_accept)
        widget_layout.addWidget(self.mode_list)
        self.mode_list.setIconSize(QSize(48, 48))
        for name, item in modes.items():
            if not item.is_debugger:
                litem = ModeItem(item.name, item.description, item.icon, self.mode_list)
                if item.icon == current_mode:
                    self.mode_list.setCurrentItem(litem)
        self.mode_list.sortItems()
        instructions = QLabel(
            _(
                "Change mode at any time by clicking "
                'the "Mode" button containing Nu\'s logo.'
            )
        )
        instructions.setWordWrap(True)
        widget_layout.addWidget(instructions)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)

    def select_and_accept(self):
        """
        Handler for when an item is double-clicked.
        """
        self.accept()

    def get_mode(self):
        """
        Return details of the newly selected mode.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return self.mode_list.currentItem().icon
        else:
            raise RuntimeError("Mode change cancelled.")


class LogWidget(QWidget):
    """
    Used to display Mu's logs.
    """

    def setup(self, log):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "When reporting a bug, copy and paste the content of "
                "the following log file."
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.log_text_area = QPlainTextEdit()
        self.log_text_area.setReadOnly(True)
        self.log_text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_text_area.setPlainText(log)
        widget_layout.addWidget(self.log_text_area)


class EnvironmentVariablesWidget(QWidget):
    """
    Used for editing and displaying environment variables used with Python 3
    mode.
    """

    def setup(self, envars):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "The environment variables shown below will be "
                "set each time you run a Python 3 script.\n\n"
                "Each separate environment variable should be on a "
                "new line and of the form:\nNAME=VALUE"
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.text_area = QPlainTextEdit()
        self.text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text_area.setPlainText(envars)
        widget_layout.addWidget(self.text_area)


class PackagesWidget(QWidget):
    """
    Used for editing and displaying 3rd party packages installed via pip to be
    used with Python 3 mode.
    """

    def setup(self, packages):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.text_area = QPlainTextEdit()
        self.text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        label = QLabel(
            _(
                "The packages shown below will be available to "
                "import in Python 3 mode. Delete a package from "
                "the list to remove its availability.\n\n"
                "Each separate package name should be on a new "
                "line. Packages are installed from PyPI "
                "(see: https://pypi.org/)."
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.text_area.setPlainText(packages)
        widget_layout.addWidget(self.text_area)


def code_font():
    """Nu's code font (as in the editor), at the size of the dialog text."""
    font = Font().load()
    size = QApplication.font().pointSize()
    if size > 0:
        font.setPointSize(size)
    return font


class CopyButton(QPushButton):
    """
    A "Copy" button that puts `text()` of its source on the clipboard and
    says "Copied".
    """

    def __init__(self, source, parent=None):
        super().__init__(_("Copy"), parent)
        self.source = source
        self.setToolTip(_("Copy to the clipboard"))
        self.clicked.connect(self.copy)

    def copy(self):
        """Copy the source's text."""
        source = self.source
        text = source.toPlainText() if hasattr(source, "toPlainText") else source.text()
        QApplication.clipboard().setText(text)
        self.setText(_("Copied"))


class CommandLogWidget(QWidget):
    """
    "What Nu ran": the uv commands Nu has run in the learner's environment
    (see `mu.command_log`), as they'd type them, newest last.
    """

    def setup(self, commands, uv_path=None):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "These are the commands Nu has run in your environment since "
                "it started, newest last. You can type them in a terminal "
                "yourself."
            )
        )
        label.setWordWrap(True)
        top_row = QHBoxLayout()
        top_row.addWidget(label, stretch=1)
        widget_layout.addLayout(top_row)
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        # Wrap, so the end of a long command (the package, the file) shows.
        self.text_area.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        )
        self.text_area.setFont(code_font())
        self.text_area.setPlainText(commands or CommandLog().render())
        if uv_path:
            self.text_area.setToolTip(
                _("“uv” is Nu's copy of uv, at:\n{}").format(uv_path)
            )
        # Newest last: show the end.
        self.text_area.moveCursor(QTextCursor.MoveOperation.End)
        widget_layout.addWidget(self.text_area)
        self.copy_button = CopyButton(self.text_area)
        top_row.addWidget(self.copy_button)

    def showEvent(self, event):
        """Scroll to the newest command once there's room to show it."""
        super().showEvent(event)
        self.text_area.moveCursor(QTextCursor.MoveOperation.End)
        self.text_area.ensureCursorVisible()


class EnvironmentWidget(QWidget):
    """
    The learner's Python environment, made visible: where it is, which
    Python it has, and how to use it from a terminal, then its packages,
    environment variables and the uv commands Nu ran in it.
    """

    def setup(self, environment, envars, packages):
        """
        `environment` is the dict from `VirtualEnvironment.describe()` plus
        the rendered command log under "commands" (or None), `envars` and
        `packages` the text for their editors.
        """
        environment = environment or {}
        self.fields = {}
        self.copy_buttons = {}
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        if environment:
            intro = QLabel(
                _(
                    "Nu runs your programs with this Python environment: a "
                    "folder with its own Python and the packages you add. "
                    "It's an ordinary Python environment, so you can use it "
                    "from a terminal too."
                )
            )
            intro.setWordWrap(True)
            widget_layout.addWidget(intro)
            grid = QGridLayout()
            grid.setColumnStretch(1, 1)
            grid.setVerticalSpacing(2)
            name = environment.get("name", "")
            if environment.get("python_version"):
                name = _("{name} (Python {version})").format(
                    name=name, version=environment["python_version"]
                )
            rows = [
                ("name", _("Name"), name),
                ("path", _("Folder"), environment.get("path")),
                ("interpreter", _("Python"), environment.get("interpreter")),
                ("activate", _("Activate it"), environment.get("activate")),
                ("install", _("Add a package"), environment.get("install")),
                ("run", _("Run a program"), environment.get("run")),
                ("uv", _("Nu's uv"), environment.get("uv") or _("(not found)")),
            ]
            for row, (key, title, value) in enumerate(rows):
                grid.addWidget(QLabel(title), row, 0)
                # Selectable text that wraps between a command's arguments,
                # so a long path never hides the end of a command.
                field = QLabel(value or "")
                field.setWordWrap(True)
                field.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                if key == "name":
                    field.setStyleSheet("font-weight: bold;")
                else:
                    field.setFont(code_font())
                    self.copy_buttons[key] = CopyButton(field)
                    grid.addWidget(self.copy_buttons[key], row, 2)
                grid.addWidget(field, row, 1)
                self.fields[key] = field
            widget_layout.addLayout(grid)
        self.sections = QTabWidget()
        self.package_widget = PackagesWidget(self)
        self.package_widget.setup(packages)
        self.sections.addTab(self.package_widget, _("Packages"))
        self.envar_widget = EnvironmentVariablesWidget(self)
        self.envar_widget.setup(envars)
        self.sections.addTab(self.envar_widget, _("Environment variables"))
        self.commands_widget = CommandLogWidget(self)
        self.commands_widget.setup(
            environment.get("commands"), uv_path=environment.get("uv")
        )
        self.sections.addTab(self.commands_widget, _("What Nu ran"))
        widget_layout.addWidget(self.sections, stretch=1)


class PluginsWidget(QWidget):
    """
    The Plugins tab: every plugin Nu found, where it comes from, whether it
    loaded (and if not, why), and an On/Off checkbox. Switching takes effect
    the next time Nu starts.
    """

    # Columns.
    ON, NAME, FROM, STATUS, MODES = range(5)

    #: Where a plugin comes from (PluginRecord.kind), in the order shown.
    KINDS = {
        "bundled": _("Bundled with Nu"),
        "package": _("Installed package"),
        "folder": _("Plugins folder"),
    }

    #: Why a plugin couldn't load (PluginRecord.problem), for the learner.
    PROBLEMS = {
        "duplicate": _(
            "Another plugin has the same name, so Nu left this one out. "
            "Rename one of them."
        ),
        "import-failed": _("It has an error in its code, so Nu couldn't start it."),
        "incompatible": _(
            "It was written for a different version of Nu. Look for an update to it."
        ),
        "register-failed": _("It had an error while setting itself up."),
    }

    def setup(self, plugins, open_directory=None):
        """
        `plugins` holds the rows from `Host.describe_plugins` under
        "plugins", the plugins folder under "folder" and the page about
        writing plugins under "help_url". `open_directory(path)` shows a
        folder in the system's file manager.
        """
        self.rows = sorted(
            plugins.get("plugins", []),
            key=lambda row: (
                list(self.KINDS).index(row["kind"])
                if row["kind"] in self.KINDS
                else len(self.KINDS),
                row["name"].lower(),
            ),
        )
        self.folder = plugins.get("folder")
        self.help_url = plugins.get("help_url")
        self.open_directory = open_directory
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.intro = QLabel(
            _(
                "Plugins add modes to Nu. Untick a plugin to switch it off, or "
                "tick it to switch it back on. <b>Changes take effect the "
                "next time you start Nu.</b>"
            )
        )
        self.intro.setWordWrap(True)
        widget_layout.addWidget(self.intro)
        # The list.
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(
            [_("On"), _("Plugin"), _("From"), _("Status"), _("Modes")]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.header().setStretchLastSection(True)  # the modes
        self.items = []
        # Rows with room for the themes' checkboxes (16px and a border). The
        # hint goes on the last column, which stretches, so its width is moot.
        row_height = max(24, self.tree.fontMetrics().height() + 8)
        for row in self.rows:
            item = QTreeWidgetItem()
            item.setSizeHint(self.MODES, QSize(0, row_height))
            item.setData(self.ON, Qt.ItemDataRole.UserRole, row)
            if row["can_switch"]:
                item.setCheckState(
                    self.ON,
                    Qt.CheckState.Checked
                    if row["enabled"]
                    else Qt.CheckState.Unchecked,
                )
                item.setToolTip(
                    self.ON, _("Tick to switch it on, untick to switch it off")
                )
            else:
                # Switched with the first plugin of the same id.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setText(self.NAME, row["name"])
            item.setToolTip(self.NAME, row["description"] or row["name"])
            item.setText(self.FROM, self.KINDS.get(row["kind"], row["kind"]))
            item.setToolTip(self.FROM, row["origin"])
            item.setText(self.MODES, ", ".join(row["modes"]))
            self._show_status(item)
            self.tree.addTopLevelItem(item)
            self.items.append(item)
        self._fit_columns()
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.currentItemChanged.connect(self._show_details)
        self.tree.setMinimumHeight(120)
        widget_layout.addWidget(self.tree, stretch=1)
        # About the selected plugin: a plain summary, then (when there are
        # any) the technical details for whoever can fix it.
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        widget_layout.addWidget(self.summary)
        self.details_box = QWidget()
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.details.setFont(code_font())
        self.details_copy = CopyButton(self.details)
        details_row = QHBoxLayout(self.details_box)
        details_row.setContentsMargins(0, 0, 0, 0)
        details_row.addWidget(self.details, stretch=1)
        details_row.addWidget(self.details_copy, alignment=Qt.AlignmentFlag.AlignTop)
        widget_layout.addWidget(self.details_box, stretch=1)
        # Buttons and the trust note.
        buttons = QHBoxLayout()
        self.open_folder_button = QPushButton(_("Open plugins folder"))
        self.open_folder_button.setToolTip(self.folder or "")
        self.open_folder_button.clicked.connect(self.open_folder)
        buttons.addWidget(self.open_folder_button)
        self.help_button = QPushButton(_("How to write a plugin"))
        self.help_button.setEnabled(bool(self.help_url))
        self.help_button.clicked.connect(self.show_help)
        buttons.addWidget(self.help_button)
        buttons.addStretch()
        widget_layout.addLayout(buttons)
        self.trust_note = QLabel(
            _(
                "A plugin is Python code that runs inside Nu, with the same "
                "access to your computer as Nu itself. Only add plugins you "
                "trust, just as you'd only install programs you trust."
            )
        )
        self.trust_note.setWordWrap(True)
        widget_layout.addWidget(self.trust_note)
        if self.items:
            self.tree.setCurrentItem(self.items[0])
        else:
            self._show_details(None)

    def _row(self, item):
        return item.data(self.ON, Qt.ItemDataRole.UserRole)

    def _checked(self, item):
        return item.checkState(self.ON) == Qt.CheckState.Checked

    def _status(self, item):
        """The status to show: what's true now, and what changes at restart."""
        row = self._row(item)
        on_next_start = self._checked(item) if row["can_switch"] else row["enabled"]
        if row["status"] == "loaded":
            return _("On") if on_next_start else _("On until you restart Nu")
        if row["status"] == "disabled":
            if on_next_start:
                return _("Off until you restart Nu")
            if row["switched_off_after_errors"]:
                return _("Switched off after errors; see the log")
            return _("Off")
        if on_next_start:
            return _("Couldn't load")
        return _("Couldn't load; switched off")

    def _problem(self, row):
        """The first line about why a plugin couldn't load, for the learner."""
        return self.PROBLEMS.get(row["problem"], _("Nu couldn't load it."))

    def _show_status(self, item):
        row = self._row(item)
        item.setText(self.STATUS, self._status(item))
        if row["status"] == "skipped":
            item.setToolTip(
                self.STATUS, "{}\n\n{}".format(self._problem(row), row["reason"])
            )

    #: Room between the columns, in pixels.
    COLUMN_GAP = 16

    def _fit_columns(self):
        """Size the columns to their contents, with a gap between them."""
        for column in (self.ON, self.NAME, self.FROM, self.STATUS):
            self.tree.resizeColumnToContents(column)
            width = self.tree.columnWidth(column) + self.COLUMN_GAP
            self.tree.setColumnWidth(column, width)

    def _item_changed(self, item, column):
        if column == self.ON:
            self._show_status(item)
            self._fit_columns()  # the status may be longer now
            if item is self.tree.currentItem():
                self._show_details(item)

    def _show_details(self, item, previous=None):
        """Describe the selected plugin under the list."""
        if item is None:
            self.summary.setText(
                html.escape(_("Nu didn't find any plugins."), quote=False)
            )
            self.details_box.hide()
            return
        row = self._row(item)
        title = "<b>{}</b>".format(html.escape(row["name"]))
        if row["description"]:
            title += " \u2014 " + html.escape(row["description"])
        lines = [_("Status: {status}").format(status=self._status(item))]
        details = ""
        if row["status"] == "skipped":
            lines.append(self._problem(row))
            # The traceback ends with the reason; without one, the reason.
            details = row["detail"] or row["reason"]
        elif row["status"] == "disabled" and row["switched_off_after_errors"]:
            lines.append(
                _(
                    "Nu switched it off because it kept having errors. They're "
                    "in the log (the Current Log tab). Tick it to switch it "
                    "back on."
                )
            )
        elif row["status"] == "disabled":
            lines.append(_("It's switched off, so Nu didn't load it."))
        lines.append(
            _("From: {kind} ({origin})").format(
                kind=self.KINDS.get(row["kind"], row["kind"]), origin=row["origin"]
            )
        )
        lines.append(_("Id: {id}").format(id=row["id"]))
        if row["modes"]:
            lines.append(_("Modes: {modes}").format(modes=", ".join(row["modes"])))
        self.summary.setText(
            "<br>".join([title] + [html.escape(line, quote=False) for line in lines])
        )
        self.details.setPlainText(details)
        self.details_box.setVisible(bool(details))

    def enabled_plugins(self):
        """Whether each plugin should load at the next start: {id: bool}."""
        return {
            self._row(item)["id"]: self._checked(item)
            for item in self.items
            if self._row(item)["can_switch"]
        }

    def open_folder(self):
        """Show the plugins folder, making it first if it's missing."""
        if not (self.folder and self.open_directory):
            return
        try:
            os.makedirs(self.folder, exist_ok=True)
        except OSError as ex:
            logger.exception("Can't make the plugins folder %s", self.folder)
            self.summary.setText(
                html.escape(
                    _("Couldn't open the plugins folder {folder}: {error}").format(
                        folder=self.folder, error=ex
                    ),
                    quote=False,
                )
            )
            return
        self.open_directory(self.folder)

    def show_help(self):
        """Open the page about writing plugins in the web browser."""
        webbrowser.open_new(self.help_url)


class LocaleWidget(QWidget):
    """
    Used for manually setting the locale (and thus the language) used by Mu.
    """

    LANGUAGES = {
        _("Automatically detect"): "",
        "English": "en",
        "Deutsch": "de_DE",
        "Español": "es",
        "Français": "fr",
        "日本語": "ja",
        "Nederlands": "nl",
        "Polski": "pl",
        "Português (Br)": "pt_BR",
        "Português (Pt)": "pt_PT",
        "русский язык": "ru_RU",
        "Slovenský": "sk_SK",
        "Svenska": "sv",
        "tiếng Việt": "vi",
        "中文": "zh_CN",
    }

    def setup(self, locale):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.drop_down = QComboBox()
        for k, v in self.LANGUAGES.items():
            self.drop_down.addItem(k, v)
        index = self.drop_down.findData(locale)
        if index > -1:
            self.drop_down.setCurrentIndex(index)
        label = QLabel(
            _(
                "Please select the language for Nu's user interface from the "
                "choices listed below. <strong>Restart Nu for these changes "
                "to take effect.</strong>"
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        widget_layout.addWidget(self.drop_down)
        widget_layout.addStretch()

    def get_locale(self):
        """
        Return the user-selected language code.
        """
        return self.LANGUAGES.get(self.drop_down.currentText(), "")


class AdminDialog(QDialog):
    """
    Displays administrative related information and settings (logs, environment
    variables, third party packages etc...).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.package_widget = None
        self.envar_widget = None
        self.environment_tab = None
        self.plugins_tab = None

    def setup(
        self,
        log,
        settings,
        packages,
        mode,
        device_list,
        environment=None,
        focus=None,
        plugins=None,
        open_directory=None,
    ):
        """
        Build the tabs. `environment` holds the facts about the learner's
        Python environment (see `EnvironmentWidget.setup`); `plugins` what
        the Plugins tab shows (see `PluginsWidget.setup`, which also gets
        `open_directory`). `focus` names the tab to open on ("environment"
        or "plugins"), otherwise the log is shown.
        """
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Nu Administration"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.tabs = QTabWidget()
        widget_layout.addWidget(self.tabs)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)
        # Tabs
        self.log_widget = LogWidget(self)
        self.log_widget.setup(log)
        self.tabs.addTab(self.log_widget, _("Current Log"))
        if mode.uses_user_environment:
            self.environment_tab = EnvironmentWidget(self)
            self.environment_tab.setup(
                environment, settings.get("envars", ""), packages
            )
            self.tabs.addTab(self.environment_tab, _("Environment"))
            self.envar_widget = self.environment_tab.envar_widget
            self.package_widget = self.environment_tab.package_widget
            # Room for the environment's facts above its editors.
            self.setMinimumSize(760, 620)
        if plugins is not None:
            self.plugins_tab = PluginsWidget(self)
            self.plugins_tab.setup(plugins, open_directory=open_directory)
            self.tabs.addTab(self.plugins_tab, _("Plugins"))
            # Room for the list, the details and the trust note.
            self.setMinimumSize(760, 620)
        # Configure local.
        self.locale_widget = LocaleWidget(self)
        self.locale_widget.setup(settings.get("locale"))
        self.tabs.addTab(
            self.locale_widget, load_icon("language.svg"), _("Select Language")
        )
        self.log_widget.log_text_area.setFocus()
        if focus == "environment" and self.environment_tab:
            self.tabs.setCurrentWidget(self.environment_tab)
            self.environment_tab.sections.setFocus()
        elif focus == "plugins" and self.plugins_tab:
            self.tabs.setCurrentWidget(self.plugins_tab)
            self.plugins_tab.tree.setFocus()

    def settings(self):
        """
        Return a dictionary representation of the raw settings information
        generated by this dialog. Such settings will need to be processed /
        checked in the "logic" layer of Mu.
        """
        settings = {}
        if self.envar_widget:
            settings["envars"] = self.envar_widget.text_area.toPlainText()
        if self.package_widget:
            settings["packages"] = self.package_widget.text_area.toPlainText()
        settings["locale"] = self.locale_widget.get_locale()
        if self.plugins_tab:
            settings["plugins"] = self.plugins_tab.enabled_plugins()
        return settings


class FindReplaceDialog(QDialog):
    """
    Display a dialog for getting:

    * A term to find,
    * An optional value to replace the search term,
    * A flag to indicate if the user wishes to replace all.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup(self, find=None, replace=None, replace_flag=False):
        self.setMinimumSize(600, 200)
        self.setWindowTitle(_("Find / Replace"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        # Find.
        find_label = QLabel(_("Find:"))
        self.find_term = QLineEdit()
        self.find_term.setText(find)
        self.find_term.selectAll()
        widget_layout.addWidget(find_label)
        widget_layout.addWidget(self.find_term)
        # Replace
        replace_label = QLabel(_("Replace (optional):"))
        self.replace_term = QLineEdit()
        self.replace_term.setText(replace)
        widget_layout.addWidget(replace_label)
        widget_layout.addWidget(self.replace_term)
        # Global replace.
        self.replace_all_flag = QCheckBox(_("Replace all?"))
        self.replace_all_flag.setChecked(replace_flag)
        widget_layout.addWidget(self.replace_all_flag)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)

    def find(self):
        """
        Return the value the user entered to find.
        """
        return self.find_term.text()

    def replace(self):
        """
        Return the value the user entered for replace.
        """
        return self.replace_term.text()

    def replace_flag(self):
        """
        Return the value of the global replace flag.
        """
        return self.replace_all_flag.isChecked()


class PackageDialog(QDialog):
    """
    Display the output of the pip commands needed to remove or install
    packages.

    Because the QProcess mechanism we're using is asynchronous, we have to
    manage the pip requests via `pip_queue`. When one request is signalled
    as finished we start the next.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pip_queue = []

    def setup(self, to_remove, to_add):
        """
        Create the UI for the dialog.
        """
        # Basic layout.
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Third Party Package Status"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        # Text area for the commands and their output, wrapped so the end
        # of a long command (the packages) shows.
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        )
        widget_layout.addWidget(self.text_area)
        # Buttons.
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        widget_layout.addWidget(self.button_box)

        #
        # Set up the commands to be issues to pip. Since we'll be popping
        # from the list (as LIFO) we'll add the installs first so the
        # removes are the first to happen
        #
        if to_add:
            self.pip_queue.append(("install", to_add))
        if to_remove:
            self.pip_queue.append(("remove", to_remove))
        QTimer.singleShot(2, self.next_pip_command)

    def next_pip_command(self):
        """
        Run the next pip command, finishing if there is none.
        """
        if self.pip_queue:
            command, packages = self.pip_queue.pop()
            self.run_pip(command, packages)
        else:
            self.finish()

    def finish(self):
        """
        Set the UI to a valid end state.
        """
        self.text_area.appendPlainText("\nFINISHED")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def run_pip(self, command, packages):
        """
        Run a pip command in a subprocess and pipe the output to the dialog's
        text area.
        """
        if command == "remove":
            pip_fn = venv.remove_user_packages
        elif command == "install":
            pip_fn = venv.install_user_packages
        else:
            raise RuntimeError("Invalid pip command: %s %s" % (command, packages))
        record = pip_fn(
            packages,
            slots=venv.Slots(
                output=self.text_area.appendPlainText,
                finished=self.next_pip_command,
            ),
        )
        # Show the learner the real command before its output streams in
        # (the process starts on the next turn of the event loop).
        if self.text_area.toPlainText():
            self.text_area.appendPlainText("")
        self.text_area.appendPlainText("$ " + record.display())


class CrashDialog(QDialog):
    """
    Shown when Nu hits an error it can't recover from. It shows the crash
    details and lets the user copy them (e.g. into a bug report); nothing is
    sent anywhere.
    """

    ISSUES_URL = "https://github.com/kovirlabs/nu/issues"

    def __init__(self, details, parent=None):
        super().__init__(parent)
        self.details = details
        self.setWindowTitle(_("Nu has crashed"))
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout(self)
        label = QLabel(
            _(
                "Sorry, Nu hit an error it couldn't recover from and has to "
                "close. Nothing has been sent anywhere.<br><br>To report it, "
                'copy the details below into a new issue at <a href="{url}">'
                "{url}</a>."
            ).format(url=self.ISSUES_URL)
        )
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlainText(details)
        layout.addWidget(self.text_area)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.copy_button = QPushButton(_("Copy to clipboard"))
        button_box.addButton(self.copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_details)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def copy_details(self):
        """Put the crash details on the clipboard."""
        QApplication.clipboard().setText(self.details)
        self.copy_button.setText(_("Copied"))
