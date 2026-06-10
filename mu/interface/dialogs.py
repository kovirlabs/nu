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
import logging

from PyQt5.QtCore import QSize, QTimer
from PyQt5.QtWidgets import (
    QVBoxLayout,
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
)
from mu.resources import load_icon
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
                litem = ModeItem(
                    item.name, item.description, item.icon, self.mode_list
                )
                if item.icon == current_mode:
                    self.mode_list.setCurrentItem(litem)
        self.mode_list.sortItems()
        instructions = QLabel(
            _(
                "Change mode at any time by clicking "
                'the "Mode" button containing Mu\'s logo.'
            )
        )
        instructions.setWordWrap(True)
        widget_layout.addWidget(instructions)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
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
        if self.result() == QDialog.Accepted:
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
        self.log_text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
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
        self.text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
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
        self.text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
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
                "Please select the language for Mu's user interface from the "
                "choices listed below. <strong>Restart Mu for these changes "
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

    def setup(self, log, settings, packages, mode, device_list):
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Mu Administration"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.tabs = QTabWidget()
        widget_layout.addWidget(self.tabs)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)
        # Tabs
        self.log_widget = LogWidget(self)
        self.log_widget.setup(log)
        self.tabs.addTab(self.log_widget, _("Current Log"))
        if mode.short_name in ["python", "pygamezero"]:
            self.envar_widget = EnvironmentVariablesWidget(self)
            self.envar_widget.setup(settings.get("envars", ""))
            self.tabs.addTab(self.envar_widget, _("Python3 Environment"))
        if mode.short_name in ["python", "pygamezero"]:
            self.package_widget = PackagesWidget(self)
            self.package_widget.setup(packages)
            self.tabs.addTab(self.package_widget, _("Third Party Packages"))
        # Configure local.
        self.locale_widget = LocaleWidget(self)
        self.locale_widget.setup(settings.get("locale"))
        self.tabs.addTab(
            self.locale_widget, load_icon("language.svg"), _("Select Language")
        )
        self.log_widget.log_text_area.setFocus()

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
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
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
        # Text area for pip output.
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
        widget_layout.addWidget(self.text_area)
        # Buttons.
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
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
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

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
            raise RuntimeError(
                "Invalid pip command: %s %s" % (command, packages)
            )
        pip_fn(
            packages,
            slots=venv.Slots(
                output=self.text_area.appendPlainText,
                finished=self.next_pip_command,
            ),
        )
