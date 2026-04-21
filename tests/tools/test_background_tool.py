"""Tests for background task tools."""

from unittest.mock import patch

import pytest

from nanocode.tools.background_tool import CheckBackgroundTask, RunBackgroundTask


@pytest.fixture
def run_bg():
    return RunBackgroundTask()


@pytest.fixture
def check_bg():
    return CheckBackgroundTask()


class TestRunBackgroundTask:
    def test_name(self, run_bg):
        assert run_bg.name() == "run_background_task"

    def test_execute_success(self, run_bg):
        with patch("nanocode.core.background_manager") as mock_bm:
            mock_bm.run.return_value = "task-123"
            result = run_bg.execute(command="sleep 10")
            assert "task-123" in result
            mock_bm.run.assert_called_once_with("sleep 10")

    def test_execute_empty_command(self, run_bg):
        result = run_bg.execute(command="")
        assert "No command" in result


class TestCheckBackgroundTask:
    def test_name(self, check_bg):
        assert check_bg.name() == "check_background_task"

    def test_execute_with_task_id(self, check_bg):
        with patch("nanocode.core.background_manager") as mock_bm:
            mock_bm.check_status.return_value = "Task: task-123, command: sleep 10, status: running"
            result = check_bg.execute(task_id="task-123")
            assert "running" in result
            mock_bm.check_status.assert_called_once_with("task-123")

    def test_execute_without_task_id(self, check_bg):
        with patch("nanocode.core.background_manager") as mock_bm:
            mock_bm.check_status.return_value = "All tasks listed"
            result = check_bg.execute(task_id=None)
            assert "All tasks listed" == result
            mock_bm.check_status.assert_called_once_with(None)
