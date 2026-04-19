"""Graph-based task management system."""

import json
from pathlib import Path

from ..utils import NANOCODE_HOME


class TaskManager:
    """Graph-based task manager to track multiple tasks and their dependencies."""

    def __init__(self):
        self.dir = NANOCODE_HOME / ".tasks"
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1

    def create_task(self, description: str) -> str:
        """Create a new task with description."""
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

    def update_task(
        self,
        task_id: int,
        status: str,
        add_blocked_by: list[int] = None,
        add_blocks: list[int] = None,
    ) -> str:
        """Update task status and dependencies."""
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        task = json.loads(path.read_text(encoding="utf-8"))

        # Update status
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                # Check if all prerequisites are completed
                for prereq_id in task["blockedBy"]:
                    prereq_path = self.dir / f"task_{prereq_id}.json"
                    if not prereq_path.exists():
                        raise ValueError(f"Prerequisite task {prereq_id} not found")
                    prereq_task = json.loads(prereq_path.read_text(encoding="utf-8"))
                    if prereq_task["status"] != "completed":
                        raise ValueError(f"Cannot complete task {task_id} because prerequisite task {prereq_id} is not completed")

                # If completed, clear all blocks-task by this task
                self._clear_blocks(task_id)

        # Update dependencies
        if add_blocked_by is not None:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))

        # Update task which is blocked by this task to maintain consistency
        if add_blocks is not None:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
            for block_id in add_blocks:
                blocked_path = self.dir / f"task_{block_id}.json"
                if blocked_path.exists():
                    blocked_task = json.loads(blocked_path.read_text(encoding="utf-8"))
                    blocked_task["blockedBy"] = list(set(blocked_task["blockedBy"] + [task_id]))
                    blocked_path.write_text(json.dumps(blocked_task, indent=2), encoding="utf-8")

        # Save updated task
        path.write_text(json.dumps(task, indent=2), encoding="utf-8")
        return json.dumps(task, indent=2)

    def get_task(self, task_id: int) -> str:
        """Get a task's details by id."""
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return path.read_text(encoding="utf-8")

    def list_tasks(self) -> str:
        """List all tasks with their details."""
        tasks = []
        for path in self.dir.glob("task_*.json"):
            task = json.loads(path.read_text(encoding="utf-8"))
            tasks.append(task)
        return json.dumps(tasks, indent=2)

    def _clear_blocks(self, task_id: int):
        """Clear blocks for a completed task."""
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        task = json.loads(path.read_text(encoding="utf-8"))
        for blocked_id in task["blocks"]:
            blocked_path = self.dir / f"task_{blocked_id}.json"
            if blocked_path.exists():
                blocked_task = json.loads(blocked_path.read_text(encoding="utf-8"))
                blocked_task["blockedBy"] = [id for id in blocked_task["blockedBy"] if id != task_id]
                blocked_path.write_text(json.dumps(blocked_task, indent=2), encoding="utf-8")

    def _max_id(self) -> int:
        """Get the maximum task id."""
        max_id = -1
        for path in self.dir.glob("task_*.json"):
            try:
                id = int(path.stem.split("_")[1])
                if id > max_id:
                    max_id = id
            except:
                continue
        return max_id + 1
