"""Core subsystems for the agent."""
from .hook import HookManager
from .permission import PermissionManager, PermissionRule
from .skill_loader import SkillLoader
from .task_manager import TaskManager
from .background import BackgroundManager
from .context import ContextManager
from .memory import MemoryManager

# Global instances
hook_manager = HookManager()
permission_manager = PermissionManager()
task_manager = TaskManager()
background_manager = BackgroundManager()
context_manager = ContextManager()
memory_manager = MemoryManager()
skill_loader = SkillLoader()

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
    "hook_manager",
    "permission_manager",
    "task_manager",
    "background_manager",
    "context_manager",
    "memory_manager",
    "skill_loader",
]
