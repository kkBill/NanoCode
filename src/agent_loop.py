from abc import ABC
import os
import subprocess
import json
from pathlib import Path
from openai import OpenAI


WORKDIR = Path(__file__).parent.parent.resolve() / "workspace"

# Initialize OpenAI client (via aliyun dashscope)
api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

client = OpenAI(api_key=api_key, base_url=base_url)


############################### Helper functions ###############################


def debug_print_messages(messages):
    print("-" * 40)
    output = json.dumps(messages, indent=2)
    print(output)
    print("-" * 40)


# 确保所有文件操作都在 WORKDIR 内进行，防止路径穿越攻击(Path Traversal Attack)
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    # 校验：最终路径必须在 WORKDIR 内部
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")

    return path


############################### Tools Definition ###############################


class Tool(ABC):
    def name(self) -> str:
        raise NotImplementedError

    def description(self) -> str:
        raise NotImplementedError

    def execute(self, **kwargs) -> str:
        raise NotImplementedError

    def schema(self) -> dict:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, tool: Tool):
        self.tools[tool.name()] = tool

    def get_tool(self, name: str):
        return self.tools.get(name, None)

    def get_all_schemas(self):
        return [tool.schema() for _, tool in self.tools.items()]

    def list_tools(self):
        return list(self.tools.keys())


class Bash(Tool):
    def name(self) -> str:
        return "bash"

    def description(self) -> str:
        return "Run a shell command."

    def execute(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        print(f"bash({command})")

        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return f"Error: Dangerous command {command} blocked"

        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            out = (r.stdout + r.stderr).strip()
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Timeout (120s)"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        }


class ReadFile(Tool):
    def name(self) -> str:
        return "read_file"

    def description(self) -> str:
        return "Read a file's content."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        print(f"read_file({path})")

        try:
            real_path = safe_path(path)
            content = real_path.read_text(encoding="utf-8")
            return content[:50000] if content else "(empty file)"
        except Exception as e:
            return f"Error: {str(e)}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {"filename": {"type": "string"}},
                    "required": ["filename"],
                },
            },
        }


class WriteFile(Tool):
    def name(self) -> str:
        return "write_file"

    def description(self) -> str:
        return "Write content to a file."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        content = kwargs.get("content", "")
        print(f"write_file({path}, content length={len(content)})")

        try:
            real_path = safe_path(path)
            real_path.write_text(content)
            return "File written successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["filename", "content"],
                },
            },
        }


############################### Agent Main Loop ###############################


registry = ToolRegistry()
registry.register(Bash())
registry.register(ReadFile())
registry.register(WriteFile())


def agent_loop(messages: list):

    while True:
        # print messages before sending to the model for better debugging
        debug_print_messages(messages)

        response = client.chat.completions.create(
            model="kimi-k2.5",
            messages=messages,
            tools=registry.get_all_schemas(),
            max_tokens=4096,
            temperature=0.7,
            extra_body={"enable_thinking": True},
        )

        message = response.choices[0].message

        # print the reasoning content if available for better understanding of the model's thought process
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            print("=" * 40)
            print("🤔 reasoning content:")
            print(message.reasoning_content)
            print("=" * 40)

        if response.choices[0].finish_reason == "tool_calls":
            tool_calls = response.choices[0].message.tool_calls
            for call in tool_calls:
                # we only have one tool, so we can directly check the name
                if call.function.name in registry.list_tools():
                    args = json.loads(call.function.arguments)
                    # print(f"Executing command: {args}")
                    output = registry.get_tool(call.function.name).execute(**args)
                    # Append the tool call and its output to messages for context
                    messages.append(
                        {
                            "role": "assistant",
                            "content": message.content,
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "type": "function",
                                    "function": {
                                        "name": call.function.name,
                                        "arguments": call.function.arguments,
                                    },
                                }
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "tool_name": call.function.name,
                            "content": output,
                        }
                    )
        elif response.choices[0].finish_reason == "stop":
            print("Final response:", response.choices[0].message.content)
            return response.choices[0].message.content
        else:
            print(f"Unexpected finish reason: {response.choices[0].finish_reason}")
            return f"Unexpected finish reason: {response.choices[0].finish_reason}"


if __name__ == "__main__":
    # query = 'Create a file called hello.py that prints "Hello, World!"'
    # query = "Create a directory called test_output and write 3 files in it"

    # query = "Create a file called greet.py with a greet(name) function"
    # agent_loop(query)

    # print(WORKDIR)
    # print(safe_path("hello.py"))
    # print(safe_path("../hello.py"))  # This should raise an error

    history = [
        {
            "role": "system",
            "content": f"You are a coding agent at {os.getcwd()}. Use available and appropriate tool to solve tasks. Act, don't explain.",
        }
    ]
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        print(f"\033[32ms02 << {response_content}\033[0m")
        print()
