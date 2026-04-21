"""Tests for task management tools."""

from unittest.mock import patch

import pytest

from nanocode.tools.task_tool import CreateTask, GetTask, ListTasks, UpdateTask


@pytest.fixture
def create_task():
    return CreateTask()


@pytest.fixture
def update_task():
    return UpdateTask()


@pytest.fixture
def get_task():
    return GetTask()


@pytest.fixture
def list_tasks():
    return ListTasks()


class TestCreateTask:
    def test_name(self, create_task):
        assert create_task.name() == "create_task"

    def test_execute_success(self, create_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.create_task.return_value = '{"id": "1", "description": "test"}'
            result = create_task.execute(description="test task")
            assert "1" in result
            mock_tm.create_task.assert_called_once_with("test task")

    def test_execute_empty_description(self, create_task):
        result = create_task.execute(description="")
        assert "No task description" in result


class TestUpdateTask:
    def test_name(self, update_task):
        assert update_task.name() == "update_task"

    def test_execute_success(self, update_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.update_task.return_value = '{"id": 1, "status": "completed"}'
            result = update_task.execute(task_id=1, status="completed")
            assert "completed" in result
            mock_tm.update_task.assert_called_once_with(1, "completed", [], [])

    def test_execute_with_dependencies(self, update_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.update_task.return_value = '{"id": 1}'
            result = update_task.execute(task_id=1, status="in_progress", add_blocked_by=[2, 3], add_blocks=[4])
            assert result == '{"id": 1}'
            mock_tm.update_task.assert_called_once_with(1, "in_progress", [2, 3], [4])

    def test_execute_no_task_id(self, update_task):
        result = update_task.execute(task_id=None, status="completed")
        assert "No task id" in result

    def test_execute_error(self, update_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.update_task.side_effect = ValueError("Task not found")
            result = update_task.execute(task_id=99, status="completed")
            assert "Error" in result
            assert "Task not found" in result


class TestGetTask:
    def test_name(self, get_task):
        assert get_task.name() == "get_task"

    def test_execute_success(self, get_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.get_task.return_value = '{"id": 1, "description": "test"}'
            result = get_task.execute(task_id=1)
            assert "test" in result
            mock_tm.get_task.assert_called_once_with(1)

    def test_execute_no_task_id(self, get_task):
        result = get_task.execute(task_id=None)
        assert "No task id" in result

    def test_execute_error(self, get_task):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.get_task.side_effect = ValueError("Task not found")
            result = get_task.execute(task_id=99)
            assert "Error" in result
            assert "Task not found" in result


class TestListTasks:
    def test_name(self, list_tasks):
        assert list_tasks.name() == "list_tasks"

    def test_execute(self, list_tasks):
        with patch("nanocode.core.task_manager") as mock_tm:
            mock_tm.list_tasks.return_value = "[]"
            result = list_tasks.execute()
            assert result == "[]"
            mock_tm.list_tasks.assert_called_once()
