"""Hook system for lifecycle events."""
import json
import logging
import os
import subprocess

from ..utils import NANOCODE_HOME, WORK_DIR

logger = logging.getLogger(__name__)


class HookManager:
    """
    Load hooks from config and run hooks for a given event.

    Hook events: before_tool_call, after_tool_call, session_start, session_end

    Hook return codes:
    - 0: Continue normally
    - 1: Block the current operation
    - 2: Tool still executes but stderr is injected as message
    """

    def __init__(self) -> None:
        self.config_path = NANOCODE_HOME / "config.json"
        # Define supported hook events
        self.hook_events = [
            "before_tool_call",
            "after_tool_call",
            "session_start",
            "session_end",
        ]
        # Initialize hooks
        self.hooks = {event: [] for event in self.hook_events}
        if self.config_path.exists():
            try:
                config = json.loads(self.config_path.read_text(encoding="utf-8"))
                hooks_config = config.get("hooks", {})
                if not hooks_config or not isinstance(hooks_config, dict):
                    logger.warning("Invalid hooks configuration in %s", self.config_path)
                    return
                for event in self.hook_events:
                    if event in hooks_config:
                        self.hooks[event] = hooks_config.get(event, [])
            except Exception as e:
                logger.exception("Error loading hooks from %s: %s", self.config_path, e)

    def run_hook(self, event: str, context: dict = None) -> dict:
        """
        Run hooks for a given event.

        Returns: {"blocked": bool, "messages": list[str]}
        """
        result = {"blocked": False, "messages": []}

        if event not in self.hook_events:
            logger.warning("Unsupported hook event: %s", event)
            return result

        hooks = self.hooks.get(event, [])
        for hook in hooks:
            command = hook.get("command", "")
            if not command:
                continue
            # Build env with hook context
            env = dict(os.environ)
            if context:
                env["HOOK_EVENT"] = event
                env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
                env["HOOK_TOOL_ARGS"] = json.dumps(context.get("tool_args", {}))

            try:
                r = subprocess.run(
                    command,
                    shell=True,
                    cwd=WORK_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if r.returncode == 0:
                    logger.info("[Hook:%s] stdout:%s, stderr:%s", event, r.stdout.strip(), r.stderr.strip())
                if r.returncode == 1:
                    result["blocked"] = True
                    result["blocked_reason"] = r.stderr.strip() or f"Blocked by hook {event}"
                    logger.warning("[Hook:%s] blocked the operation with command: %s", event, command)
                elif r.returncode == 2:
                    msg = r.stdout.strip()
                    if msg:
                        result["messages"].append(msg)
                    logger.info("[Hook:%s] injected message: %s with command: %s", event, msg, command)
            except Exception as e:
                logger.exception("Error running hook for event %s with command %s: %s", event, command, e)

        return result
