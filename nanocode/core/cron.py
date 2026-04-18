from dataclasses import dataclass
from pathlib import Path
import uuid
import queue
import threading
import json
import time
from datetime import datetime
from croniter import croniter

from ..utils import NANOCODE_HOME

"""
如何设计一个定时任务系统？

1. 如何描述一个定时任务？
CronTask:
- id: task id
- name: task name
- cron: cron expression
- trigger_mode: repeat or one-shot
- persistent_mode: durable or in-memory(session only)
- task_func: the function to execute when the task is triggered 这个该如何定义？写死？让模型决定？
- created_at: task creation time
CronTask 还可以增加一个字段 last_triggered_at 来记录上次触发时间, 以便在系统重启后能够判断是否错过了某些触发时间. 如果错过了, 可以选择立即执行 task_func 或者跳过


2. 如何创建定时任务
将 create_task 接口作为 tool, 由模型决定是否调用该工具来创建定时任务
如果任务是持久化的, 还需将其写入到本地文件中, 以便在系统重启后能够恢复任务列表
一般写在 ~/.nanocode/cron_tasks.json 中

3. 如何触发定时任务
“触发”的关键是“时间是否匹配”
需要一个独立的后台线程来监控当前时间, 并在任务的 cron 表达式“匹配”时执行对应的 task_func
那么, 如何定义“匹配”呢？可以使用第三方库如 croniter 来解析 cron 表达式, 并计算下一个触发时间. 当系统时间达到或超过这个触发时间时, 就执行对应的 task_func

如何考虑过期？

"""

@dataclass
class CronTask:
    id: str
    cron_expr: str  # cron expression, e.g. "0 9 * * *" for every day at 9am
    trigger_mode: str  # "repeat" or "one-shot"
    persistent_mode: str  # "durable" or "in-memory"
    prompt: str  # the function to execute when the task is triggered
    created_at: str
    last_triggered_at: str | None = None

class CronScheduler:
    def __init__(self):
        self.scheduled_tasks_file = NANOCODE_HOME / "scheduled_tasks.json"
        self.tasks = {}  # task_id -> CronTask
        self.notify_queue = queue.Queue()
        self._stop_event = threading.Event()  # 用于通知后台线程停止
        self._thread = None

    def start(self):
        """Load durable tasks and start the background thread to monitor and trigger tasks."""
        self._load_tasks()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Background thread function to monitor and trigger tasks."""
        while not self._stop_event.is_set():
            now = datetime.now()
            for task in self.tasks.values():
                # Check if the task should be triggered
                if croniter.match(task.cron_expr, now):
                    # If it's a one-shot task and has been triggered before, skip it
                    if task.trigger_mode == "one-shot" and task.last_triggered_at is not None:
                        continue
                    # Trigger the task (put it in the notify queue)
                    self.notify_queue.put(task)
                    # Update last_triggered_at
                    task.last_triggered_at = now.isoformat()
                    # If it's a durable task, save the updated task info to disk
                    if task.persistent_mode == "durable":
                        self._save_task(task)
            time.sleep(1)  # Check every 1 seconds

    def stop(self):
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def create_task(self, cron_expr: str, trigger_mode: str, persistent_mode: str, prompt: str) -> CronTask:
        """Create a new cron task."""
        task_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        task = CronTask(
            id=task_id,
            cron_expr=cron_expr,
            trigger_mode=trigger_mode,
            persistent_mode=persistent_mode,
            prompt=prompt,
            created_at=created_at,
        )
        self.tasks[task_id] = task
        if persistent_mode == "durable":
            self._save_task(task)
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a cron task."""
        if task_id not in self.tasks:
            return False
        task = self.tasks[task_id]
        if task.persistent_mode == "durable":
            path = self.scheduled_tasks_file
            if path.exists():
                config = json.loads(path.read_text(encoding="utf-8"))
                cron_tasks = config.get("cron_tasks", {})
                if task_id in cron_tasks:
                    del cron_tasks[task_id]
                    config["cron_tasks"] = cron_tasks
                    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        del self.tasks[task_id]
        return True

    def list_tasks(self) -> list[CronTask]:
        return list(self.tasks.values())
    
    def _load_tasks(self):
        """Load durable tasks from disk."""
        path = self.scheduled_tasks_file
        if not path.exists():
            return
        config = json.loads(path.read_text(encoding="utf-8"))
        cron_tasks = config.get("cron_tasks", {})
        if not cron_tasks:
            return
        # 遍历cron_tasks, 将其转换为CronTask对象并存储到self.tasks中
        for id, task in cron_tasks.items():
            self.tasks[id] = CronTask(**task)

    def _save_task(self, task: CronTask):
        """Save durable task to disk."""
        path = self.scheduled_tasks_file
        if not path.exists():
            config = {"cron_tasks": {}}
        else:
            config = json.loads(path.read_text(encoding="utf-8"))
        cron_tasks = config.get("cron_tasks", {})
        cron_tasks[task.id] = task.__dict__  # 将CronTask对象转换为字典
        config["cron_tasks"] = cron_tasks
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def drain_notify_queue(self) -> list[CronTask]:
        """Drain the notify queue and return the list of triggered tasks."""
        tasks = []
        while not self.notify_queue.empty():
            task = self.notify_queue.get()
            tasks.append(task)
        return tasks
