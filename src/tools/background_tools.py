"""Background task execution tools."""
from ..core import background_manager
from .base import Tool


class RunBackgroundTask(Tool):
    """Run a task in the background."""

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
    """Check background task status."""

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
