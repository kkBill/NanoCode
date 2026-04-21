"""Background task execution tools."""

import logging

from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class RunBackgroundTask(Tool):
    """Run a task in the background."""

    PARAMS = (
        ToolParams().param("command", str, description="Shell command to run in the background").required("command")
    )

    def name(self) -> str:
        return "run_background_task"

    def description(self) -> str:
        return "Run a long-running task in the background. Return a task id immediately, and the result will be available later via check_background_task."

    def execute(self, **kwargs) -> str:
        from ..core import background_manager

        command = kwargs.get("command", "")
        logger.info("run_background_task(command=%s)", command)

        if not command:
            return "No command provided for background task."

        task_id = background_manager.run(command)
        return f"Background task started with id: {task_id}"


class CheckBackgroundTask(Tool):
    """Check background task status."""

    PARAMS = ToolParams().param("task_id", str, description="ID of the background task to check")

    def name(self) -> str:
        return "check_background_task"

    def description(self) -> str:
        return "Check the status of a background task by id, or list all background tasks if no id provided."

    def execute(self, **kwargs) -> str:
        from ..core import background_manager

        task_id = kwargs.get("task_id", None)
        logger.info("check_background_task(task_id=%s)", task_id)

        status = background_manager.check_status(task_id)
        return status
