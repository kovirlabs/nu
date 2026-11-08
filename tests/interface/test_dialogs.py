# -*- coding: utf-8 -*-
"""
Tests for the user interface elements of Mu.
"""

import os

import pytest
import mu.command_log
import mu.i18n
import mu.interface.dialogs
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget, QDialogButtonBox
from unittest import mock
from mu import virtual_environment
from mu.modes import (
    PythonMode,
    DebugMode,
)
from mu.modes.base import BaseMode


class BoardMode(BaseMode):
    """A selectable mode besides Python 3, as a plugin would add."""

    name = "Board"
    short_name = "board"
    description = "Write code for a board."
    icon = "help"


def test_ModeItem_init():
    """
    Ensure that ModeItem objects are setup correctly.
    """
    name = "item_name"
    description = "item_description"
    icon = "icon_name"
    mock_text = mock.MagicMock()
    mock_icon = mock.MagicMock()
    mock_load = mock.MagicMock(return_value=icon)
    with (
        mock.patch("mu.interface.dialogs.QListWidgetItem.setText", mock_text),
        mock.patch("mu.interface.dialogs.QListWidgetItem.setIcon", mock_icon),
        mock.patch("mu.interface.dialogs.load_icon", mock_load),
    ):
        mi = mu.interface.dialogs.ModeItem(name, description, icon)
        assert mi.name == name
        assert mi.description == description
        assert mi.icon == icon
    mock_text.assert_called_once_with("{}\n{}".format(name, description))
    mock_load.assert_called_once_with(icon)
    mock_icon.assert_called_once_with(icon)


def test_ModeSelector_setup():
    """
    Ensure the ModeSelector dialog is setup properly given a list of modes.

    If a mode has debugger = True it is ignored since debug mode is not a mode
    to be selected by users.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    modes = {
        "python": PythonMode(editor, view),
        "board": BoardMode(editor, view),
        "debugger": DebugMode(editor, view),
    }
    current_mode = "python"
    mock_item = mock.MagicMock()
    with mock.patch("mu.interface.dialogs.ModeItem", mock_item):
        with mock.patch("mu.interface.dialogs.QVBoxLayout"):
            with mock.patch("mu.interface.dialogs.QListWidget"):
                ms = mu.interface.dialogs.ModeSelector()
                ms.setLayout = mock.MagicMock()
                ms.setup(modes, current_mode)
                assert ms.setLayout.call_count == 1
    assert mock_item.call_count == 2


def test_ModeSelector_select_and_accept():
    """
    Ensure the accept slot is fired when this event handler is called.
    """
    ms = mu.interface.dialogs.ModeSelector()
    ms.accept = mock.MagicMock()
    ms.select_and_accept()
    ms.accept.assert_called_once_with()


def test_ModeSelector_get_mode():
    """
    Ensure that the ModeSelector will correctly return a selected mode (or
    raise the expected exception if cancelled).
    """
    ms = mu.interface.dialogs.ModeSelector()
    ms.result = mock.MagicMock(return_value=QDialog.DialogCode.Accepted)
    item = mock.MagicMock()
    item.icon = "name"
    ms.mode_list = mock.MagicMock()
    ms.mode_list.currentItem.return_value = item
    result = ms.get_mode()
    assert result == "name"
    ms.result.return_value = None
    with pytest.raises(RuntimeError):
        ms.get_mode()


def test_LogWidget_setup():
    """
    Ensure the log widget displays the referenced log file string in the
    expected way.
    """
    log = "this is the contents of a log file"
    lw = mu.interface.dialogs.LogWidget()
    lw.setup(log)
    assert lw.log_text_area.toPlainText() == log
    assert lw.log_text_area.isReadOnly()


def test_EnvironmentVariablesWidget_setup():
    """
    Ensure the widget for editing user defined environment variables displays
    the referenced string in the expected way.
    """
    envars = "name=value"
    evw = mu.interface.dialogs.EnvironmentVariablesWidget()
    evw.setup(envars)
    assert evw.text_area.toPlainText() == envars
    assert not evw.text_area.isReadOnly()


def test_PackagesWidget_setup():
    """
    Ensure the widget for editing settings related to third party packages
    displays the referenced data in the expected way.
    """
    packages = "foo\nbar\nbaz"
    pw = mu.interface.dialogs.PackagesWidget()
    pw.setup(packages)
    assert pw.text_area.toPlainText() == packages


def test_AdminDialog_setup_python_mode():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars when in Python mode.
    """
    log = "this is the contents of a log file"
    settings = {
        "envars": "name=value",
        "locale": "",
    }
    packages = "foo\nbar\nbaz\n"
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "a-mode-that-runs-code"
    mode.name = "Python 3"
    mode.uses_user_environment = True
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, packages, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s["packages"] == packages
    del s["packages"]
    assert s == settings


def _python_mode():
    mode = mock.MagicMock()
    mode.name = "Python 3"
    mode.uses_user_environment = True
    return mode


def test_AdminDialog_focus_environment():
    """Opened from the environment indicator, the dialog shows the
    environment first."""
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup(
        "log",
        {"envars": "", "locale": ""},
        "",
        _python_mode(),
        None,
        focus="environment",
    )
    assert ad.tabs.currentWidget() is ad.environment_tab


def test_AdminDialog_focus_defaults_to_log():
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup("log", {"envars": "", "locale": ""}, "", _python_mode(), None)
    assert ad.tabs.currentWidget() is ad.log_widget


def test_AdminDialog_focus_environment_in_other_modes():
    """In a mode without the learner's environment there's no such tab; the
    log is shown."""
    mode = mock.MagicMock()
    mode.uses_user_environment = False
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup("log", {"locale": ""}, "", mode, None, focus="environment")
    assert ad.tabs.currentWidget() is ad.log_widget


def test_AdminDialog_commands_tab_in_other_modes():
    """
    A mode without the learner's environment still shows "What Nu Ran" (the
    micro:bit plugin logs its mpremote and copy commands there), as a tab of
    its own.
    """
    mode = mock.MagicMock()
    mode.uses_user_environment = False
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup(
        "log",
        {"locale": ""},
        "",
        mode,
        None,
        environment={"commands": "$ mpremote connect COM3 fs cp a.py :main.py"},
    )
    assert ad.environment_tab is None
    assert ad.commands_tab.text_area.toPlainText().startswith("$ mpremote")
    titles = [ad.tabs.tabText(i) for i in range(ad.tabs.count())]
    assert "What Nu Ran" in titles
    assert ad.tabs.currentWidget() is ad.log_widget


def test_AdminDialog_no_commands_tab_without_the_log():
    mode = mock.MagicMock()
    mode.uses_user_environment = False
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup("log", {"locale": ""}, "", mode, None)
    assert ad.commands_tab is None


def test_AdminDialog_setup():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars.
    """
    log = "this is the contents of a log file"
    settings = {
        "locale": "",
    }
    packages = "foo\nbar\nbaz\n"
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "python"
    mode.name = "Debugger"
    mode.uses_user_environment = False
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, packages, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s == settings


def test_FindReplaceDialog_setup():
    """
    Ensure the find/replace dialog is setup properly given only the theme
    as an argument.
    """
    frd = mu.interface.dialogs.FindReplaceDialog()
    frd.setup()
    assert frd.find() == ""
    assert frd.replace() == ""
    assert frd.replace_flag() is False


def test_FindReplaceDialog_setup_with_args():
    """
    Ensure the find/replace dialog is setup properly given only the theme
    as an argument.
    """
    find = "foo"
    replace = "bar"
    flag = True
    frd = mu.interface.dialogs.FindReplaceDialog()
    frd.setup(find, replace, flag)
    assert frd.find() == find
    assert frd.replace() == replace
    assert frd.replace_flag()


def test_PackageDialog_setup():
    """
    Ensure the PackageDialog is set up correctly and kicks off the process of
    removing and adding packages.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.remove_packages = mock.MagicMock()

    to_remove = {"foo"}
    to_add = {"bar"}
    with mock.patch.object(pd, "pip_queue") as pip_queue:
        pip_queue.append = mock.Mock()
        pd.setup(to_remove, to_add)

    queue_called_with = pip_queue.append.call_args_list
    [args0], _ = queue_called_with[0]
    assert args0 == ("install", to_add)
    [args1], _ = queue_called_with[1]
    assert args1 == ("remove", to_remove)
    assert pd.button_box.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is False


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_packages():
    """
    Ensure the pkg_dirs of to-be-removed packages is correctly filled and the
    remove_package method is scheduled.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.to_remove = {"foo", "bar-baz", "Quux"}
    pd.module_dir = "wibble"
    dirs = [
        "foo-1.0.0.dist-info",
        "foo",
        "bar_baz-1.0.0.dist-info",
        "bar_baz",
        "quux-1.0.0.dist-info",
        "quux",
    ]
    with (
        mock.patch("mu.interface.dialogs.os.listdir", return_value=dirs),
        mock.patch("mu.interface.dialogs.QTimer") as mock_qtimer,
    ):
        pd.remove_packages()
        assert pd.pkg_dirs == {
            "foo": os.path.join("wibble", "foo-1.0.0.dist-info"),
            "bar-baz": os.path.join("wibble", "bar_baz-1.0.0.dist-info"),
            "Quux": os.path.join("wibble", "quux-1.0.0.dist-info"),
        }
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_dist_info():
    """
    Ensures that if there are packages remaining to be deleted, then the next
    one is deleted as expected.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.pkg_dirs = {"foo": os.path.join("bar", "foo-1.0.0.dist-info")}
    pd.module_dir = "baz"
    files = [["filename1", ""], ["filename2", ""], ["filename3", ""]]
    mock_remove = mock.MagicMock()
    mock_shutil = mock.MagicMock()
    mock_qtimer = mock.MagicMock()
    with (
        mock.patch("builtins.open"),
        mock.patch("mu.interface.dialogs.csv.reader", return_value=files),
        mock.patch("mu.interface.dialogs.os.remove", mock_remove),
        mock.patch("mu.interface.dialogs.shutil", mock_shutil),
        mock.patch("mu.interface.dialogs.QTimer", mock_qtimer),
    ):
        pd.remove_package()
        assert pd.pkg_dirs == {}
        assert mock_remove.call_count == 3
        assert mock_shutil.rmtree.call_count == 3
        pd.append_data.assert_called_once_with("Removed foo\n")
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_dist_info_cannot_delete():
    """
    Ensures that if there are packages remaining to be deleted, then the next
    one is deleted and any failures are logged.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.pkg_dirs = {"foo": os.path.join("bar", "foo-1.0.0.dist-info")}
    pd.module_dir = "baz"
    files = [["filename1", ""], ["filename2", ""], ["filename3", ""]]
    mock_remove = mock.MagicMock(side_effect=Exception("Bang"))
    mock_shutil = mock.MagicMock()
    mock_qtimer = mock.MagicMock()
    mock_log = mock.MagicMock()
    with (
        mock.patch("builtins.open"),
        mock.patch("mu.interface.dialogs.csv.reader", return_value=files),
        mock.patch("mu.interface.dialogs.os.remove", mock_remove),
        mock.patch("mu.interface.dialogs.logger.error", mock_log),
        mock.patch("mu.interface.dialogs.shutil", mock_shutil),
        mock.patch("mu.interface.dialogs.QTimer", mock_qtimer),
    ):
        pd.remove_package()
        assert pd.pkg_dirs == {}
        assert mock_remove.call_count == 3
        assert mock_log.call_count == 6
        assert mock_shutil.rmtree.call_count == 3
        pd.append_data.assert_called_once_with("Removed foo\n")
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_egg_info():
    """
    Ensures that if there are packages remaining to be deleted, then the next
    one is deleted as expected.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.pkg_dirs = {"foo": os.path.join("bar", "foo-1.0.0.egg-info")}
    pd.module_dir = "baz"
    files = "".join(["filename1\n", "filename2\n", "filename3\n"])
    mock_remove = mock.MagicMock()
    mock_shutil = mock.MagicMock()
    mock_qtimer = mock.MagicMock()
    with (
        mock.patch("builtins.open", mock.mock_open(read_data=files)),
        mock.patch("mu.interface.dialogs.os.remove", mock_remove),
        mock.patch("mu.interface.dialogs.shutil", mock_shutil),
        mock.patch("mu.interface.dialogs.QTimer", mock_qtimer),
    ):
        pd.remove_package()
        assert pd.pkg_dirs == {}
        assert mock_remove.call_count == 3
        assert mock_shutil.rmtree.call_count == 3
        pd.append_data.assert_called_once_with("Removed foo\n")
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_egg_info_cannot_delete():
    """
    Ensures that if there are packages remaining to be deleted, then the next
    one is deleted and any failures are logged.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.pkg_dirs = {"foo": os.path.join("bar", "foo-1.0.0.egg-info")}
    pd.module_dir = "baz"
    files = "".join(["filename1\n", "filename2\n", "filename3\n"])
    mock_remove = mock.MagicMock(side_effect=Exception("Bang"))
    mock_shutil = mock.MagicMock()
    mock_qtimer = mock.MagicMock()
    mock_log = mock.MagicMock()
    with (
        mock.patch("builtins.open", mock.mock_open(read_data=files)),
        mock.patch("mu.interface.dialogs.os.remove", mock_remove),
        mock.patch("mu.interface.dialogs.logger.error", mock_log),
        mock.patch("mu.interface.dialogs.shutil", mock_shutil),
        mock.patch("mu.interface.dialogs.QTimer", mock_qtimer),
    ):
        pd.remove_package()
        assert pd.pkg_dirs == {}
        assert mock_remove.call_count == 3
        assert mock_log.call_count == 6
        assert mock_shutil.rmtree.call_count == 3
        pd.append_data.assert_called_once_with("Removed foo\n")
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_egg_info_cannot_open_record():
    """
    If the installed-files.txt file is not available (sometimes the case), then
    simply raise an exception and communicate this to the user.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.pkg_dirs = {"foo": os.path.join("bar", "foo-1.0.0.egg-info")}
    pd.module_dir = "baz"
    mock_qtimer = mock.MagicMock()
    mock_log = mock.MagicMock()
    with (
        mock.patch("builtins.open", mock.MagicMock(side_effect=Exception("boom"))),
        mock.patch("mu.interface.dialogs.logger.error", mock_log),
        mock.patch("mu.interface.dialogs.QTimer", mock_qtimer),
    ):
        pd.remove_package()
        assert pd.pkg_dirs == {}
        assert mock_log.call_count == 2
        msg = "UNABLE TO REMOVE PACKAGE: foo (check the logs for more information.)"
        pd.append_data.assert_called_once_with(msg)
        mock_qtimer.singleShot.assert_called_once_with(2, pd.remove_package)


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_remove_package_end_state():
    """
    If there are no more packages to remove and there's nothing to be done for
    adding packages, then ensure all directories that do not contain files are
    deleted and the expected end-state is called.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.module_dir = "foo"
    pd.pkg_dirs = {}
    pd.to_add = {}
    pd.process = None
    pd.end_state = mock.MagicMock()
    with (
        mock.patch("mu.interface.dialogs.os.listdir", return_value=["bar", "baz"]),
        mock.patch(
            "mu.interface.dialogs.os.walk",
            side_effect=[[("bar", [], [])], [("baz", [], ["x"])]],
        ),
        mock.patch("mu.interface.dialogs.shutil") as mock_shutil,
    ):
        pd.remove_package()
        assert mock_shutil.rmtree.call_count == 2
        call_args = mock_shutil.rmtree.call_args_list
        assert call_args[0][0][0] == os.path.join("foo", "bar")
        assert call_args[1][0][0] == os.path.join("foo", "bin")
    pd.end_state.assert_called_once_with()


@pytest.mark.skip(reason="Superseded probably by ntoll's previous work on venv")
def test_PackageDialog_end_state():
    """
    Ensure the expected end-state is correctly configured (for when all tasks
    relating to third party packages have finished).
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.append_data = mock.MagicMock()
    pd.button_box = mock.MagicMock()
    pd.end_state()
    pd.append_data.assert_called_once_with("\nFINISHED")
    pd.button_box.button().setEnabled.assert_called_once_with(True)


@pytest.mark.skip(reason="Superseded probably by virtual environment work")
def test_PackageDialog_run_pip():
    """
    Ensure the expected package to be installed is done so via the expected
    correct call to "pip" in a new process (as per the recommended way to
    us "pip").
    """
    pd = mu.interface.dialogs.PackageDialog()
    venv = virtual_environment.VirtualEnvironment(".")
    mock_process = mock.MagicMock()
    with mock.patch("mu.interface.dialogs.QProcess", mock_process):
        pd.setup({}, {"foo"})
        pd.process.readyRead.connect.assert_called_once_with(pd.read_process)
        pd.process.finished.connect.assert_called_once_with(pd.finished)
        args = [
            "-m",  # run the module
            "pip",  # called pip
            "install",  # to install
            "foo",  # a package called "foo"
        ]
        pd.process.start.assert_called_once_with(venv.interpreter, args)


@pytest.mark.skip(reason="Superseded probably by virtual environment work")
def test_PackageDialog_finished_with_more_to_remove():
    """
    When the pip process is finished, check if there are more packages to
    install and run again.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.run_pip = mock.MagicMock()
    pd.process = mock.MagicMock()
    venv = virtual_environment.VirtualEnvironment(".")
    pd.setup({}, {"foo"}, venv)
    pd.finished()
    assert pd.process is None
    pd.run_pip.assert_called_once_with()


@pytest.mark.skip(reason="Superseded probably by virtual environment work")
def test_PackageDialog_finished_to_end_state():
    """
    When the pip process is finished, if there are no more packages to install
    and there's no more activity for removing packages, move to the end state.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.to_add = set()
    pd.pkg_dirs = {}
    pd.end_state = mock.MagicMock()
    pd.finished()
    pd.end_state.assert_called_once_with()


@pytest.mark.skip(reason="Superseded probably by virtual environment work")
def test_PackageDialog_read_process():
    """
    Ensure any data from the subprocess running "pip" is read and appended to
    the text area.
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.process = mock.MagicMock()
    pd.process.readAll().data.return_value = b"hello"
    pd.append_data = mock.MagicMock()
    mock_timer = mock.MagicMock()
    with mock.patch("mu.interface.dialogs.QTimer", mock_timer):
        pd.read_process()
        pd.append_data.assert_called_once_with("hello")
        mock_timer.singleShot.assert_called_once_with(2, pd.read_process)


@pytest.mark.skip(reason="Superseded probably by virtual environment work")
def test_PackageDialog_append_data():
    """
    Ensure that when data is appended, it's added to the end of the text area!
    """
    pd = mu.interface.dialogs.PackageDialog()
    pd.text_area = mock.MagicMock()
    pd.append_data("hello")
    c = pd.text_area.textCursor()
    assert c.movePosition.call_count == 2
    c.insertText.assert_called_once_with("hello")
    pd.text_area.setTextCursor.assert_called_once_with(c)


def test_CrashDialog_shows_details_and_where_to_report():
    dialog = mu.interface.dialogs.CrashDialog("Nu 2.0\nValueError: BANG")
    assert dialog.text_area.toPlainText() == "Nu 2.0\nValueError: BANG"
    assert dialog.text_area.isReadOnly()
    labels = dialog.findChildren(mu.interface.dialogs.QLabel)
    assert any(dialog.ISSUES_URL in label.text() for label in labels)
    assert any("Nothing has been sent" in label.text() for label in labels)


def test_CrashDialog_copy_details():
    """
    Copy puts the details on the clipboard and doesn't close the dialog.
    """
    dialog = mu.interface.dialogs.CrashDialog("ValueError: BANG")
    clipboard = mock.MagicMock()
    with mock.patch(
        "mu.interface.dialogs.QApplication.clipboard", return_value=clipboard
    ):
        dialog.copy_button.click()
    clipboard.setText.assert_called_once_with("ValueError: BANG")
    assert dialog.copy_button.text() == "Copied"


def test_CrashDialog_close():
    dialog = mu.interface.dialogs.CrashDialog("details")
    dialog.show()
    button_box = dialog.findChild(QDialogButtonBox)
    button_box.button(QDialogButtonBox.StandardButton.Close).click()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.isVisible()


#
# The Environment tab (Phase 4b): the learner's Python environment, made
# visible.
#
ENVIRONMENT = {
    "name": "mu_venv",
    "path": "/data/mu/mu_venv-311-20261108-030353",
    "interpreter": "/data/mu/mu_venv-311-20261108-030353/bin/python",
    "python_version": "3.11.15",
    "activate": "source /data/mu/mu_venv-311-20261108-030353/bin/activate",
    "install": "uv pip install --python /data/mu/…/python cowsay",
    "run": "uv run --python /data/mu/…/python hello.py",
    "uv": "/opt/nu/bin/uv",
    "commands": "$ uv pip list --format=json\n  10:00:00 · finished OK (exit code 0)",
}


@pytest.fixture
def environment_widget():
    parent = QWidget()
    widget = mu.interface.dialogs.EnvironmentWidget(parent)
    widget.setup(dict(ENVIRONMENT), "NAME=value", "cowsay\nrich")
    yield widget
    parent.deleteLater()


def test_EnvironmentWidget_facts(environment_widget):
    """Where the environment is, which Python, and how to use it yourself."""
    fields = environment_widget.fields
    assert fields["name"].text() == "mu_venv (Python 3.11.15)"
    for key in ("path", "interpreter", "activate", "install", "run", "uv"):
        assert fields[key].text() == ENVIRONMENT[key]
        # Selectable, and wrapped so a long path never hides the end of a
        # command.
        assert fields[key].wordWrap()
        assert fields[key].textInteractionFlags() & (
            Qt.TextInteractionFlag.TextSelectableByMouse
        )


def test_EnvironmentWidget_facts_unknown_version_and_uv():
    parent = QWidget()
    widget = mu.interface.dialogs.EnvironmentWidget(parent)
    widget.setup(dict(ENVIRONMENT, python_version=None, uv=None), "", "")
    assert widget.fields["name"].text() == "mu_venv"
    assert widget.fields["uv"].text() == "(not found)"


def test_EnvironmentWidget_copy_button(environment_widget, qtapp):
    """Each fact has a Copy button that copies its full text."""
    button = environment_widget.copy_buttons["activate"]
    button.click()
    assert qtapp.clipboard().text() == ENVIRONMENT["activate"]
    assert button.text() == "Copied"


def test_EnvironmentWidget_sections(environment_widget):
    """The packages and environment-variable editors keep their behaviour, as
    sections of the Environment tab, beside "What Nu Ran"."""
    sections = environment_widget.sections
    titles = [sections.tabText(i) for i in range(sections.count())]
    assert titles == ["Packages", "Environment Variables", "What Nu Ran"]
    assert environment_widget.package_widget.text_area.toPlainText() == ("cowsay\nrich")
    assert environment_widget.envar_widget.text_area.toPlainText() == "NAME=value"


def test_EnvironmentWidget_without_facts():
    """No environment details: the sections still work."""
    parent = QWidget()
    widget = mu.interface.dialogs.EnvironmentWidget(parent)
    widget.setup(None, "A=b", "cowsay")
    assert widget.fields == {}
    assert widget.package_widget.text_area.toPlainText() == "cowsay"
    assert "hasn't run" in widget.commands_widget.text_area.toPlainText()


def test_CommandLogWidget(qtapp):
    """What Nu Ran: read-only, monospace, newest last, copyable."""
    parent = QWidget()
    widget = mu.interface.dialogs.CommandLogWidget(parent)
    widget.setup(ENVIRONMENT["commands"], uv_path="/opt/nu/bin/uv")
    text_area = widget.text_area
    assert text_area.toPlainText() == ENVIRONMENT["commands"]
    assert text_area.isReadOnly()
    assert text_area.font().family() == "Source Code Pro"  # Nu's code font.
    assert "/opt/nu/bin/uv" in text_area.toolTip()
    # Long commands wrap rather than hide their end.
    assert text_area.lineWrapMode() == text_area.LineWrapMode.WidgetWidth
    # Scrolled to the newest (last) command, also once it's shown.
    assert text_area.textCursor().atEnd()
    text_area.moveCursor(text_area.textCursor().MoveOperation.Start)
    parent.show()
    assert text_area.textCursor().atEnd()
    parent.hide()
    widget.copy_button.click()
    assert qtapp.clipboard().text() == ENVIRONMENT["commands"]


def test_CommandLogWidget_without_uv():
    parent = QWidget()
    widget = mu.interface.dialogs.CommandLogWidget(parent)
    widget.setup("", uv_path=None)
    assert "hasn't run" in widget.text_area.toPlainText()
    assert widget.text_area.toolTip() == ""


def test_AdminDialog_environment_tab():
    """In a mode that uses the learner's environment, one Environment tab
    holds the facts and the package / environment-variable editors."""
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    settings = {"envars": "A=b", "locale": ""}
    ad.setup("log", settings, "cowsay", _python_mode(), None, environment=ENVIRONMENT)
    titles = [ad.tabs.tabText(i) for i in range(ad.tabs.count())]
    assert titles == ["Current Log", "Environment", "Select Language"]
    assert ad.environment_tab.fields["path"].text() == ENVIRONMENT["path"]
    assert ad.package_widget is ad.environment_tab.package_widget
    assert ad.envar_widget is ad.environment_tab.envar_widget
    # Same settings keys as before.
    assert ad.settings() == {"envars": "A=b", "packages": "cowsay", "locale": ""}


#
# The package dialog shows the real command before its output.
#
def _record(argv):
    from mu.command_log import CommandLog

    return CommandLog().start(argv)


def test_PackageDialog_run_pip_shows_the_command():
    pd = mu.interface.dialogs.PackageDialog()
    pd.setup(set(), set())  # Nothing queued; just build the UI.
    record = _record(["/opt/uv", "pip", "install", "--python", "/env/python", "x"])
    with (
        mock.patch.object(
            virtual_environment.venv, "install_user_packages", return_value=record
        ) as install,
        mock.patch.object(mu.command_log.sys, "platform", "linux"),
    ):
        pd.run_pip("install", {"x"})
    install.assert_called_once()
    assert pd.text_area.toPlainText() == ("$ uv pip install --python /env/python x")
    # Its output and the next command follow.
    pd.text_area.appendPlainText("Installed 1 package")
    remove = _record(["/opt/uv", "pip", "uninstall", "y"])
    with (
        mock.patch.object(
            virtual_environment.venv, "remove_user_packages", return_value=remove
        ),
        mock.patch.object(mu.command_log.sys, "platform", "linux"),
    ):
        pd.run_pip("remove", {"y"})
    assert pd.text_area.toPlainText() == (
        "$ uv pip install --python /env/python x\n"
        "Installed 1 package\n"
        "\n"
        "$ uv pip uninstall y"
    )


def test_PackageDialog_run_pip_invalid_command():
    pd = mu.interface.dialogs.PackageDialog()
    with pytest.raises(RuntimeError):
        pd.run_pip("frobnicate", {"x"})


def test_PackageDialog_next_pip_command_and_finish():
    """Commands run one after another (removals first), then FINISHED."""
    pd = mu.interface.dialogs.PackageDialog()
    pd.setup(set(), set())
    pd.pip_queue = [("install", {"a"}), ("remove", {"b"})]
    pd.run_pip = mock.MagicMock()
    pd.next_pip_command()
    pd.run_pip.assert_called_once_with("remove", {"b"})
    pd.next_pip_command()
    pd.run_pip.assert_called_with("install", {"a"})
    pd.next_pip_command()
    assert pd.text_area.toPlainText().endswith("FINISHED")
    assert pd.button_box.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


#
# The Plugins tab.
#
def plugin_row(**overrides):
    """A row as Host.describe_plugins gives it."""
    row = {
        "id": "pygamezero",
        "name": "Pygame Zero",
        "description": "Adds Pygame Zero mode, for making games.",
        "kind": "bundled",
        "origin": "nu-pygamezero 0.1.0",
        "status": "loaded",
        "problem": "",
        "reason": "",
        "detail": "",
        "enabled": True,
        "switched_off_after_errors": False,
        "can_switch": True,
        "modes": ["Pygame Zero"],
    }
    row.update(overrides)
    return row


PLUGINS = {
    "plugins": [
        plugin_row(),
        plugin_row(
            id="circuitpython",
            name="circuitpython",
            description="The CircuitPython mode for the Nu editor.",
            origin="nu-circuitpython 0.1.0",
            status="disabled",
            enabled=False,
            modes=[],
        ),
        plugin_row(
            id="cows",
            name="Cows",
            description="",
            kind="package",
            origin="nu-cows 2.0",
            modes=["Cow", "Calf"],
        ),
        plugin_row(
            id="broken",
            name="broken",
            description="",
            kind="folder",
            origin="/data/mu/plugins/broken.py",
            status="skipped",
            problem="import-failed",
            reason="it failed to import: NameError: name 'x' is not defined",
            detail="Traceback (most recent call last):\n  ...\nNameError: x",
            modes=[],
        ),
        plugin_row(
            id="flaky",
            name="flaky",
            description="",
            kind="folder",
            origin="/data/mu/plugins/flaky.py",
            status="disabled",
            enabled=False,
            switched_off_after_errors=True,
            modes=[],
        ),
        plugin_row(
            id="cows",
            name="cows",
            description="",
            kind="folder",
            origin="/data/mu/plugins/cows.py",
            status="skipped",
            problem="duplicate",
            reason="another plugin is already called 'cows'",
            can_switch=False,
            modes=[],
        ),
    ],
    "folder": "/data/mu/plugins",
    "help_url": "https://example.org/plugins/",
}


@pytest.fixture
def plugins_widget():
    widget = mu.interface.dialogs.PluginsWidget()
    open_directory = mock.MagicMock()
    widget.setup(PLUGINS, open_directory=open_directory)
    widget.open_directory = open_directory
    return widget


def cells(widget, column):
    return [
        widget.tree.topLevelItem(i).text(column)
        for i in range(widget.tree.topLevelItemCount())
    ]


def test_PluginsWidget_lists_every_plugin(plugins_widget):
    """
    Bundled plugins first, then installed packages, then the plugins
    folder; each with where it comes from, its status and its modes.
    """
    w = plugins_widget
    C = mu.interface.dialogs.PluginsWidget
    assert cells(w, C.NAME) == [
        "circuitpython",
        "Pygame Zero",
        "Cows",
        "broken",
        "cows",
        "flaky",
    ]
    assert cells(w, C.FROM) == [
        "Bundled with Nu",
        "Bundled with Nu",
        "Installed package",
        "Plugins folder",
        "Plugins folder",
        "Plugins folder",
    ]
    assert cells(w, C.STATUS) == [
        "Off",
        "On",
        "On",
        "Couldn't load",
        "Couldn't load",
        "Switched off after errors; see the log",
    ]
    assert cells(w, C.MODES) == ["", "Pygame Zero", "Cow, Calf", "", "", ""]
    # Where exactly, on hover.
    assert w.tree.topLevelItem(1).toolTip(C.FROM) == "nu-pygamezero 0.1.0"
    assert w.tree.topLevelItem(3).toolTip(C.FROM) == "/data/mu/plugins/broken.py"


def test_PluginsWidget_checkboxes(plugins_widget):
    w = plugins_widget
    C = mu.interface.dialogs.PluginsWidget
    states = [
        w.tree.topLevelItem(i).checkState(C.ON)
        for i in range(w.tree.topLevelItemCount())
    ]
    Checked, Unchecked = Qt.CheckState.Checked, Qt.CheckState.Unchecked
    assert states == [Unchecked, Checked, Checked, Checked, Unchecked, Unchecked]
    # A duplicate id is switched along with the first plugin of that name.
    duplicate = w.tree.topLevelItem(4)
    assert not duplicate.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert w.enabled_plugins() == {
        "circuitpython": False,
        "pygamezero": True,
        "cows": True,
        "broken": True,
        "flaky": False,
    }


@pytest.mark.parametrize(
    "row, expected",
    [
        (1, "On until you restart Nu"),
        (0, "Off until you restart Nu"),
        (3, "Couldn't load; switched off"),
        (5, "Off until you restart Nu"),
    ],
)
def test_PluginsWidget_toggling_says_when_it_happens(plugins_widget, row, expected):
    """Ticking or unticking a plugin says it takes effect at the next start."""
    w = plugins_widget
    C = mu.interface.dialogs.PluginsWidget
    item = w.tree.topLevelItem(row)
    before = item.text(C.STATUS)
    checked = item.checkState(C.ON) == Qt.CheckState.Checked
    item.setCheckState(
        C.ON, Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked
    )
    assert item.text(C.STATUS) == expected
    item.setCheckState(
        C.ON, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    )
    assert item.text(C.STATUS) == before


def test_PluginsWidget_details_of_a_loaded_plugin(plugins_widget):
    w = plugins_widget
    w.tree.setCurrentItem(w.tree.topLevelItem(1))
    summary = w.summary.text()
    assert "Pygame Zero" in summary
    assert "Adds Pygame Zero mode, for making games." in summary
    assert "nu-pygamezero 0.1.0" in summary
    assert "pygamezero" in summary
    assert "From: Bundled with Nu (nu-pygamezero 0.1.0)" in summary
    assert w.details_box.isHidden()


def test_PluginsWidget_details_of_a_plugin_that_failed(plugins_widget):
    """
    A plain first line for the learner, then the full details (the
    traceback) for whoever fixes it, which can be copied.
    """
    w = plugins_widget
    C = mu.interface.dialogs.PluginsWidget
    item = w.tree.topLevelItem(3)
    w.tree.setCurrentItem(item)
    assert "It has an error in its code, so Nu couldn't start it." in (w.summary.text())
    assert not w.details_box.isHidden()
    details = w.details.toPlainText()
    assert details.startswith("Traceback (most recent call last)")
    assert details.endswith("NameError: x")
    tooltip = item.toolTip(C.STATUS)
    assert tooltip.startswith("It has an error in its code")
    assert "NameError" in tooltip


@pytest.mark.parametrize(
    "problem, expected",
    [
        ("duplicate", "Another plugin has the same name"),
        ("incompatible", "written for a different version of Nu"),
        ("register-failed", "had an error while setting itself up"),
        ("something-new", "Nu couldn't load it."),
    ],
)
def test_PluginsWidget_explains_each_problem(problem, expected):
    widget = mu.interface.dialogs.PluginsWidget()
    row = plugin_row(status="skipped", problem=problem, reason="why", modes=[])
    widget.setup({"plugins": [row], "folder": "/p", "help_url": ""})
    assert expected in widget.summary.text()
    assert widget.details.toPlainText() == "why"


def test_PluginsWidget_details_switched_off_after_errors(plugins_widget):
    w = plugins_widget
    w.tree.setCurrentItem(w.tree.topLevelItem(5))
    assert "kept having errors" in w.summary.text()
    assert "Current Log" in w.summary.text()


def test_PluginsWidget_details_switched_off(plugins_widget):
    w = plugins_widget
    w.tree.setCurrentItem(w.tree.topLevelItem(0))
    assert "switched off" in w.summary.text()


def test_PluginsWidget_says_changes_need_a_restart(plugins_widget):
    assert "next time you start Nu" in plugins_widget.intro.text()


def test_PluginsWidget_trust_note(plugins_widget):
    note = plugins_widget.trust_note.text()
    assert "Only add plugins you trust" in note


def test_PluginsWidget_open_folder(plugins_widget, tmp_path):
    """The plugins folder is created if it's missing, then opened."""
    w = plugins_widget
    folder = tmp_path / "plugins"
    w.folder = str(folder)
    w.open_folder_button.click()
    assert folder.is_dir()
    w.open_directory.assert_called_once_with(str(folder))


def test_PluginsWidget_open_folder_that_cant_be_made(plugins_widget, tmp_path):
    w = plugins_widget
    w.folder = str(tmp_path / "plugins")
    with mock.patch("os.makedirs", side_effect=PermissionError("no")):
        w.open_folder_button.click()
    w.open_directory.assert_not_called()
    assert "Couldn't open" in w.summary.text()


def test_PluginsWidget_how_to_write_a_plugin(plugins_widget):
    with mock.patch("webbrowser.open_new") as open_new:
        plugins_widget.help_button.click()
    open_new.assert_called_once_with("https://example.org/plugins/")


def test_PluginsWidget_no_plugins():
    widget = mu.interface.dialogs.PluginsWidget()
    widget.setup({"plugins": [], "folder": "/p", "help_url": ""})
    assert widget.enabled_plugins() == {}
    assert "didn't find any plugins" in widget.summary.text()
    assert not widget.help_button.isEnabled()
    widget.open_folder_button.click()  # no way to open it: nothing happens


def test_AdminDialog_plugins_tab():
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    opener = mock.MagicMock()
    ad.setup(
        "log",
        {"envars": "", "locale": ""},
        "",
        _python_mode(),
        None,
        plugins=PLUGINS,
        open_directory=opener,
    )
    titles = [ad.tabs.tabText(i) for i in range(ad.tabs.count())]
    assert titles == ["Current Log", "Environment", "Plugins", "Select Language"]
    assert ad.plugins_tab.open_directory is opener
    assert ad.settings()["plugins"] == ad.plugins_tab.enabled_plugins()


def test_AdminDialog_focus_plugins():
    mode = mock.MagicMock()
    mode.uses_user_environment = False
    parent = QWidget()
    ad = mu.interface.dialogs.AdminDialog(parent)
    ad.setup("log", {"locale": ""}, "", mode, None, focus="plugins", plugins=PLUGINS)
    assert ad.tabs.currentWidget() is ad.plugins_tab
    assert "plugins" in ad.settings()


def test_PluginsWidget_columns_have_room(plugins_widget):
    """Each column fits its widest entry, with a gap before the next."""
    w = plugins_widget
    C = mu.interface.dialogs.PluginsWidget
    widest = max(
        w.tree.fontMetrics().horizontalAdvance(text) for text in cells(w, C.STATUS)
    )
    assert w.tree.columnWidth(C.STATUS) >= widest + C.COLUMN_GAP


def test_PluginsWidget_rows_fit_a_checkbox(plugins_widget):
    """The themes draw 16px checkboxes with a border: rows leave room."""
    tree = plugins_widget.tree
    assert tree.sizeHintForRow(0) >= 24


def test_PluginsWidget_switched_off_after_errors_this_session():
    """
    Switched off after errors earlier this session: still on until Nu
    restarts, and the details say why it will be off.
    """
    widget = mu.interface.dialogs.PluginsWidget()
    row = plugin_row(enabled=False, switched_off_after_errors=True)
    widget.setup({"plugins": [row], "folder": "/p", "help_url": ""})
    item = widget.tree.topLevelItem(0)
    assert item.text(widget.STATUS) == "On until you restart Nu"
    assert "kept having errors, so it will be off" in widget.summary.text()
    # Ticking it again keeps it on: no warning any more.
    item.setCheckState(widget.ON, Qt.CheckState.Checked)
    assert "kept having errors" not in widget.summary.text()
