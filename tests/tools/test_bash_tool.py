"""Tests for Bash tool."""

import subprocess
from unittest.mock import patch

import pytest

from nanocode.tools.bash_tool import Bash


@pytest.fixture
def bash():
    return Bash()


def test_bash_name(bash):
    assert bash.name() == "bash"


def test_bash_schema_structure(bash):
    schema = bash.schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "bash"
    assert "command" in schema["function"]["parameters"]["properties"]


def test_bash_execute_echo(bash):
    result = bash.execute(command="echo hello")
    assert "hello" in result


def test_bash_execute_empty_command(bash):
    result = bash.execute(command="")
    assert result == "(no output)"


def test_bash_execute_dangerous_rm(bash):
    result = bash.execute(command="rm -rf /")
    assert "blocked" in result


def test_bash_execute_dangerous_sudo(bash):
    result = bash.execute(command="sudo ls")
    assert "blocked" in result


def test_bash_execute_dangerous_shutdown(bash):
    result = bash.execute(command="shutdown now")
    assert "blocked" in result


def test_bash_execute_timeout(bash):
    with patch("nanocode.tools.bash_tool.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 1000", timeout=120)
        result = bash.execute(command="sleep 1000")
        assert "Timeout" in result


def test_bash_execute_error_code(bash):
    with patch("nanocode.tools.bash_tool.subprocess.run") as mock_run:
        mock_process = mock_run.return_value
        mock_process.stdout = ""
        mock_process.stderr = "error msg"
        mock_process.returncode = 1
        result = bash.execute(command="false")
        assert "error msg" in result
