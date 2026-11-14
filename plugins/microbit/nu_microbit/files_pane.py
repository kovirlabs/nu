"""
The micro:bit Files pane: the files on the micro:bit on one side, the files in
the learner's micro:bit folder on the other, and buttons to copy between them.
Only the widget: it says what the learner asked for through signals, and the
mode (see `mode.py`) does it on the board (see `files.py`).

Copyright (c) 2026 the Nu contributors (see the AUTHORS file).

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

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .files import local_files


def _size(size):
    """A file size for the learner: "120 bytes", "3.4 KB"."""
    if size < 1024:
        return _("{} bytes").format(size)
    return _("{:.1f} KB").format(size / 1024)


class FilesPane(QWidget):
    """
    Two lists and the buttons between them. `local_dir` is the learner's
    micro:bit folder. Signals say what the learner asked for:
    `refresh_requested()`, `get_requested(names)` (copy from the micro:bit),
    `put_requested(paths)` (copy onto it), `delete_requested(names)` and
    `open_requested(path)` (a file on the computer, in a tab).
    """

    refresh_requested = pyqtSignal()
    get_requested = pyqtSignal(list)
    put_requested = pyqtSignal(list)
    delete_requested = pyqtSignal(list)
    open_requested = pyqtSignal(str)

    def __init__(self, local_dir, parent=None):
        super().__init__(parent)
        self.local_dir = local_dir
        self.busy = False
        self.board_files = None  # None until the board has been listed

        self.board_list = self._file_list()
        self.board_list.itemDoubleClicked.connect(lambda item: self.get_selected())
        self.local_list = self._file_list()
        self.local_list.itemDoubleClicked.connect(self._open_item)

        self.board_label = QLabel(_("On your micro:bit"))
        self.local_label = QLabel(_("On your computer"))
        self.local_label.setToolTip(local_dir)

        self.get_button = QPushButton(_("◀ Copy to computer"))
        self.get_button.setToolTip(
            _("Copy the files selected on the micro:bit into your micro:bit folder.")
        )
        self.get_button.clicked.connect(self.get_selected)
        self.put_button = QPushButton(_("Copy to micro:bit ▶"))
        self.put_button.setToolTip(
            _("Copy the files selected on your computer onto the micro:bit.")
        )
        self.put_button.clicked.connect(self.put_selected)
        self.delete_button = QPushButton(_("Delete from micro:bit"))
        self.delete_button.clicked.connect(self.delete_selected)
        self.open_button = QPushButton(_("Open"))
        self.open_button.setToolTip(_("Open the file selected on your computer."))
        self.open_button.clicked.connect(self.open_selected)
        self.refresh_button = QPushButton(_("Refresh"))
        self.refresh_button.clicked.connect(self.refresh)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        middle = QVBoxLayout()
        middle.addStretch()
        for button in (self.get_button, self.put_button):
            middle.addWidget(button)
        middle.addStretch()

        lists = QGridLayout()
        lists.addWidget(self.board_label, 0, 0)
        lists.addWidget(self.local_label, 0, 2)
        lists.addWidget(self.board_list, 1, 0)
        lists.addLayout(middle, 1, 1)
        lists.addWidget(self.local_list, 1, 2)
        lists.setColumnStretch(0, 1)
        lists.setColumnStretch(2, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.open_button)

        layout = QVBoxLayout()
        layout.addLayout(lists)
        layout.addLayout(buttons)
        layout.addWidget(self.message)
        self.setLayout(layout)

        for widget in (self.board_list, self.local_list):
            widget.itemSelectionChanged.connect(self.update_buttons)
        self.show_local_files()
        self.update_buttons()

    @staticmethod
    def _file_list():
        widget = QListWidget()
        widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        widget.setMinimumHeight(80)
        return widget

    # --- what's shown ---

    def show_board_files(self, files):
        """List `files` (`files.BoardFile`s) as the micro:bit's."""
        self.board_files = list(files)
        self.board_list.clear()
        for board_file in self.board_files:
            item = QListWidgetItem(board_file.name)
            item.setData(Qt.ItemDataRole.UserRole, board_file.name)
            item.setToolTip(_size(board_file.size))
            self.board_list.addItem(item)
        if not self.board_files:
            self.board_label.setText(_("On your micro:bit (no files)"))
        else:
            self.board_label.setText(_("On your micro:bit"))
        self.update_buttons()

    def show_local_files(self, names=None):
        """
        List the files in the micro:bit folder (`names`, or read from it).
        """
        if names is None:
            names = local_files(self.local_dir)
        self.local_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(self.local_dir, name))
            self.local_list.addItem(item)
        self.update_buttons()

    def set_busy(self, busy, text=None):
        """Grey the buttons while the micro:bit is busy; say `text` if given."""
        self.busy = busy
        if text is not None:
            self.message.setText(text)
        self.update_buttons()

    def show_message(self, text):
        self.message.setText(text)

    def update_buttons(self):
        """Each button works on what's selected, and not while busy."""
        board_selected = bool(self.board_list.selectedItems())
        local_selected = bool(self.local_list.selectedItems())
        idle = not self.busy
        self.get_button.setEnabled(idle and board_selected)
        self.delete_button.setEnabled(idle and board_selected)
        self.put_button.setEnabled(idle and local_selected)
        self.open_button.setEnabled(local_selected)
        self.refresh_button.setEnabled(idle)

    # --- what the learner asks for ---

    def _selected(self, widget):
        return [item.data(Qt.ItemDataRole.UserRole) for item in widget.selectedItems()]

    def refresh(self):
        self.show_local_files()
        if not self.busy:
            self.refresh_requested.emit()

    def get_selected(self):
        names = self._selected(self.board_list)
        if names and not self.busy:
            self.get_requested.emit(names)

    def put_selected(self):
        paths = self._selected(self.local_list)
        if paths and not self.busy:
            self.put_requested.emit(paths)

    def delete_selected(self):
        names = self._selected(self.board_list)
        if names and not self.busy:
            self.delete_requested.emit(names)

    def open_selected(self):
        for path in self._selected(self.local_list):
            self.open_requested.emit(path)

    def _open_item(self, item):
        self.open_requested.emit(item.data(Qt.ItemDataRole.UserRole))
