from dataclasses import dataclass
import uuid

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
    name: str
    cron: str
    trigger_mode: str  # "repeat" or "one-shot"
    persistent_mode: str  # "durable" or "in-memory"
    prompt: str  # the function to execute when the task is triggered
    created_at: str
    last_triggered_at: str | None = None

class CronScheduler:
    def __init__(self):
        pass

    def create_task(self) -> CronTask:
        pass

    def list_tasks(self) -> list[CronTask]:
        pass

    def delete_task(self, task_id: str) -> bool:
        return True

