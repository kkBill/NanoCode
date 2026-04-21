import logging

from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class CreateCron(Tool):
    def name(self) -> str:
        return "create_cron"

    def description(self) -> str:
        return "Create a cron task with a cron expression, trigger mode, persistent mode, and prompt."

    PARAMS = (
        ToolParams()
        .param("cron_expr", str, description="Cron expression to specify the schedule of the task")
        .param("trigger_mode", str, enum=["repeat", "one-shot"])
        .param("persistent_mode", str, enum=["durable", "in-memory"])
        .param("prompt", str, description="The prompt to execute when the task is triggered")
        .required("cron_expr", "trigger_mode", "persistent_mode", "prompt")
    )

    # 为什么这个execute方法不返回 str 也没有关系？它不是继承自 Tool 吗？
    # Python 中的继承、抽象类等机制是怎么样的？
    def execute(self, **kwargs) -> str:
        from ..core import cron_scheduler

        cron_expr = kwargs.get("cron_expr", "")
        trigger_mode = kwargs.get("trigger_mode", "")
        persistent_mode = kwargs.get("persistent_mode", "")
        prompt = kwargs.get("prompt", "")
        logger.info(
            "Creating cron task with cron_expr=%s, trigger_mode=%s, persistent_mode=%s, prompt=%s",
            cron_expr,
            trigger_mode,
            persistent_mode,
            prompt,
        )

        task = cron_scheduler.create_task(cron_expr, trigger_mode, persistent_mode, prompt)
        if task:
            return f"Cron task created successfully with ID {task.id}."
        else:
            return f"Failed to create cron task with cron_expr={cron_expr}, trigger_mode={trigger_mode}, persistent_mode={persistent_mode}, prompt={prompt}."


class DeleteCron(Tool):
    def name(self) -> str:
        return "delete_cron"

    def description(self) -> str:
        return "Delete a cron task by its ID."

    PARAMS = ToolParams().param("task_id", str, description="The ID of the cron task to delete").required("task_id")

    def execute(self, **kwargs) -> str:
        from ..core import cron_scheduler

        task_id = kwargs.get("task_id", "")
        logger.info("Deleting cron task with id=%s", task_id)

        if cron_scheduler.delete_task(task_id):
            return f"Cron task {task_id} deleted successfully."
        else:
            return f"Cron task {task_id} not found."
