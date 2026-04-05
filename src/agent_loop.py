from abc import ABC
import re
import yaml
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
    # for better readability, trucate long content in messages
    truncated = []
    for msg in messages:
        content = msg["content"]
        if len(content) > 200:
            content = content[:100] + "...(truncated)"
        if "tool_calls" in msg:
            tool_calls_truncated = []
            for call in msg["tool_calls"]:
                call_truncated = {**call}
                if "arguments" in call["function"]:
                    args = call["function"]["arguments"]
                    if len(args) > 200:
                        call_truncated["function"]["arguments"] = (
                            args[:200] + "...(truncated)"
                        )
                tool_calls_truncated.append(call_truncated)

        new_msg = {**msg, "content": content}
        if "tool_calls" in msg:
            new_msg = {**msg, "content": content, "tool_calls": tool_calls_truncated}

        truncated.append(new_msg)
    output = json.dumps(truncated, indent=2)
    print(output)
    print("-" * 40)


# 确保所有文件操作都在 WORKDIR 内进行，防止路径穿越攻击(Path Traversal Attack)
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    # 校验：最终路径必须在 WORKDIR 内部
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")

    return path


############################### Skill ###############################


class SkillLoader:
    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir

    # load skill by name
    def load_skill(self, name: str) -> str | None:
        # 1. check if skill file exists
        skill_path = self.skill_dir / f"{name}/SKILL.md"
        if not skill_path.exists():
            return None
        # 2. if exists, read and return content (instructions for the skill)
        return skill_path.read_text(encoding="utf-8")

    def load_instructions(self, name: str) -> str:
        content = self.load_skill(name)
        if not content:
            return f"Skill {name} not found."

        # 提取元数据块之外的内容作为指令文本
        pattern = r"^---\n(.*?)\n---\n?(.*)$"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

        if not match:
            return content.strip()  # 如果没有元数据块，返回整个内容

        instructions = match.group(2).strip()
        return instructions

    def load_metadata(self, name: str) -> dict:
        content = self.load_skill(name)
        if not content:
            return {}

        # 匹配文件开头的 --- ... --- 元数据块
        pattern = r"^---\n(.*?)\n---"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

        if not match:
            return {}

        # 提取元数据文本并 YAML 解析（最优雅）
        metadata_text = match.group(1)
        metadata = yaml.safe_load(metadata_text)

        return metadata

    # list all available skills (skill name + description)
    def list_skills(self) -> str:
        # 1. scan skill_dir for subdirectories, each subdirectory is a skill
        skills = []
        for item in self.skill_dir.iterdir():
            if not item.is_dir():
                continue
            # 2. check if SKILL.md exists in the subdirectory
            skill_file = item / "SKILL.md"
            if not skill_file.exists():
                continue

            name = item.name
            metadata = self.load_metadata(name)
            description = metadata.get("description", "No description available.")
            skills.append(f"{name}: {description}")

        return "\n".join(skills)


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

    def get_schemas_for_subagent(self):
        # sub-agent doesn't need `sub_agent` tool to avoid infinite recursion, but can use all other tools
        return [
            tool.schema() for name, tool in self.tools.items() if name != "sub_agent"
        ]

    def list_tools(self):
        return list(self.tools.keys())

    def list_tools_for_subagent(self):
        return [name for name in self.tools.keys() if name != "sub_agent"]


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


class Todo(Tool):
    def __init__(self) -> None:
        # List of dicts: {"task_id": int, "task_description": str, "task_status": "pending" | "in_progress" | "completed"}
        self.tasks = []

    def name(self) -> str:
        return "todo"

    def description(self) -> str:
        return "Update task list. Track progress on multi-step tasks. Use 'in_progress' status before starting a task, 'pending' when waiting, and 'completed' when done."

    def execute(self, **kwargs) -> str:
        items = kwargs.get("items", [])
        print(f"todo(items={items})")

        if len(items) > 20:
            raise ValueError("Too many tasks! Please limit to 20")

        validated = []
        in_progress_count = 0  # only allow 1 task in progress at a time

        for i, item in enumerate(items, start=1):
            id = str(item.get("task_id", str(i)))  # default to index if no id provided
            description = str(item.get("task_description", "")).strip()
            status = str(item.get("task_status", "pending")).lower()

            # basic validation
            if not description:
                raise ValueError(f"Task {id} has empty description")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Task {id} has invalid status: {status}")
            if status == "in_progress":
                in_progress_count += 1
                if in_progress_count > 1:
                    raise ValueError(
                        f"Only one task can be in_progress at a time (task {id})"
                    )

            # if all good, add to validated list
            validated.append(
                {"task_id": id, "task_description": description, "task_status": status}
            )

        self.tasks = validated
        return self.render()

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "task_id": {"type": "string"},
                                    "task_description": {"type": "string"},
                                    "task_status": {
                                        "type": "string",
                                        "enum": ["pending", "in_progress", "completed"],
                                    },
                                },
                                "required": [
                                    "task_id",
                                    "task_description",
                                    "task_status",
                                ],
                            },
                        }
                    },
                    "required": ["items"],
                },
            },
        }

    def render(self) -> str:
        if not self.tasks:
            return "No tasks yet."
        lines = []
        for task in self.tasks:
            # [in_progress] task 1: xxxxx
            lines.append(
                f"[{task['task_status']}] task #{task['task_id']}: {task['task_description']}"
            )
        return "\n".join(lines)


class SubAgent(Tool):
    def name(self) -> str:
        return "sub_agent"

    def description(self) -> str:
        return "Spawn a subagent with fresh context to solve a given task. It shares the filesystem but not conversation history."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                    },
                    "required": ["task"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        print(f"sub_agent(task={task})")

        if not task:
            return "No task provided for sub-agent."

        system_prompt = f"You are a coding sub-agent at {WORKDIR}. Complete a given task and return concise summary. Use available tools to solve it. Prefer tools over prose."
        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        # sub-agent loop with limited rounds to prevent infinite recursion
        for _ in range(5):
            response = client.chat.completions.create(
                model="kimi-k2.5",
                messages=history,
                tools=registry.get_schemas_for_subagent(),
                max_tokens=4096,
                temperature=0.7,
                extra_body={"enable_thinking": True},
            )

            message = response.choices[0].message

            if hasattr(message, "reasoning_content") and message.reasoning_content:
                print("=" * 40)
                print("🤔 sub-agent reasoning content:")
                print(message.reasoning_content)
                print("=" * 40)

            if response.choices[0].finish_reason == "tool_calls":
                tool_calls = response.choices[0].message.tool_calls

                for call in tool_calls:
                    if call.function.name in registry.list_tools_for_subagent():
                        args = json.loads(call.function.arguments)
                        output = registry.get_tool(call.function.name).execute(**args)
                        history.append(
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
                        history.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "tool_name": call.function.name,
                                "content": output,
                            }
                        )
            elif response.choices[0].finish_reason == "stop":
                break
            else:
                print(
                    f"Unexpected finish reason in sub-agent: {response.choices[0].finish_reason}"
                )
                break

        # only return the final response
        return (
            response.choices[0].message.content.strip()
            if response.choices[0].message.content
            else "Sub-agent finished without response."
        )


class LoadSkill(Tool):
    def name(self) -> str:
        return "load_skill"

    def description(self) -> str:
        return "Load instructions for a skill by name. Use it when you need to use a skill but don't know how."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                    },
                    "required": ["skill_name"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        skill_name = kwargs.get("skill_name", "")
        print(f"load_skill(name={skill_name})")

        if not skill_name:
            return "No skill name provided."

        instructions = skill_loader.load_instructions(skill_name)
        return instructions

############################### Agent Main Loop ###############################


registry = ToolRegistry()
registry.register(Bash())
registry.register(ReadFile())
registry.register(WriteFile())
registry.register(Todo())
registry.register(SubAgent())
registry.register(LoadSkill())


def agent_loop(messages: list):

    # track how many rounds since last todo update, to prevent infinite loops without progress
    round_since_last_todo = 0

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

        used_todo = False
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

                if call.function.name == "todo":
                    used_todo = True
        elif response.choices[0].finish_reason == "stop":
            print("Final response:", response.choices[0].message.content)
            return response.choices[0].message.content
        else:
            print(f"Unexpected finish reason: {response.choices[0].finish_reason}")
            return f"Unexpected finish reason: {response.choices[0].finish_reason}"

        # update round_since_last_todo counter
        round_since_last_todo = 0 if used_todo else round_since_last_todo + 1
        # inject a todo reminder to prevent infinite loops without progress
        if round_since_last_todo > 3:
            messages.append(
                {
                    "role": "user",
                    "content": "Reminder: Please use the `todo` tool to plan and track your progress on multi-step tasks. This helps ensure steady progress and prevents infinite loops.",
                }
            )


if __name__ == "__main__":
    # query = 'Create a file called hello.py that prints "Hello, World!"'
    # query = "Create a directory called test_output and write 3 files in it"

    # query = "Create a file called greet.py with a greet(name) function"
    # agent_loop(query)

    # print(WORKDIR)
    # print(safe_path("hello.py"))
    # print(safe_path("../hello.py"))  # This should raise an error

    skill_loader = SkillLoader(Path(__file__).parent.parent.resolve() / "skills")

    system_prompt = f"You are a coding agent at {WORKDIR}. \
    Use available and appropriate tools or skills to solve tasks. \
    For complex tasks, use the `todo` tool to plan multi-step sub-tasks. Mark in_progress before starting, completed when done. \
    Use the `sub_agent` tool to delegate exploration or subtasks. \
    Use the `load_skill` tool to load instructions for a skill when needed.\n \
    Available skills:\n {skill_loader.list_skills()}."

    history = [{"role": "system", "content": system_prompt}]
    while True:
        try:
            query = input("\033[36mNanoCode >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        print(f"\033[32mNanoCode << {response_content}\033[0m")
        print()

    # simple test for skill loader
    # skill_loader = SkillLoader(Path(__file__).parent.parent.resolve() / "skills")
    # print("Available skills:")
    # print(skill_loader.list_skills())
    # print()
    # name = "memory"
    # print(f"Instructions for skill '{name}':")
    # print(skill_loader.load_instructions(name))
    # print()
