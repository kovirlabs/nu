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

from PyQt6.QtCore import QObject, QSize, QThread, QTimer, Qt, pyqtSignal
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
    QInputDialog,
    QFileDialog,
    QMessageBox,
    QToolButton,
)
from mu.resources import load_icon
from .themes import Font
from ..command_log import CommandLog
from ..virtual_environment import VirtualEnvironmentError, activate_command, venv

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
    Defines a UI for selecting the mode for Nu.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup(self, modes, current_mode):
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Select Mode"))
        widget_layout = QVBoxLayout()
        label = QLabel(_('Choose what you\'d like to make, then click "OK".'))
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.setLayout(widget_layout)
        self.mode_list = QListWidget()
        self.mode_list.itemDoubleClicked.connect(self.select_and_accept)
        widget_layout.addWidget(self.mode_list)
        self.mode_list.setIconSize(QSize(48, 48))
        # Plain Python first (it's where most learners start), then the
        # other modes (all from plugins) by name.
        ordered = sorted(
            (item for item in modes.values() if not item.is_debugger),
            key=lambda item: (item.icon != "python", item.name.lower()),
        )
        for item in ordered:
            litem = ModeItem(item.name, item.description, item.icon, self.mode_list)
            if item.icon == current_mode:
                self.mode_list.setCurrentItem(litem)
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
    "What Nu Ran": the commands Nu has run for the learner (uv's, and those
    plugins log, see `mu.command_log`), as they'd type them, newest last.
    """

    def setup(self, commands, uv_path=None):
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "These are the commands Nu has run for you since it started, "
                "newest last. You can type them in a terminal yourself."
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
        self.sections.addTab(self.envar_widget, _("Environment Variables"))
        self.commands_widget = CommandLogWidget(self)
        self.commands_widget.setup(
            environment.get("commands"), uv_path=environment.get("uv")
        )
        self.sections.addTab(self.commands_widget, _("What Nu Ran"))
        widget_layout.addWidget(self.sections, stretch=1)
        self.environments_section = None
        if "environments" in environment:
            self.environments_section = EnvironmentsWidget(self)
            self.environments_section.setup(environment["environments"])
            widget_layout.addWidget(self.environments_section)


class EnvironmentsWidget(QWidget):
    """
    The Environment tab's "Advanced: more environments" section, collapsed
    until opened: the learner's environments (the default one and any named
    ones), which one Nu uses, and buttons to use another from the next start
    or make a new one.
    """

    def setup(self, environments):
        """
        `environments` are the dicts from
        `VirtualEnvironment.list_environments`.
        """
        self.environments = list(environments or [])
        # The folder of the environment the learner chose with "Use this
        # one", for the admin dialog's settings; None if they didn't.
        self.chosen = None
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.toggle = QToolButton()
        self.toggle.setText(_("Advanced: more environments"))
        self.toggle.setCheckable(True)
        self.toggle.setAutoRaise(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.toggled.connect(self.expand)
        layout.addWidget(self.toggle)
        self.body = QWidget()
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        self.body.setLayout(body_layout)
        intro = QLabel(
            _(
                "An environment is a separate set of packages for a project. "
                "Nu uses one at a time; if you choose another, Nu uses it "
                "from when you restart Nu."
            )
        )
        intro.setWordWrap(True)
        body_layout.addWidget(intro)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([_("Name"), _("Python"), _("Status")])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setMinimumHeight(110)
        self.tree.currentItemChanged.connect(self._update_buttons)
        body_layout.addWidget(self.tree)
        # What to type to do the same in a terminal.
        self.command_label = QLabel()
        self.command_label.setWordWrap(True)
        self.command_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body_layout.addWidget(self.command_label)
        buttons = QHBoxLayout()
        self.use_button = QPushButton(_("Use this one"))
        self.use_button.clicked.connect(self.use_selected)
        buttons.addWidget(self.use_button)
        self.new_button = QPushButton(_("New environment…"))
        self.new_button.clicked.connect(self.new_environment)
        buttons.addWidget(self.new_button)
        buttons.addStretch()
        body_layout.addLayout(buttons)
        layout.addWidget(self.body)
        self.body.setVisible(False)
        self.fill()

    def expand(self, expanded):
        """Show or hide the section's contents."""
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.body.setVisible(expanded)
        if expanded:
            # Make room for it rather than squeezing the facts above.
            window = self.window()
            if window is not self and window.layout() is not None:
                window.layout().activate()
                needed = window.minimumSizeHint().height()
                if window.height() < needed:
                    window.resize(window.width(), needed)

    def _is_next(self, environment):
        """Whether Nu will use `environment` from the next start."""
        if self.chosen:
            return environment["path"] == self.chosen
        return environment["next_start"]

    def _status(self, environment):
        """What the Status column says: what's true now and after a restart."""
        is_next = self._is_next(environment)
        if environment["in_use"]:
            return _("In use") if is_next else _("In use until you restart Nu")
        return _("From the next start") if is_next else ""

    def fill(self, select=None):
        """
        List the environments, selecting the one at `select` (a folder), or
        else the one in use.
        """
        self.tree.clear()
        current = None
        for environment in self.environments:
            name = environment["name"]
            if environment["default"]:
                name = _("{} (default)").format(name)
            item = QTreeWidgetItem(
                [
                    name,
                    environment["python_version"] or "?",
                    self._status(environment),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, environment)
            item.setToolTip(0, environment["path"])
            self.tree.addTopLevelItem(item)
            if select:
                if environment["path"] == select:
                    current = item
            elif environment["in_use"]:
                current = item
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)
        if current is not None:
            self.tree.setCurrentItem(current)
        self._update_buttons()

    def _selected(self):
        """The environment selected in the list, or None."""
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _update_buttons(self, *args):
        """ "Use this one" is for an environment Nu won't already use next."""
        environment = self._selected()
        self.use_button.setEnabled(
            environment is not None and not self._is_next(environment)
        )
        if environment is None:
            self.command_label.setText("")
            return
        self.command_label.setText(
            _("To use “{name}” in a terminal: {command}").format(
                name=environment["name"], command=activate_command(environment["path"])
            )
        )

    def use_selected(self):
        """
        Use the selected environment from the next start (once the learner
        clicks OK; see `AdminDialog.settings`).
        """
        environment = self._selected()
        if environment is None:
            return
        self.chosen = environment["path"]
        self.fill(select=self.chosen)

    def new_environment(self):
        """
        Ask for a name, then make the environment (showing what Nu runs) and
        add it to the list.
        """
        title = _("New Environment")
        name, ok = QInputDialog.getText(
            self,
            title,
            _(
                "Name of the new environment (letters, digits, - and _), "
                "e.g. project-a:"
            ),
        )
        if not ok:
            return
        name = name.strip()
        problem = venv.environment_name_problem(name)
        if problem:
            QMessageBox.warning(self, title, problem)
            return
        dialog = CreateEnvironmentDialog(self)
        dialog.setup(name)
        dialog.exec()
        if dialog.path:
            self.environments = venv.list_environments()
            self.fill(select=dialog.path)


class CreateEnvironmentWorker(QObject):
    """Makes a named environment, on a thread of its own (it takes a while)."""

    progress = pyqtSignal(str)
    # The new environment's folder and "", or "" and why it failed.
    finished = pyqtSignal(str, str)

    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self):
        try:
            path = venv.create_environment(self.name, progress=self.progress.emit)
        except VirtualEnvironmentError as exc:
            self.finished.emit("", exc.message)
        else:
            self.finished.emit(path, "")


class CreateEnvironmentDialog(QDialog):
    """
    Shows a new environment being made: the commands Nu runs (first the
    ``uv venv`` one) and each step, then whether it worked.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.done = False

    def setup(self, name):
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("New Environment"))
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        )
        self.text_area.setFont(code_font())
        layout.addWidget(self.text_area)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        layout.addWidget(self.button_box)
        self.text_area.appendPlainText(
            _("Making the environment “{}”. This can take a minute…").format(name)
        )
        self.thread = QThread(self)
        self.worker = CreateEnvironmentWorker(name)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.text_area.appendPlainText)
        self.worker.finished.connect(self.finish)
        self.thread.start()

    def finish(self, path, problem):
        """Say how it went and let the learner close the dialog."""
        self.thread.quit()
        self.thread.wait()
        self.done = True
        self.text_area.appendPlainText("")
        if path:
            self.path = path
            self.text_area.appendPlainText(_("FINISHED"))
        else:
            self.text_area.appendPlainText(problem)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def reject(self):
        """Don't close (Escape, the window's close button) until it's done."""
        if self.done:
            super().reject()


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
        "added": _("Added by you"),
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
        "plugins", the plugins folder under "folder", the page about
        writing plugins under "help_url" and, to add and remove plugins, the
        Host under "manager" and its `plugin_environment_state()` under
        "environment". `open_directory(path)` shows a folder in the system's
        file manager.
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
        self.manager = plugins.get("manager")
        self.environment = plugins.get("environment") or {}
        self.open_directory = open_directory
        #: What the learner changed with Add/Update/Remove this time, as
        #: sentences: it all happens at the next start.
        self.changes = []
        #: The packages of the plugins removed this time.
        self.removed = set()
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
        # After Nu moved to a new Python, the plugins the learner added need
        # installing again before they load.
        self.reinstall_box = QWidget()
        reinstall_row = QHBoxLayout(self.reinstall_box)
        reinstall_row.setContentsMargins(0, 0, 0, 0)
        self.reinstall_note = QLabel(
            _(
                "Nu has moved to Python {new}, so the plugins you added for "
                "Python {old} ({names}) are switched off until you install "
                "them again."
            ).format(
                new=self.environment.get("nu_python", ""),
                old=self.environment.get("python", ""),
                names=", ".join(self.environment.get("added", [])) or _("none"),
            )
        )
        self.reinstall_note.setWordWrap(True)
        reinstall_row.addWidget(self.reinstall_note, stretch=1)
        self.reinstall_button = QPushButton(_("Reinstall my plugins"))
        self.reinstall_button.clicked.connect(self.reinstall_plugins)
        reinstall_row.addWidget(
            self.reinstall_button, alignment=Qt.AlignmentFlag.AlignTop
        )
        self.reinstall_box.setVisible(self._python_changed())
        widget_layout.addWidget(self.reinstall_box)
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
        # What changes at the next start.
        self.changes_label = QLabel()
        self.changes_label.setWordWrap(True)
        self.changes_label.hide()
        widget_layout.addWidget(self.changes_label)
        # Adding, updating and removing plugins.
        manage = QHBoxLayout()
        self.add_button = QPushButton(_("Add a plugin…"))
        self.add_button.setToolTip(_("Install a plugin from PyPI by its name"))
        self.add_button.clicked.connect(self.add_plugin)
        manage.addWidget(self.add_button)
        self.add_file_button = QPushButton(_("Add from a file…"))
        self.add_file_button.setToolTip(
            _("Install a plugin from a .whl file (this works without the internet)")
        )
        self.add_file_button.clicked.connect(self.add_plugin_file)
        manage.addWidget(self.add_file_button)
        self.update_button = QPushButton(_("Update"))
        self.update_button.setToolTip(
            _("Get the latest version of a plugin you added from PyPI")
        )
        self.update_button.clicked.connect(self.update_plugin)
        manage.addWidget(self.update_button)
        self.remove_button = QPushButton(_("Remove"))
        self.remove_button.setToolTip(_("Remove a plugin you added"))
        self.remove_button.clicked.connect(self.remove_plugin)
        manage.addWidget(self.remove_button)
        manage.addStretch()
        widget_layout.addLayout(manage)
        can_add = self.manager is not None and not self._python_changed()
        self.add_button.setEnabled(can_add)
        self.add_file_button.setEnabled(can_add)
        self.update_button.setEnabled(False)
        self.remove_button.setEnabled(False)
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

    def _python_changed(self):
        return self.environment.get("status") == "python-changed"

    def _is_removed(self, row):
        return bool(row.get("distribution")) and row["distribution"] in self.removed

    def _checked(self, item):
        return item.checkState(self.ON) == Qt.CheckState.Checked

    def _status(self, item):
        """The status to show: what's true now, and what changes at restart."""
        row = self._row(item)
        if self._is_removed(row):
            return _("Removed; gone when you restart Nu")
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
        self._update_buttons(item)
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
        elif row["switched_off_after_errors"] and not self._checked(item):
            lines.append(
                _(
                    "It kept having errors, so it will be off the next time "
                    "you start Nu. They're in the log (the Current Log tab)."
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

    def _update_buttons(self, item):
        """Offer Update and Remove for a plugin the learner added."""
        row = self._row(item) if item is not None else {}
        usable = (
            self.manager is not None
            and not self._is_removed(row)
            and not self._python_changed()
        )
        self.update_button.setEnabled(usable and bool(row.get("updatable")))
        self.remove_button.setEnabled(usable and bool(row.get("removable")))

    def _selected_row(self):
        item = self.tree.currentItem()
        return self._row(item) if item is not None else None

    def add_plugin(self):
        """
        Ask for a plugin's package name, show what PyPI says about it and
        what Nu will run, and if the learner agrees, install it.
        """
        title = _("Add a Plugin")
        text, ok = QInputDialog.getText(
            self,
            title,
            _("The name of the plugin's package on PyPI (for example nu-microbit):"),
        )
        if not ok:
            return
        try:
            requirement = self.manager.check_plugin_name(text)
        except ValueError as ex:
            QMessageBox.warning(self, title, str(ex))
            return
        job = self.manager.add_plugin(requirement=requirement)
        confirm = AddPluginDialog(self)
        confirm.setup(
            title,
            job.preview,
            name=requirement.name,
            look_up=self.manager.look_up_plugin,
        )
        if confirm.exec():
            self.run_job(job, title)

    def add_plugin_file(self):
        """Add a plugin from a wheel file (no internet needed)."""
        title = _("Add a Plugin from a File")
        path, _filter = QFileDialog.getOpenFileName(
            self, title, "", _("Plugin files (*.whl)")
        )
        if not path:
            return
        try:
            name, version = self.manager.check_plugin_file(path)
        except ValueError as ex:
            QMessageBox.warning(self, title, str(ex))
            return
        job = self.manager.add_plugin(wheel=path)
        confirm = AddPluginDialog(self)
        confirm.setup(
            title,
            job.preview,
            info={
                "name": name,
                "version": version,
                "summary": "",
                "author": "",
                "homepage": "",
                "file": path,
            },
        )
        if confirm.exec():
            self.run_job(job, title)

    def update_plugin(self):
        """Update the selected plugin (one the learner added) from PyPI."""
        row = self._selected_row()
        if not (row and row.get("updatable")):
            return
        self.run_job(self.manager.update_plugin(row["distribution"]), _("Update"))

    def remove_plugin(self):
        """Remove the selected plugin (one the learner added)."""
        row = self._selected_row()
        if not (row and row.get("removable")):
            return
        job = self.manager.remove_plugin(row["distribution"])
        answer = QMessageBox.question(
            self,
            _("Remove a Plugin"),
            _(
                "Remove {name}? Nu will run:\n\n{commands}\n\nIt's gone the "
                "next time you start Nu."
            ).format(name=row["name"], commands="\n".join(job.preview)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.run_job(job, _("Remove a Plugin")):
            self.removed.add(row["distribution"])
            item = self.tree.currentItem()
            self._show_status(item)
            self._show_details(item)

    def reinstall_plugins(self):
        """Make the plugin environment again, with the plugins added before."""
        job = self.manager.reinstall_plugins()
        self.run_job(job, _("Reinstall my plugins"))
        if job.changed:
            self.reinstall_button.setEnabled(False)
            self.reinstall_note.setText(
                _("Your plugins are installed again. They load when you restart Nu.")
            )

    def run_job(self, job, title):
        """
        Run a plugin_env.PluginJob in the package progress window, then note
        what changes at the next start. Return whether it worked.
        """
        dialog = PackageDialog(self)
        dialog.setup_job(job, title)
        dialog.exec()
        if job.changed:
            self.changes += [m for m in job.messages if m.strip()]
            self.changes_label.setText(
                "<b>{}</b><br>{}".format(
                    html.escape(_("When you restart Nu:"), quote=False),
                    "<br>".join(html.escape(m, quote=False) for m in self.changes),
                )
            )
            self.changes_label.show()
        return job.succeeded

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


class PluginLookupWorker(QObject):
    """Asks PyPI about a package, on a thread of its own."""

    # What PyPI said (a dict; empty if it has no such package) and "", or
    # {} and why Nu couldn't ask.
    finished = pyqtSignal(dict, str)

    def __init__(self, look_up, name):
        super().__init__()
        self.look_up = look_up
        self.name = name

    def run(self):
        try:
            info = self.look_up(self.name)
        except Exception as ex:  # no internet, PyPI down, ...
            logger.info("Couldn't look up %s on PyPI: %s", self.name, ex)
            self.finished.emit({}, str(ex) or ex.__class__.__name__)
        else:
            self.finished.emit(info or {}, "")


class AddPluginDialog(QDialog):
    """
    Before adding a plugin: what it is (from PyPI, or the file's name), the
    trust note, and exactly what Nu will run. OK installs it.
    """

    def setup(self, title, commands, name=None, look_up=None, info=None):
        """
        `commands` are the lines Nu will run. Either `info` describes the
        plugin already (a file), or `look_up(name)` asks PyPI about `name`
        (off the GUI thread); OK is enabled once PyPI knows it.
        """
        self.setWindowTitle(title)
        self.setMinimumSize(560, 360)
        self.thread = None
        layout = QVBoxLayout(self)
        self.about = QLabel()
        self.about.setWordWrap(True)
        self.about.setTextFormat(Qt.TextFormat.RichText)
        self.about.setOpenExternalLinks(True)
        self.about.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(self.about)
        self.trust_note = QLabel(
            _(
                "A plugin is Python code that runs inside Nu, with the same "
                "access to your computer as Nu itself. Only add plugins you "
                "trust, just as you'd only install programs you trust."
            )
        )
        self.trust_note.setWordWrap(True)
        layout.addWidget(self.trust_note)
        layout.addWidget(QLabel(_("Nu will run:")))
        self.commands = QPlainTextEdit()
        self.commands.setReadOnly(True)
        self.commands.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.commands.setFont(code_font())
        self.commands.setPlainText("\n".join(commands))
        layout.addWidget(self.commands, stretch=1)
        layout.addWidget(QLabel(_("The plugin loads the next time you start Nu.")))
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText(_("Add it"))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        if info is not None:
            self.show_info(info, "")
            return
        self.name = name
        self.ok_button.setEnabled(False)
        self.about.setText(
            html.escape(_("Asking PyPI about {name}…").format(name=name), quote=False)
        )
        self.thread = QThread(self)
        self.worker = PluginLookupWorker(look_up, name)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_info)
        self.thread.start()

    def _stop_thread(self):
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()
            self.thread = None

    def show_info(self, info, problem):
        """Show what PyPI said about the plugin (or why it can't be added)."""
        self._stop_thread()
        if problem:
            self.about.setText(
                html.escape(
                    _(
                        "Nu couldn't ask PyPI about {name}, so it can't add it "
                        "now. Are you connected to the internet? ({problem})"
                    ).format(name=self.name, problem=problem),
                    quote=False,
                )
            )
            self.ok_button.setEnabled(False)
            return
        if not info:
            self.about.setText(
                html.escape(
                    _(
                        "PyPI has no package called {name}. Check the "
                        "spelling: the name is on the plugin's web page."
                    ).format(name=self.name),
                    quote=False,
                )
            )
            self.ok_button.setEnabled(False)
            return
        title = "<b>{}</b> {}".format(
            html.escape(info["name"]), html.escape(info.get("version", ""))
        )
        lines = [title]
        if info.get("summary"):
            lines.append(html.escape(info["summary"]))
        if info.get("author"):
            lines.append(html.escape(_("By: {author}").format(author=info["author"])))
        homepage = info.get("homepage", "")
        if homepage.startswith(("https://", "http://")):
            lines.append(
                html.escape(_("Web page:"))
                + ' <a href="{0}">{0}</a>'.format(html.escape(homepage))
            )
        if info.get("file"):
            lines.append(
                html.escape(_("From the file {file}").format(file=info["file"]))
            )
        else:
            lines.append(
                html.escape(
                    _(
                        "This is what the package says about itself on PyPI. "
                        "Check it's the plugin you meant: names can look alike."
                    )
                )
            )
        self.about.setText("<br>".join(lines))
        self.ok_button.setEnabled(True)

    def done(self, result):
        """
        Close, not leaving the lookup's thread running (Qt aborts if a
        running QThread is destroyed): if PyPI hasn't answered yet, this
        waits for it, at most the lookup's timeout (10 seconds).
        """
        if self.thread is not None:
            self.worker.finished.disconnect()
            self._stop_thread()
        super().done(result)


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
        "Українська": "uk_UA",
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
        self.commands_tab = None
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
        elif environment is not None and "commands" in environment:
            # No learner environment in this mode (a board's), but Nu may
            # still have run commands for it (e.g. micro:bit's mpremote).
            self.commands_tab = CommandLogWidget(self)
            self.commands_tab.setup(environment["commands"])
            self.tabs.addTab(self.commands_tab, _("What Nu Ran"))
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
        section = self.environment_tab and self.environment_tab.environments_section
        if section and section.chosen:
            settings["environment"] = section.chosen
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
        self.job = None

    def setup(self, to_remove, to_add):
        """
        Create the UI for the dialog.
        """
        self._build(_("Third Party Package Status"))
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

    def setup_job(self, job, title):
        """
        Show a plugin change (a mu.plugin.plugin_env.PluginJob) happening:
        the commands Nu runs and their output, then how it went.
        """
        self._build(title)
        self.job = job
        QTimer.singleShot(
            2, lambda: job.start(self.text_area.appendPlainText, self.job_finished)
        )

    def job_finished(self, job):
        """Say how the plugin change went."""
        self.text_area.appendPlainText("")
        if not job.succeeded:
            self.text_area.appendPlainText(_("Not everything worked: see above."))
        if job.changed:
            self.text_area.appendPlainText(
                _("The changes take effect the next time you start Nu.")
            )
        self.finish()

    def reject(self):
        """While a plugin change runs, don't close (Escape, the close button)."""
        if self.job is not None and not self.job.done:
            return
        super().reject()

    def _build(self, title):
        # Basic layout.
        self.setMinimumSize(600, 400)
        self.setWindowTitle(title)
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
