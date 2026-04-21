"""Task management tools."""

import logging

from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class CreateTask(Tool):
    """Create a new task."""

    PARAMS = ToolParams().param("description", str, description="Task description").required("description")

    def name(self) -> str:
        return "create_task"

    def description(self) -> str:
        return "Create a new task with description. Return the created task with id."

    def execute(self, **kwargs) -> str:
        from ..core import task_manager

        description = kwargs.get("description", "")
        logger.info("create_task(description=%s)", description)

        if not description:
            return "No task description provided."

        task = task_manager.create_task(description)
        return task


class UpdateTask(Tool):
    """Update a task's status and dependencies."""

    PARAMS = (
        ToolParams()
        .param("task_id", int, description="Task ID")
        .param("status", str, enum=["pending", "in_progress", "completed"], description="New status")
        .param("add_blocked_by", list, items=int, description="List of task ids that block this task")
        .param("add_blocks", list, items=int, description="List of task ids that this task blocks")
        .required("task_id", "status")
    )

    def name(self) -> str:
        return "update_task"

    def description(self) -> str:
        return "Update a task's status and dependencies. Return the updated task."

    def execute(self, **kwargs) -> str:
        from ..core import task_manager

        task_id = kwargs.get("task_id", None)
        status = kwargs.get("status", "")
        add_blocked_by = kwargs.get("add_blocked_by", [])
        add_blocks = kwargs.get("add_blocks", [])
        logger.info(
            "update_task(id=%s, status=%s, add_blocked_by=%s, add_blocks=%s)",
            task_id,
            status,
            add_blocked_by,
            add_blocks,
        )

        if not task_id:
            return "No task id provided."

        try:
            updated_task = task_manager.update_task(task_id, status, add_blocked_by, add_blocks)
            return updated_task
        except Exception as e:
            return f"Error: {str(e)}"


class GetTask(Tool):
    """Get a task by id."""

    PARAMS = ToolParams().param("task_id", int, description="Task ID").required("task_id")

    def name(self) -> str:
        return "get_task"

    def description(self) -> str:
        return "Get a task's details by id."

    def execute(self, **kwargs) -> str:
        from ..core import task_manager

        task_id = kwargs.get("task_id", None)
        logger.info("get_task(id=%s)", task_id)

        if not task_id:
            return "No task id provided."

        try:
            task = task_manager.get_task(task_id)
            return task
        except Exception as e:
            return f"Error: {str(e)}"


class ListTasks(Tool):
    """List all tasks."""

    # No parameters

    def name(self) -> str:
        return "list_tasks"

    def description(self) -> str:
        return "List all tasks with their details."

    def execute(self, **kwargs) -> str:
        from ..core import task_manager

        logger.info("list_tasks()")
        tasks = task_manager.list_tasks()
        return tasks
