"""Tests for LoadSkill tool."""

from unittest.mock import patch

import pytest

from nanocode.tools.skill_tool import LoadSkill


@pytest.fixture
def load_skill():
    return LoadSkill()


def test_load_skill_name(load_skill):
    assert load_skill.name() == "load_skill"


def test_load_skill_schema_structure(load_skill):
    schema = load_skill.schema()
    assert schema["type"] == "function"
    assert "skill_name" in schema["function"]["parameters"]["properties"]


def test_load_skill_execute_success(load_skill):
    with patch("nanocode.core.skill_loader") as mock_loader:
        mock_loader.load_instructions.return_value = "instructions here"
        result = load_skill.execute(skill_name="test_skill")
        assert result == "instructions here"
        mock_loader.load_instructions.assert_called_once_with("test_skill")


def test_load_skill_execute_empty_name(load_skill):
    result = load_skill.execute(skill_name="")
    assert "No skill name" in result
