"""Background task execution system."""

import subprocess
import threading
import uuid

from ..utils import WORK_DIR


class BackgroundManager:
    """Async task execution with daemon threads."""

    def __init__(self) -> None:
        # task_id -> {"command": str, "status": "running" | "success" | "timeout" | "error", "result": str}
        self._tasks: dict[str, dict] = {}
        # List of completed tasks
        self._result_queue: list[dict] = []
        # Lock for thread-safe access to _result_queue
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        """Run a task in the background and return task id immediately."""
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {"command": command, "status": "running", "result": None}
        # Start a new daemon thread to execute the task
        thread = threading.Thread(target=self._execute, args=(task_id,), daemon=True)
        thread.start()
        return task_id

    def _execute(self, task_id: str):
        """Execute the command for a given task id."""
        command = self._tasks[task_id]["command"]
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=WORK_DIR,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            result = (r.stdout + r.stderr).strip()[:50000] if (r.stdout or r.stderr) else "(no output)"
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
        """Check the status of a specific task or all tasks."""
        if task_id:
            task = self._tasks.get(task_id, None)
            if not task:
                return f"Task {task_id} not found"
            return f"Task: {task_id}, command: {task['command']}, status: {task['status']}"
        else:
            lines = []
            for id, task in self._tasks.items():
                lines.append(f"Task: {id}, command: {task['command']}, status: {task['status']}")
            return "\n".join(lines)

    def get_result(self) -> list[dict]:
        """Get and clear the result queue of completed tasks."""
        with self._lock:
            result = self._result_queue.copy()
            self._result_queue.clear()
        return result
