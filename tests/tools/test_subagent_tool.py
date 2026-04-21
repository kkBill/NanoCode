"""Tests for SubAgent tool."""

from unittest.mock import MagicMock, patch

import pytest

from nanocode.tools.subagent_tool import SubAgent


@pytest.fixture
def sub_agent():
    return SubAgent()


def test_sub_agent_name(sub_agent):
    assert sub_agent.name() == "sub_agent"


def test_sub_agent_schema_structure(sub_agent):
    schema = sub_agent.schema()
    assert schema["type"] == "function"
    assert "task" in schema["function"]["parameters"]["properties"]


def test_sub_agent_execute_empty_task(sub_agent):
    result = sub_agent.execute(task="")
    assert "No task" in result


def test_sub_agent_execute_success_no_tools(sub_agent):
    """Sub-agent finishes immediately with stop reason."""
    with patch("nanocode.tools.subagent_tool.load_dotenv"):
        with patch(
            "nanocode.tools.subagent_tool.os.getenv",
            side_effect=lambda k, default=None: {
                "OPENAI_API_KEY": "test_key",
                "OPENAI_BASE_URL": "http://test",
                "MODEL": "test-model",
            }.get(k, default),
        ):
            with patch("nanocode.tools.subagent_tool.OpenAIClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_message = MagicMock()
                mock_message.content = "Done"
                mock_message.reasoning_content = None

                mock_choice = MagicMock()
                mock_choice.finish_reason = "stop"
                mock_choice.message = mock_message

                mock_response = MagicMock()
                mock_response.choices = [mock_choice]
                mock_client.chat.return_value = mock_response

                result = sub_agent.execute(task="do something")
                assert result == "Done"


def test_sub_agent_execute_with_tool_call(sub_agent):
    """Sub-agent makes one tool call then stops."""
    with patch("nanocode.tools.subagent_tool.load_dotenv"):
        with patch(
            "nanocode.tools.subagent_tool.os.getenv",
            side_effect=lambda k, default=None: {
                "OPENAI_API_KEY": "test_key",
                "OPENAI_BASE_URL": "http://test",
                "MODEL": "test-model",
            }.get(k, default),
        ):
            with patch("nanocode.tools.subagent_tool.OpenAIClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                # First response: tool call
                tool_call = MagicMock()
                tool_call.id = "call_1"
                tool_call.type = "function"
                tool_call.function.name = "bash"
                tool_call.function.arguments = '{"command": "echo hi"}'

                first_message = MagicMock()
                first_message.content = ""
                first_message.reasoning_content = None

                first_choice = MagicMock()
                first_choice.finish_reason = "tool_calls"
                first_choice.message = first_message
                first_choice.message.tool_calls = [tool_call]

                first_response = MagicMock()
                first_response.choices = [first_choice]

                # Second response: stop
                second_message = MagicMock()
                second_message.content = "Finished"
                second_message.reasoning_content = None

                second_choice = MagicMock()
                second_choice.finish_reason = "stop"
                second_choice.message = second_message

                second_response = MagicMock()
                second_response.choices = [second_choice]

                mock_client.chat.side_effect = [first_response, second_response]

                with patch("nanocode.tools.registry") as mock_registry:
                    mock_tool = MagicMock()
                    mock_tool.execute.return_value = "hi"
                    mock_registry.list_tools_for_subagent.return_value = ["bash"]
                    mock_registry.get_tool.return_value = mock_tool

                    result = sub_agent.execute(task="call a tool")
                    assert result == "Finished"
                    mock_tool.execute.assert_called_once_with(command="echo hi")


def test_sub_agent_execute_unexpected_finish_reason(sub_agent):
    """Sub-agent handles unexpected finish reason gracefully."""
    with patch("nanocode.tools.subagent_tool.load_dotenv"):
        with patch(
            "nanocode.tools.subagent_tool.os.getenv",
            side_effect=lambda k, default=None: {
                "OPENAI_API_KEY": "test_key",
                "OPENAI_BASE_URL": "http://test",
                "MODEL": "test-model",
            }.get(k, default),
        ):
            with patch("nanocode.tools.subagent_tool.OpenAIClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client

                mock_message = MagicMock()
                mock_message.content = ""
                mock_message.reasoning_content = None

                mock_choice = MagicMock()
                mock_choice.finish_reason = "length"
                mock_choice.message = mock_message

                mock_response = MagicMock()
                mock_response.choices = [mock_choice]
                mock_client.chat.return_value = mock_response

                result = sub_agent.execute(task="do something")
                assert result == "Sub-agent finished without response."
