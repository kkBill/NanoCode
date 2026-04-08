from abc import ABC
import threading
import re
import uuid
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


############################### Hook ###############################
"""
Hook System Design
The agent loop exposes extension points (lifecycle events). At each point, it runs external shell commands called hooks. 
Each hook communicates its intent through its exit code: continue silently, block the operation, or inject a message into the conversation.


HookEvent: event (str), command (list[str])
- event: "before_tool_call", "after_tool_call", "session_start", "session_end"
- command: a shell command to run, e.g. ["echo hello world", "python3 safety_check.py"]

hook return code:
- 0: continue normally
- 1: block the current operation, tool not execute and stderr returns as error
- 2: tool still execute but stderr returns and injected as message


hook configuration: a JSON file (~/.nanocode/config.json) defining hooks for different events, e.g.
```json
{
    "hooks": {
        "before_tool_call": [
            {"command": "echo 'Hook before tool call: checking safety...'", "type": "log"},
            {"command": "python3 safety_check.py", "type": "script"}
        ],
        "after_tool_call": [
            {"command": "echo 'Hook after tool call: logging...'", "type": "log"},
            {"command": "python3 log_tool_call.py", "type": "script"}
        ],
        "session_start": [
            {"command": "echo 'Hook on session start: initializing...'", "type": "log"},
            {"command": "python3 init_session.py", "type": "script"}
        ],
        "session_end": [
            {"command": "echo 'Hook on session end: cleaning up...'", "type": "log"},
            {"command": "python3 cleanup_session.py'", "type": "script"}
        ]
    }
}
```
为什么一个事件类型会有多个 hook？因为不同的 hook 可以负责不同的功能，比如安全检查、日志记录、资源初始化等，互相独立又可以协同工作。
比如openclaw系统, 可以允许加载多种plugin，不同的plugin可能监听同一种事件类型来完成不同的事情
同一个事件类型对应的不同的hook该如何执行呢？它们彼此之间如果互相有影响该怎么办？本项目中暂时全部加载，顺序执行
"""

class HookManager:
    """
    load hooks from config
    run hooks for a given event
    """

    def __init__(self, config_path: Path = None) -> None:
        """Load hooks from config file."""
        default_config_path = WORKDIR / "config.json"
        self.config_path = config_path or default_config_path
        # define supported hook events
        self.hook_events = [
            "before_tool_call",
            "after_tool_call",
            "session_start",
            "session_end",
        ]
        # initialize hooks
        self.hooks = {event: [] for event in self.hook_events}
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text(encoding="utf-8"))
                hooks_config = config.get("hooks", {})
                if not hooks_config or not isinstance(hooks_config, dict):
                    print(f"Invalid hooks configuration in {self.config_path}")
                    return
                for event in self.hook_events:
                    if event in hooks_config:
                        self.hooks[event] = hooks_config.get(event, [])
            except Exception as e:
                print(f"Error loading hooks from {self.config_path}: {str(e)}")

    def run_hook(self, event: str, context: dict = None) -> dict:
        """
        Run hooks for a given event.

        Returns: {"blocked": bool, "messages": list[str]}
        - blocked:
        - messages:
        """
        result = {"blocked": False, "messages": []}

        if event not in self.hook_events:
            print(f"Unsupported hook event: {event}")
            return result

        hooks = self.hooks.get(event, [])
        for hook in hooks:
            command = hook.get("command", "")
            if not command:
                continue
            # build env with hook context, so that when hook execute, it can read from env
            env = dict(os.environ)
            if context:
                env["HOOK_EVENT"] = event
                env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
                env["HOOK_TOOL_ARGS"] = json.dumps(context.get("tool_args", {}))

            try:
                r = subprocess.run(
                    command,
                    shell=True,
                    cwd=WORKDIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if r.returncode == 0:
                    print(f"    [Hook:{event}] stdout:{r.stdout.strip()}, stderr:{r.stderr.strip()}")
                if r.returncode == 1:
                    result["blocked"] = True
                    result["blocked_reason"] = r.stderr.strip() or f"Blocked by hook {event}"
                    print(f"    [Hook:{event}] blocked the operation with command: {command}")
                elif r.returncode == 2:
                    msg = r.stdout.strip()
                    if msg:
                        result["messages"].append(msg)
                    print(f"    [Hook:{event}] injected message: {msg} with command: {command}")
            except Exception as e:
                print(f"Error running hook for event {event} with command {command}: {str(e)}")

        return result


hook_manager = HookManager()

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
            skills.append(f" - {name}: {description}")

        return "\n".join(skills)


############################### Task Manager ###############################


#  graph-based task manager to track multiple tasks and their dependencies
#  each task is a JSON file in the task_dir, with fields: id, description, status (pending/in_progress/completed), blockBy (list of task ids), blocks (list of task ids)
class TaskManager:
    def __init__(self, task_dir: Path):
        self.dir = task_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1

    # create a new task with description, return the task JSON
    def create_task(self, description: str) -> str:
        task = {
            "id": str(self._next_id),
            "description": description,
            "status": "pending",
            "blockedBy": [],
            "blocks": [],
        }
        self._next_id += 1
        path = self.dir / f"task_{task['id']}.json"
        task_json = json.dumps(task, indent=2)
        path.write_text(task_json, encoding="utf-8")
        return task_json

    # update task status and dependencies
    def update_task(
        self,
        task_id: int,
        status: str,
        add_blocked_by: list[int] = None,
        add_blocks: list[int] = None,
    ) -> str:
        # load task and make sure it exists
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        task = json.loads(path.read_text(encoding="utf-8"))

        # update status
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                # check if all prerequisites are completed
                for prereq_id in task["blockedBy"]:
                    prereq_path = self.dir / f"task_{prereq_id}.json"
                    if not prereq_path.exists():
                        raise ValueError(f"Prerequisite task {prereq_id} not found")
                    prereq_task = json.loads(prereq_path.read_text(encoding="utf-8"))
                    if prereq_task["status"] != "completed":
                        raise ValueError(
                            f"Cannot complete task {task_id} because prerequisite task {prereq_id} is not completed"
                        )

                # if completed, clear all blocks-task by this task
                self._clear_blocks(task_id)

        # update dependencies
        if add_blocked_by is not None:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))

        # update task which is blocked by this task to maintain consistency
        if add_blocks is not None:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
            for block_id in add_blocks:
                blocked_path = self.dir / f"task_{block_id}.json"
                if blocked_path.exists():
                    blocked_task = json.loads(blocked_path.read_text(encoding="utf-8"))
                    blocked_task["blockedBy"] = list(
                        set(blocked_task["blockedBy"] + [task_id])
                    )
                    blocked_path.write_text(
                        json.dumps(blocked_task, indent=2), encoding="utf-8"
                    )

        # save updated task
        path.write_text(json.dumps(task, indent=2), encoding="utf-8")
        return json.dumps(task, indent=2)

    def get_task(self, task_id: int) -> str:
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return path.read_text(encoding="utf-8")

    def list_tasks(self) -> str:
        tasks = []
        for path in self.dir.glob("task_*.json"):
            task = json.loads(path.read_text(encoding="utf-8"))
            tasks.append(task)
        return json.dumps(tasks, indent=2)

    def _clear_blocks(self, task_id: int):
        # clear blocks for a completed task
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        task = json.loads(path.read_text(encoding="utf-8"))
        for blocked_id in task["blocks"]:
            blocked_path = self.dir / f"task_{blocked_id}.json"
            if blocked_path.exists():
                blocked_task = json.loads(blocked_path.read_text(encoding="utf-8"))
                blocked_task["blockedBy"] = [
                    id for id in blocked_task["blockedBy"] if id != task_id
                ]
                blocked_path.write_text(
                    json.dumps(blocked_task, indent=2), encoding="utf-8"
                )

    def _max_id(self) -> int:
        max_id = -1
        for path in self.dir.glob("task_*.json"):
            try:
                id = int(path.stem.split("_")[1])
                if id > max_id:
                    max_id = id
            except:
                continue
        return max_id + 1


task_dir = WORKDIR / ".tasks"
task_manager = TaskManager(task_dir=task_dir)


############################### Background Task Manager ###############################


class BackgroundManager:

    def __init__(self) -> None:
        # task_id -> {"command": str, "status": "running" | "success" | "timeout" | "error", "result": str}
        self._tasks: dict[str, dict] = {}
        # list of completed tasks: {"task_id": str, "command": str, "status": str, "result": str}
        self._result_queue: list[dict] = []
        # lock for thread-safe access to _result_queue
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        """run a task in the background and return task id immediately"""
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {"command": command, "status": "running", "result": None}
        # start a new daemon thread to execute the task
        thread = threading.Thread(target=self._execute, args=(task_id,), daemon=True)
        thread.start()
        return task_id

    def _execute(self, task_id: str):
        """execute the command for a given task id, update the task status and result when done"""
        command = self._tasks[task_id]["command"]
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=WORKDIR,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            result = (
                (r.stdout + r.stderr).strip()[:50000]
                if (r.stdout or r.stderr)
                else "(no output)"
            )
            status = "success" if r.returncode == 0 else f"error (code {r.returncode})"
        except subprocess.TimeoutExpired:
            result = "Error: Timeout (300s)"
            status = "timeout"
        except Exception as e:
            result = f"Error: {str(e)}"
            status = f"error ({str(e)})"

        self._tasks[task_id]["status"] = status
        self._tasks[task_id]["result"] = result

        with self._lock:
            self._result_queue.append(
                {
                    "task_id": task_id,
                    "command": command,
                    "status": status,
                    "result": result,
                }
            )

    def check_status(self, task_id: str | None) -> str:
        # check the status of a specific task or all tasks if task_id is None
        if task_id:
            task = self._tasks.get(task_id, None)
            if not task:
                return f"Task {task_id} not found"
            return (
                f"Task: {task_id}, command: {task['command']}, status: {task['status']}"
            )
        else:
            lines = []
            for id, task in self._tasks.items():
                lines.append(f"Task: {id}, command: {task['command']}, status: {task['status']}")
            return "\n".join(lines)

    def get_result(self) -> list[dict]:
        """get and clear the result queue of completed tasks"""
        with self._lock:
            result = self._result_queue.copy()
            self._result_queue.clear()
        return result


background_manager = BackgroundManager()


############################### Context Manager ###############################
class ContextManager:
    def __init__(self, token_threshold: int = 1024, keep_recent_rounds: int = 1):
        self.token_threshold = token_threshold
        self.keep_recent_rounds = keep_recent_rounds

    def compact_tool_calls(self, messages: list) -> list:
        """compact tool call result, do it every time before sending messages to the model"""
        if len(messages) <= self.keep_recent_rounds * 2:
            return messages

        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        compacted = []
        for msg in old_messages:
            if msg.get("role") == "system" or msg.get("role") == "user":
                compacted.append(msg)
            elif msg.get("role") == "assistant" and "tool_calls" not in msg:
                compacted.append(msg)
            elif msg.get("role") == "tool":
                # for tool messages, only keep the tool name
                compacted.append(
                    {
                        "role": "assistant",
                        "content": f"Tool {msg.get('tool_name', 'unknown')} used",
                    }
                )
        recent_messages = messages[-(self.keep_recent_rounds * 2) :]
        return compacted + recent_messages

    def compact(self, messages: list) -> list:
        """automatically compact messages when token count exceeds threshold, can be called at the end of each round"""
        if self._token_estimate(messages) <= self.token_threshold:
            return messages

        print("Token count exceeds threshold, compacting messages...")
        # keep recent `keep_recent_rounds` rounds of messages, and summarize the older messages
        old_messages = messages[
            : -(self.keep_recent_rounds * 2)
        ]  # each round has 2 messages (user + assistant)
        context = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in old_messages]
        )

        response = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful context manager. Summarize the following conversation history in a concise way, keeping important details and omitting trivial parts.",
                },
                {"role": "user", "content": context},
            ],
            max_tokens=1024,
            temperature=0.5,
        )
        summary = response.choices[0].message.content.strip()

        # return the compacted messages with summary of old messages + recent messages
        pre_messages = [
            {"role": "user", "content": f"Summary of previous conversation: {summary}"},
            {
                "role": "assistant",
                "content": "Understood. I have the context from the summary. Continuing.",
            },
        ]
        return pre_messages + messages[-(self.keep_recent_rounds * 2) :]

    def _token_estimate(self, messages: list) -> int:
        """estimate token count of messages, use 1 token per 4 characters as a rough estimate"""
        return len(str(messages)) // 4


context_manager = ContextManager()

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


class CreateTask(Tool):
    def name(self) -> str:
        return "create_task"

    def description(self) -> str:
        return "Create a new task with description. Return the created task with id."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                    },
                    "required": ["description"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        description = kwargs.get("description", "")
        print(f"create_task(description={description})")

        if not description:
            return "No task description provided."

        task = task_manager.create_task(description)
        return task


class UpdateTask(Tool):
    def name(self) -> str:
        return "update_task"

    def description(self) -> str:
        return "Update a task's status and dependencies. Return the updated task."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                        "add_blocked_by": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of task ids that block this task.",
                        },
                        "add_blocks": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of task ids that this task blocks.",
                        },
                    },
                    "required": ["task_id", "status"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", None)
        status = kwargs.get("status", "")
        add_blocked_by = kwargs.get("add_blocked_by", [])
        add_blocks = kwargs.get("add_blocks", [])
        print(
            f"update_task(id={task_id}, status={status}, add_blocked_by={add_blocked_by}, add_blocks={add_blocks})"
        )

        if not task_id:
            return "No task id provided."

        try:
            updated_task = task_manager.update_task(
                task_id, status, add_blocked_by, add_blocks
            )
            return updated_task
        except Exception as e:
            return f"Error: {str(e)}"


class GetTask(Tool):
    def name(self) -> str:
        return "get_task"

    def description(self) -> str:
        return "Get a task's details by id."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                    },
                    "required": ["task_id"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", None)
        print(f"get_task(id={task_id})")

        if not task_id:
            return "No task id provided."

        try:
            task = task_manager.get_task(task_id)
            return task
        except Exception as e:
            return f"Error: {str(e)}"


class ListTasks(Tool):
    def name(self) -> str:
        return "list_tasks"

    def description(self) -> str:
        return "List all tasks with their details."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    def execute(self, **kwargs) -> str:
        print("list_tasks()")
        tasks = task_manager.list_tasks()
        return tasks


class RunBackgroundTask(Tool):
    def name(self) -> str:
        return "run_background_task"

    def description(self) -> str:
        return "Run a long-running task in the background. Return a task id immediately, and the result will be available later via check_background_task."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                    },
                    "required": ["command"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        print(f"run_background_task(command={command})")

        if not command:
            return "No command provided for background task."

        task_id = background_manager.run(command)
        return f"Background task started with id: {task_id}"


class CheckBackgroundTask(Tool):
    def name(self) -> str:
        return "check_background_task"

    def description(self) -> str:
        return "Check the status of a background task by id, or list all background tasks if no id provided."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                    },
                },
            },
        }

    def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", None)
        print(f"check_background_task(task_id={task_id})")

        status = background_manager.check_status(task_id)
        return status


############################### Agent Main Loop ###############################


registry = ToolRegistry()
registry.register(Bash())
registry.register(ReadFile())
registry.register(WriteFile())
# registry.register(Todo())
registry.register(SubAgent())
registry.register(LoadSkill())
registry.register(CreateTask())
registry.register(UpdateTask())
registry.register(GetTask())
registry.register(ListTasks())
registry.register(RunBackgroundTask())
registry.register(CheckBackgroundTask())


def agent_loop(messages: list):

    # track how many rounds since last todo update, to prevent infinite loops without progress
    round_since_last_todo = 0

    while True:

        # get all result from background tasks and append to messages for context
        background_results = [
            f"Task {r['task_id']} finished with status {r['status']}. Command: {r['command']}. Result: {r['result']}"
            for r in background_manager.get_result()
        ]
        results_content = "\n".join(background_results)
        if results_content:
            messages.append({"role": "user", "content": results_content})
            # add an assistant message to make it clear in the conversation history, so the model can refer to it later if needed
            messages.append({"role": "assistant", "content": "Noted background results."})

        messages = context_manager.compact_tool_calls(messages)
        messages = context_manager.compact(messages)

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

                # before_tool_call event
                ctx = {"tool_name": call.function.name, "tool_args": call.function.arguments}
                hook_result = hook_manager.run_hook("before_tool_call", ctx)

                print(f"hook result: {hook_result}")






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
        # if round_since_last_todo > 3:
        #     messages.append(
        #         {
        #             "role": "user",
        #             "content": "Reminder: Please use the `todo` tool to plan and track your progress on multi-step tasks. This helps ensure steady progress and prevents infinite loops.",
        #         }
        #     )


if __name__ == "__main__":
    # query = 'Create a file called hello.py that prints "Hello, World!"'
    # query = "Create a directory called test_output and write 3 files in it"

    # query = "Create a file called greet.py with a greet(name) function"
    # agent_loop(query)

    # print(WORKDIR)
    # print(safe_path("hello.py"))
    # print(safe_path("../hello.py"))  # This should raise an error

    skill_loader = SkillLoader(Path(__file__).parent.parent.resolve() / "skills")

    #     system_prompt = f" You are a coding agent at {WORKDIR}.\n \
    # Use available and appropriate tools or skills to solve tasks. \n \
    # - For complex tasks, use the `todo` tool to plan multi-step sub-tasks. Mark in_progress before starting, completed when done. \n \
    # - Use the `sub_agent` tool to delegate exploration or subtasks. \n \
    # - Use the `load_skill` tool to load instructions for a skill when needed.\n\n \
    # Available skills:\n{skill_loader.list_skills()}\n"

    system_prompt = f" You are a coding agent at {WORKDIR}.\n \
Use available and appropriate tools or skills to solve tasks. \n \
For complex tasks, use the task tool to plan and track your progress. \n \
Use background_run for long-running commands."

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
