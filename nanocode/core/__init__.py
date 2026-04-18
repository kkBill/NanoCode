"""Core subsystems for the agent."""
from .hook import HookManager
from .permission import PermissionManager, PermissionRule
from .skill_loader import SkillLoader
from .task_manager import TaskManager
from .background import BackgroundManager
from .context import ContextManager
from .memory import MemoryManager
from .prompt import SystemPromptBuilder
from .cron import CronScheduler, CronTask

# Global instances
hook_manager = HookManager()
permission_manager = PermissionManager()
task_manager = TaskManager()
background_manager = BackgroundManager()
context_manager = ContextManager()
memory_manager = MemoryManager()
skill_loader = SkillLoader()
system_prompt_builder = SystemPromptBuilder()
cron_scheduler = CronScheduler()


# Load memories on import
memory_manager.load()

__all__ = [
    "HookManager",
    "PermissionManager",
    "PermissionRule",
    "SkillLoader",
    "TaskManager",
    "BackgroundManager",
    "ContextManager",
    "MemoryManager",
    "CronScheduler",
    "CronTask",
    "hook_manager",
    "permission_manager",
    "task_manager",
    "background_manager",
    "context_manager",
    "memory_manager",
    "skill_loader",
    "system_prompt_builder",
    "cron_scheduler",
]
