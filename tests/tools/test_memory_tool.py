"""Tests for memory management tools."""

from unittest.mock import patch

import pytest

from nanocode.tools.memory_tool import ListMemories, SaveMemory


@pytest.fixture
def save_memory():
    return SaveMemory()


@pytest.fixture
def list_memories():
    return ListMemories()


class TestSaveMemory:
    def test_name(self, save_memory):
        assert save_memory.name() == "save_memory"

    def test_execute_success(self, save_memory):
        with patch("nanocode.core.memory_manager") as mock_mm:
            mock_mm.save_memory.return_value = True
            result = save_memory.execute(
                name="pref",
                type="user",
                description="user preference",
                content="likes dark mode",
            )
            assert "saved successfully" in result
            mock_mm.save_memory.assert_called_once_with("pref", "user", "user preference", "likes dark mode")

    def test_execute_failure(self, save_memory):
        with patch("nanocode.core.memory_manager") as mock_mm:
            mock_mm.save_memory.return_value = False
            result = save_memory.execute(
                name="pref",
                type="user",
                description="user preference",
                content="likes dark mode",
            )
            assert "Failed" in result

    def test_execute_missing_name(self, save_memory):
        result = save_memory.execute(name="", type="user", description="desc")
        assert "Error" in result
        assert "required" in result

    def test_execute_missing_type(self, save_memory):
        result = save_memory.execute(name="pref", type="", description="desc")
        assert "Error" in result

    def test_execute_missing_description(self, save_memory):
        result = save_memory.execute(name="pref", type="user", description="")
        assert "Error" in result


class TestListMemories:
    def test_name(self, list_memories):
        assert list_memories.name() == "list_memories"

    def test_execute(self, list_memories):
        with patch("nanocode.core.memory_manager") as mock_mm:
            mock_mm.list_memories.return_value = "- pref [user]: user preference"
            result = list_memories.execute()
            assert "pref" in result
            mock_mm.list_memories.assert_called_once()
