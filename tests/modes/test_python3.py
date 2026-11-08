# -*- coding: utf-8 -*-
"""
Tests for the Python3 mode.
"""

import sys
import os
import asyncio
import zmq
from jupyter_client.manager import KernelManager
from mu.modes.python3 import PythonMode, KernelRunner, MuKernelManager
from mu.modes.api import PYTHON3_APIS, SHARED_APIS, PI_APIS
from mu.virtual_environment import venv

from unittest import mock


def test_mu_kernel_manager_uses_venv_interpreter():
    """
    The kernel command's interpreter is swapped for the user's venv
    interpreter when the kernel spec names a different one.
    """
    km = MuKernelManager()

    async def fake_pre_start(self, **kw):
        return ["/some/other/python", "-m", "ipykernel_launcher"], {"env": {}}

    with (
        mock.patch.object(KernelManager, "_async_pre_start_kernel", fake_pre_start),
        mock.patch("mu.modes.python3.venv") as mock_venv,
    ):
        mock_venv.interpreter = "/the/venv/bin/python"
        cmd, kw = asyncio.run(km._async_pre_start_kernel())
    assert cmd == ["/the/venv/bin/python", "-m", "ipykernel_launcher"]
    assert kw == {"env": {}}


def test_mu_kernel_manager_starts_real_kernel():
    """
    Regression (jupyter_client 8): actually start and stop a kernel through
    MuKernelManager. The old start_kernel override bypassed jupyter_client's
    provisioner-based start-up, leaving KernelManager.kernel as None, which
    crashed Nu as soon as the REPL button was pressed.
    """
    km = MuKernelManager()
    km.kernel_name = "python3"
    with mock.patch("mu.modes.python3.venv") as mock_venv:
        mock_venv.interpreter = sys.executable
        km.start_kernel()
    try:
        assert km.has_kernel
        assert km.is_alive()
        client = km.blocking_client()
        client.start_channels()
        try:
            client.wait_for_ready(timeout=60)
        finally:
            client.stop_channels()
        # The connection is encrypted (ipykernel's kernelspec declares
        # CurveZMQ support), so the kernel doesn't warn that it isn't.
        assert km.curve_publickey is not None
    finally:
        km.shutdown_kernel(now=True)
    assert not km.has_kernel


def test_mu_kernel_manager_encrypts_the_kernel_connection():
    """CurveZMQ keys are provisioned for kernels that say they support it."""
    assert MuKernelManager().transport_encryption == "auto"


def test_mu_kernel_manager_without_curve_support_in_pyzmq():
    """A pyzmq without CurveZMQ: the connection stays as it was."""
    with mock.patch("mu.modes.python3.zmq.has", return_value=False):
        assert MuKernelManager().transport_encryption == "disabled"


def test_mu_kernel_manager_with_an_older_jupyter_client():
    """jupyter_client before 8.9 has no transport_encryption: nothing's set."""
    with (
        mock.patch.object(MuKernelManager, "class_trait_names", return_value=[]),
        mock.patch("mu.modes.python3.zmq.has") as has,
    ):
        km = MuKernelManager()
    has.assert_not_called()
    assert km.transport_encryption == "disabled"


def test_kernel_runner_start_kernel():
    """
    Ensure the start_kernel method eventually emits the kernel_started signal
    with the associated kernel manager and kernel client objects for
    subsequent use.
    """
    mock_kernel_manager = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_kernel_manager.client.return_value = mock_client
    envars = [["name", "value"]]
    kr = KernelRunner(
        kernel_name=sys.executable, cwd="/a/path/to/mu_code", envars=envars
    )
    kr.kernel_started = mock.MagicMock()
    mock_os = mock.MagicMock()
    mock_os.environ = {}
    mock_os.pathsep = os.pathsep
    mock_os.path.dirname.return_value = (
        "/Applications/mu-editor.app/Contents/Resources/app/mu"
    )
    mock_kernel_manager_class = mock.MagicMock()
    mock_kernel_manager_class.return_value = mock_kernel_manager
    mock_venv = mock.MagicMock()
    mock_venv.activation_vars.return_value = {
        "VIRTUAL_ENV": "/the/venv",
        "PATH": "/the/venv/bin:SYS",
    }
    with (
        mock.patch("mu.modes.python3.os", mock_os),
        mock.patch("mu.modes.python3.MuKernelManager", mock_kernel_manager_class),
        mock.patch("mu.modes.python3.venv", mock_venv),
        mock.patch("sys.platform", "darwin"),
    ):
        kr.start_kernel()
    mock_os.chdir.assert_called_once_with("/a/path/to/mu_code")
    # The user's venv is activated into the kernel's environment...
    assert mock_os.environ["VIRTUAL_ENV"] == "/the/venv"
    assert mock_os.environ["PATH"] == "/the/venv/bin:SYS"
    # ...and user-defined envars still take precedence.
    assert mock_os.environ["name"] == "value"
    assert kr.repl_kernel_manager == mock_kernel_manager
    mock_kernel_manager_class.assert_called_once_with()
    mock_kernel_manager.start_kernel.assert_called_once_with()
    assert kr.repl_kernel_client == mock_client
    kr.kernel_started.emit.assert_called_once_with(mock_kernel_manager, mock_client)


def test_kernel_runner_stop_kernel():
    """
    Ensure the stop_kernel method eventually emits the kernel_finished
    signal once it has stopped the client communication channels and shutdown
    the kernel in the quickest way possible.
    """
    envars = [["name", "value"]]
    kr = KernelRunner(
        kernel_name=sys.executable, cwd="/a/path/to/mu_code", envars=envars
    )
    kr.repl_kernel_client = mock.MagicMock()
    kr.repl_kernel_manager = mock.MagicMock()
    kr.kernel_finished = mock.MagicMock()
    mock_os = mock.MagicMock()
    mock_os.environ = {"old_mu_context": "to_be_deleted"}
    with mock.patch("mu.modes.python3.os", mock_os):
        kr.stop_kernel()
    assert "old_mu_context" not in mock_os.environ
    assert len(mock_os.environ) == len(kr.default_envars)
    kr.repl_kernel_client.stop_channels.assert_called_once_with()
    kr.repl_kernel_manager.shutdown_kernel.assert_called_once_with(now=True)
    kr.kernel_finished.emit.assert_called_once_with()


def test_python_mode():
    """
    Sanity check for setting up of the mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    assert pm.name == "Python 3"
    assert pm.description is not None
    assert pm.icon == "python"
    assert pm.is_debugger is False
    assert pm.uses_user_environment is True
    assert pm.editor == editor
    assert pm.view == view

    with mock.patch("mu.modes.python3.CHARTS", True):
        actions = pm.actions()
    assert len(actions) == 4
    assert actions[0]["name"] == "run"
    assert actions[0]["handler"] == pm.run_toggle
    assert actions[1]["name"] == "debug"
    assert actions[1]["handler"] == pm.debug
    assert actions[2]["name"] == "repl"
    assert actions[2]["handler"] == pm.toggle_repl
    assert actions[3]["name"] == "plotter"
    assert actions[3]["handler"] == pm.toggle_plotter


def test_python_mode_no_charts():
    """
    If QCharts is not available, ensure the plotter feature is not available.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    assert pm.name == "Python 3"
    assert pm.description is not None
    assert pm.icon == "python"
    assert pm.is_debugger is False
    assert pm.editor == editor
    assert pm.view == view

    with mock.patch("mu.modes.python3.CHARTS", False):
        actions = pm.actions()
    assert len(actions) == 3
    assert actions[0]["name"] == "run"
    assert actions[0]["handler"] == pm.run_toggle
    assert actions[1]["name"] == "debug"
    assert actions[1]["handler"] == pm.debug
    assert actions[2]["name"] == "repl"
    assert actions[2]["handler"] == pm.toggle_repl


def test_python_api():
    """
    Make sure the API definition is as expected.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    result = pm.api()
    assert result == SHARED_APIS + PYTHON3_APIS + PI_APIS


def test_python_run_toggle_on():
    """
    Check the handler for clicking run starts the new process and updates the
    UI state.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.button_bar.slots = {
        "debug": mock.MagicMock(),
        "modes": mock.MagicMock(),
        "run": mock.MagicMock(),
    }
    pm = PythonMode(editor, view)
    pm.runner = None

    def runner(pm=pm):
        pm.runner = True

    pm.run_script = mock.MagicMock(side_effect=runner)
    pm.run_toggle(None)
    pm.run_script.assert_called_once_with()
    slot = pm.view.button_bar.slots["run"]
    assert slot.setIcon.call_count == 1
    slot.setText.assert_called_once_with("Stop")
    slot.setToolTip.assert_called_once_with("Stop your Python script.")
    pm.view.button_bar.slots["debug"].setEnabled.assert_called_once_with(False)
    pm.view.button_bar.slots["modes"].setEnabled.assert_called_once_with(False)


def test_python_run_toggle_on_cancelled():
    """
    Ensure the button states are correct if running an unsaved script is
    cancelled before the process is allowed to start. See issue #338.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.runner = None
    pm.run_script = mock.MagicMock()
    pm.run_toggle(None)
    pm.run_script.assert_called_once_with()
    slot = pm.view.button_bar.slots["run"]
    assert slot.setIcon.call_count == 0


def test_python_run_toggle_off():
    """
    Check the handler for clicking run stops the process and reverts the UI
    state.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.button_bar.slots = {
        "debug": mock.MagicMock(),
        "modes": mock.MagicMock(),
        "run": mock.MagicMock(),
    }
    pm = PythonMode(editor, view)
    pm.runner = True
    pm.stop_script = mock.MagicMock()
    pm.run_toggle(None)
    pm.stop_script.assert_called_once_with()
    slot = pm.view.button_bar.slots["run"]
    assert slot.setIcon.call_count == 1
    slot.setText.assert_called_once_with("Run")
    slot.setToolTip.assert_called_once_with("Run your Python script.")
    pm.view.button_bar.slots["debug"].setEnabled.assert_called_once_with(True)
    pm.view.button_bar.slots["modes"].setEnabled.assert_called_once_with(True)


def test_python_run_script():
    """
    Ensure that running the script launches the process as expected.
    """
    editor = mock.MagicMock()
    editor.envars = [["name", "value"]]
    view = mock.MagicMock()
    view.current_tab.path = "/foo/bar"
    view.current_tab.isModified.return_value = True
    view.current_tab.text = mock.MagicMock(return_value="abc")
    mock_runner = mock.MagicMock()
    view.add_python3_runner.return_value = mock_runner
    pm = PythonMode(editor, view)
    with mock.patch.object(venv, "interpreter", "interpreter"):
        pm.run_script()

    editor.save_tab_to_file.assert_called_once_with(view.current_tab)
    view.add_python3_runner.assert_called_once_with(
        interpreter="interpreter",
        script_name="/foo/bar",
        working_directory="/foo",
        interactive=True,
        envars=editor.envars,
    )
    mock_runner.process.waitForStarted.assert_called_once_with()
    # Check the buttons are set to the correct state when other aspects of the
    # mode are also in play.
    pm.set_buttons = mock.MagicMock()
    pm.kernel_runner = True
    pm.run_script()
    pm.set_buttons.assert_called_once_with(plotter=False)
    pm.set_buttons.reset_mock()
    pm.kernel_runner = False
    pm.plotter = True
    pm.run_script()
    pm.set_buttons.assert_called_once_with(repl=False)


def test_python_run_script_no_editor():
    """
    If there's no active tab, there can be no runner either.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.current_tab = None
    pm = PythonMode(editor, view)
    pm.stop_script = mock.MagicMock()
    pm.run_script()
    assert pm.runner is None
    pm.stop_script.assert_called_once_with()


def test_python_run_script_needs_saving():
    """
    If the file hasn't been saved yet (it's unnamed), prompt the user to save
    it.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.current_tab.path = None
    pm = PythonMode(editor, view)
    pm.stop_script = mock.MagicMock()
    pm.run_script()
    editor.save.assert_called_once_with()


def test_python_run_script_uses_editor_save():
    """The run code uses the common editor save code, invoking
    encoding checks and useful messages
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.current_tab.IsModified.return_value = True
    view.current_tab.path = "foo"
    view.current_tab.text = mock.MagicMock(return_value="foo")
    pm = PythonMode(editor, view)
    pm.stop_script = mock.MagicMock()
    pm.run_script()
    editor.save_tab_to_file.assert_called_once_with(view.current_tab)


def test_python_stop_script():
    """
    Check that the child process is killed, the runner cleaned up and UI
    is reset.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    mock_runner = mock.MagicMock()
    pm.runner = mock_runner
    pm.stop_script()
    mock_runner.stop_process.assert_called_once_with()
    assert pm.runner is None


def test_python_stop_resets_focus():
    """
    Check that, when a child process is killed, the current
    tab regains focus.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    mock_runner = mock.MagicMock()
    pm.runner = mock_runner
    pm.stop_script()
    view.current_tab.setFocus.assert_called_once_with()


def test_python_stop_script_no_runner():
    """
    If the script is cancelled before the child process is created ensure
    nothing breaks and the UI is reset.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.runner = None
    pm.stop_script()
    view.remove_python_runner.assert_called_once_with()


def test_python_debug():
    """
    Ensure Python3 mode hands over running of the script to the debug mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.debug(None)
    editor.change_mode.assert_called_once_with("debugger")
    assert editor.mode == "debugger"
    editor.modes["debugger"].start.assert_called_once_with()


def test_python_toggle_repl():
    """
    Ensure the REPL handling works as expected.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.add_repl = mock.MagicMock()
    pm.remove_repl = mock.MagicMock()
    pm.toggle_repl(None)
    pm.add_repl.assert_called_once_with()
    pm.kernel_runner = True
    pm.toggle_repl(None)
    pm.remove_repl.assert_called_once_with()


def test_python_add_repl():
    """
    Check the REPL's kernel manager is configured correctly before being handed
    to the Jupyter widget in the view.
    """
    mock_qthread = mock.MagicMock()
    mock_kernel_runner = mock.MagicMock()
    editor = mock.MagicMock()
    editor.envars = [["name", "value"]]
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    pm.stop_kernel = mock.MagicMock()
    with (
        mock.patch("mu.modes.python3.QThread", mock_qthread),
        mock.patch("mu.modes.python3.KernelRunner", mock_kernel_runner),
        mock.patch.object(venv, "name", "name"),
    ):
        pm.add_repl()
    mock_qthread.assert_called_once_with()
    mock_kernel_runner.assert_called_once_with(
        kernel_name="name", cwd=pm.workspace_dir(), envars=editor.envars
    )
    assert pm.kernel_thread == mock_qthread()
    assert pm.kernel_runner == mock_kernel_runner()
    pm.set_buttons.assert_called_once_with(repl=False)
    pm.kernel_runner.moveToThread.assert_called_once_with(pm.kernel_thread)
    pm.kernel_runner.kernel_started.connect.assert_called_once_with(pm.on_kernel_start)
    pm.kernel_runner.kernel_finished.connect.assert_called_once_with(
        pm.kernel_thread.quit
    )
    pm.stop_kernel.connect.assert_called_once_with(pm.kernel_runner.stop_kernel)
    pm.kernel_thread.started.connect.assert_called_once_with(
        pm.kernel_runner.start_kernel
    )
    pm.kernel_thread.finished.connect.assert_called_once_with(pm.on_kernel_stop)
    pm.kernel_thread.start.assert_called_once_with()


def test_python_remove_repl():
    """
    Make sure the REPL is removed properly.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    pm.stop_kernel = mock.MagicMock()
    pm.remove_repl()
    pm.stop_kernel.emit.assert_called_once_with()
    pm.set_buttons.assert_called_once_with(repl=False)


def test_python_remove_repl_reset_focus():
    """
    Make sure the REPL is removed properly.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    pm.stop_kernel = mock.MagicMock()
    pm.remove_repl()
    pm.stop_kernel.emit.assert_called_once_with()
    pm.set_buttons.assert_called_once_with(repl=False)
    view.current_tab.setFocus.assert_called_once_with()


def test_python_toggle_plotter():
    """
    Ensure toggling the plotter causes it to be added/removed.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.add_plotter = mock.MagicMock()
    pm.remove_plotter = mock.MagicMock()
    pm.toggle_plotter()
    pm.add_plotter.assert_called_once_with()
    pm.plotter = True
    pm.toggle_plotter()
    pm.remove_plotter.assert_called_once_with()


def test_python_add_plotter():
    """
    Ensure the plotter is added as expected.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    pm.add_plotter()
    view.add_python3_plotter.assert_called_once_with(pm)
    assert pm.plotter
    pm.set_buttons.assert_called_once_with(debug=False)
    # Check button states are updated depending on other aspects of the mode
    # being enabled.
    # REPL active.
    pm.set_buttons.reset_mock()
    pm.repl = True
    pm.add_plotter()
    assert pm.set_buttons.call_count == 2
    assert pm.set_buttons.call_args_list[0][1]["debug"] is False
    assert pm.set_buttons.call_args_list[1][1]["run"] is False
    # Runner active.
    pm.set_buttons.reset_mock()
    pm.repl = False
    pm.runner = True
    pm.add_plotter()
    assert pm.set_buttons.call_count == 2
    assert pm.set_buttons.call_args_list[0][1]["debug"] is False
    assert pm.set_buttons.call_args_list[1][1]["repl"] is False


def test_python_remove_plotter():
    """
    Ensure the button states are returned to normal before calling super
    method.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    with mock.patch("builtins.super") as mock_super:
        pm.remove_plotter()
        pm.set_buttons.assert_called_once_with(run=True, repl=True, debug=True)
        mock_super().remove_plotter.assert_called_once_with()


def test_python_remove_plotter_reset_focus():
    """
    Ensure the button states are returned to normal before calling super
    method.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.remove_plotter()
    view.current_tab.setFocus.assert_called_once_with()


def test_python_on_data_flood():
    """
    Ensure that Python 3 mode cleans up correctly after a data flood of the
    plotter is detected: reset the buttons, stop either the REPL or runner and
    then call the base method.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    pm.run_toggle = mock.MagicMock()
    pm.remove_repl = mock.MagicMock()
    pm.runner = True
    with mock.patch("builtins.super") as mock_super:
        pm.on_data_flood()
        pm.set_buttons.assert_called_once_with(run=True, repl=True, debug=True)
        pm.run_toggle.assert_called_once_with(None)
        mock_super().on_data_flood.assert_called_once_with()
    pm.set_buttons.reset_mock()
    pm.runner = False
    pm.kernel_runner = True
    with mock.patch("builtins.super") as mock_super:
        pm.on_data_flood()
        pm.set_buttons.assert_called_once_with(run=True, repl=True, debug=True)
        pm.remove_repl.assert_called_once_with()
        mock_super().on_data_flood.assert_called_once_with()


def test_python_on_kernel_start():
    """
    Ensure the handler for when the kernel has started updates the UI such that
    the kernel manager and kernel client are used to add the Jupyter widget to
    the UI, the REPL button is re-enabled and a status update is shown.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PythonMode(editor, view)
    pm.set_buttons = mock.MagicMock()
    mock_kernel_manager = mock.MagicMock()
    mock_client = mock.MagicMock()
    pm.on_kernel_start(mock_kernel_manager, mock_client)
    view.add_jupyter_repl.assert_called_once_with(mock_kernel_manager, mock_client)
    pm.set_buttons.assert_called_once_with(repl=True)
    editor.show_status_message.assert_called_once_with("REPL started.")
    # Check button states are set according to what other aspects of the mode
    # are currently enabled.
    # With Runner enabled.
    pm.set_buttons.reset_mock()
    pm.runner = True
    pm.on_kernel_start(mock_kernel_manager, mock_client)
    assert pm.set_buttons.call_count == 2
    assert pm.set_buttons.call_args_list[0][1]["repl"] is True
    assert pm.set_buttons.call_args_list[1][1]["plotter"] is False
    # With Plotter enabled.
    pm.set_buttons.reset_mock()
    pm.runner = False
    pm.plotter = True
    pm.on_kernel_start(mock_kernel_manager, mock_client)
    assert pm.set_buttons.call_count == 2
    assert pm.set_buttons.call_args_list[0][1]["repl"] is True
    assert pm.set_buttons.call_args_list[1][1]["run"] is False
    assert pm.set_buttons.call_args_list[1][1]["debug"] is False


def test_python_on_kernel_stop():
    """
    Ensure everything REPL based is cleaned up when this handler is called.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.button_bar.slots = {"repl": mock.MagicMock()}
    pm = PythonMode(editor, view)
    pm.on_kernel_stop()
    assert pm.repl_kernel_manager is None
    view.button_bar.slots["repl"].setEnabled.assert_called_once_with(True)
    editor.show_status_message.assert_called_once_with("REPL stopped.")
    assert pm.kernel_runner is None


#
# PEP 723: a file with a `# /// script` block runs with `uv run` (Phase 4b)
#
COWSAY = '# /// script\n# dependencies = ["cowsay"]\n# ///\nimport cowsay\n'


def _uv_record():
    from mu.command_log import CommandLog

    return CommandLog().start(
        ["/opt/uv", "run", "--python", "/env/bin/python", "--script", "/foo/cow.py"],
        cwd="/foo",
    )


def _pep723_mode(text=COWSAY):
    editor = mock.MagicMock()
    editor.envars = {"NAME": "value"}
    view = mock.MagicMock()
    view.current_tab.path = "/foo/cow.py"
    view.current_tab.isModified.return_value = False
    view.current_tab.text.return_value = text
    return PythonMode(editor, view), editor, view


def test_python_run_script_with_inline_metadata():
    """Run uses `uv run --python <env> --script <file>`, so the inline
    dependencies resolve, and the pane's first line is that command."""
    pm, editor, view = _pep723_mode()
    record = _uv_record()
    with (
        mock.patch.object(venv, "script_command", return_value=record) as command,
        mock.patch("mu.command_log.sys.platform", "linux"),
    ):
        pm.run_script()
    command.assert_called_once_with("/foo/cow.py", "/foo")
    view.add_python3_runner.assert_called_once_with(
        interpreter="/opt/uv",
        script_name="/foo/cow.py",
        working_directory="/foo",
        interactive=False,
        envars=editor.envars,
        python_args=["run", "--python", "/env/bin/python", "--script"],
        echo="$ uv run --python /env/bin/python --script /foo/cow.py",
    )
    runner = view.add_python3_runner.return_value
    assert pm.runner is runner
    runner.process.finished.connect.assert_called_once()
    runner.process.waitForStarted.assert_called_once_with()


def test_python_run_script_with_malformed_inline_metadata():
    """A broken block still runs via uv, whose error explains it."""
    pm, editor, view = _pep723_mode("# /// script\n# dependencies = [\nprint(1)\n")
    with mock.patch.object(venv, "script_command", return_value=_uv_record()):
        pm.run_script()
    assert view.add_python3_runner.call_args.kwargs["interpreter"] == "/opt/uv"


def test_python_run_script_with_inline_metadata_but_no_uv():
    """Without uv, explain (in beginner terms) instead of running."""
    from mu.virtual_environment import UvNotFound

    pm, editor, view = _pep723_mode()
    with mock.patch.object(venv, "script_command", side_effect=UvNotFound()):
        pm.run_script()
    view.add_python3_runner.assert_not_called()
    assert pm.runner is None
    message, information = view.show_message.call_args[0]
    assert "uv" in message
    assert "# /// script" in information


def test_python_run_toggle_without_uv_leaves_run_button():
    from mu.virtual_environment import UvNotFound

    pm, editor, view = _pep723_mode()
    pm.set_buttons = mock.MagicMock()
    with mock.patch.object(venv, "script_command", side_effect=UvNotFound()):
        pm.run_toggle(None)
    pm.set_buttons.assert_not_called()


def _finished(pm, runner, record, code=0, normal=True):
    from PyQt6.QtCore import QProcess

    status = QProcess.ExitStatus.NormalExit if normal else QProcess.ExitStatus.CrashExit
    pm.on_uv_run_finished(runner, record, code, status)


def test_on_uv_run_finished_records_exit_code():
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=False)
    runner.toPlainText.return_value = "$ uv run\nmoo\n"
    pm.runner = runner
    record = _uv_record()
    _finished(pm, runner, record, code=0)
    assert record.finished and record.exit_code == 0
    runner.insert_hint.assert_not_called()


def test_on_uv_run_finished_stopped_has_no_exit_code():
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=False)
    runner.toPlainText.return_value = ""
    pm.runner = runner
    record = _uv_record()
    _finished(pm, runner, record, code=15, normal=False)
    assert record.finished and record.exit_code is None


def test_on_uv_run_finished_adds_hint_for_uv_errors():
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=False)
    runner.toPlainText.return_value = (
        "$ uv run\nerror: Request failed after 3 retries\n  cause: Failed to fetch"
    )
    pm.runner = runner
    _finished(pm, runner, _uv_record(), code=2)
    (hint,), _ = runner.insert_hint.call_args
    assert hint.startswith("Hint: ") and "internet" in hint


def test_on_uv_run_finished_waits_for_the_last_output():
    """The pane may still be reading the end of the output when the process
    finishes; the hint waits for it."""
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=True)
    runner.toPlainText.return_value = "error: TOML parse error at line 1"
    pm.runner = runner
    with mock.patch("mu.modes.python3.QTimer") as timer:
        _finished(pm, runner, _uv_record(), code=2)
        runner.insert_hint.assert_not_called()
        delay, retry = timer.singleShot.call_args[0]
        runner.reading_stdout = False
        retry()
    runner.insert_hint.assert_called_once()


def test_on_uv_run_finished_gives_up_waiting():
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=True)
    runner.toPlainText.return_value = "error: TOML parse error"
    pm.runner = runner
    with mock.patch("mu.modes.python3.QTimer") as timer:
        pm.show_uv_hint(runner, attempts=0)
    timer.singleShot.assert_not_called()
    runner.insert_hint.assert_called_once()


def test_on_uv_run_finished_after_stop():
    """If the learner stopped the program (its pane is gone), no hint."""
    pm, editor, view = _pep723_mode()
    runner = mock.MagicMock(reading_stdout=False)
    runner.toPlainText.return_value = "error: TOML parse error"
    pm.runner = None
    record = _uv_record()
    _finished(pm, runner, record, code=2)
    assert record.finished
    runner.insert_hint.assert_not_called()


def test_mu_kernel_manager_client_gets_curve_keys_as_bytes():
    """
    jupyter_client 8.9 hands the client the keys as str, which its traits
    refuse: they're encoded first (as 8.10 does), and the client is created.
    """
    km = MuKernelManager()
    info = {"curve_publickey": "public", "curve_secretkey": "secret", "ip": "x"}
    with (
        mock.patch.object(km, "get_connection_info", return_value=info),
        mock.patch.object(KernelManager, "client") as client,
    ):
        km.client(extra=1)
    client.assert_called_once_with(
        extra=1, curve_publickey=b"public", curve_secretkey=b"secret"
    )


def test_mu_kernel_manager_client_without_curve_keys():
    """No encryption (or keys already bytes): nothing extra is passed."""
    km = MuKernelManager()
    with (
        mock.patch.object(km, "get_connection_info", return_value={"ip": "x"}),
        mock.patch.object(KernelManager, "client") as client,
    ):
        km.client()
    client.assert_called_once_with()


def test_mu_kernel_manager_real_client():
    """The real client() accepts the keys once a kernel has them."""
    km = MuKernelManager()
    km.curve_publickey, km.curve_secretkey = zmq.curve_keypair()
    client = km.client()
    assert client.curve_publickey == km.curve_publickey
