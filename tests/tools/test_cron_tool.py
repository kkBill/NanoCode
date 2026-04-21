"""Tests for cron task tools."""

from unittest.mock import MagicMock, patch

import pytest

from nanocode.tools.cron_tool import CreateCron, DeleteCron


@pytest.fixture
def create_cron():
    return CreateCron()


@pytest.fixture
def delete_cron():
    return DeleteCron()


class TestCreateCron:
    def test_name(self, create_cron):
        assert create_cron.name() == "create_cron"

    def test_schema_structure(self, create_cron):
        schema = create_cron.schema()
        props = schema["function"]["parameters"]["properties"]
        assert "cron_expr" in props
        assert "trigger_mode" in props
        assert "persistent_mode" in props
        assert "prompt" in props

    def test_execute_success(self, create_cron):
        with patch("nanocode.core.cron_scheduler") as mock_cs:
            mock_task = MagicMock()
            mock_task.id = "cron-123"
            mock_cs.create_task.return_value = mock_task
            result = create_cron.execute(
                cron_expr="0 9 * * *",
                trigger_mode="repeat",
                persistent_mode="durable",
                prompt="test prompt",
            )
            assert "cron-123" in result
            assert "successfully" in result
            mock_cs.create_task.assert_called_once_with("0 9 * * *", "repeat", "durable", "test prompt")

    def test_execute_failure(self, create_cron):
        with patch("nanocode.core.cron_scheduler") as mock_cs:
            mock_cs.create_task.return_value = None
            result = create_cron.execute(
                cron_expr="0 9 * * *",
                trigger_mode="repeat",
                persistent_mode="durable",
                prompt="test prompt",
            )
            assert "Failed" in result


class TestDeleteCron:
    def test_name(self, delete_cron):
        assert delete_cron.name() == "delete_cron"

    def test_execute_success(self, delete_cron):
        with patch("nanocode.core.cron_scheduler") as mock_cs:
            mock_cs.delete_task.return_value = True
            result = delete_cron.execute(task_id="cron-123")
            assert "deleted successfully" in result
            mock_cs.delete_task.assert_called_once_with("cron-123")

    def test_execute_not_found(self, delete_cron):
        with patch("nanocode.core.cron_scheduler") as mock_cs:
            mock_cs.delete_task.return_value = False
            result = delete_cron.execute(task_id="cron-123")
            assert "not found" in result
