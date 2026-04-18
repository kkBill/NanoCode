"""Permission system for tool access control."""
import logging
from dataclasses import dataclass
from fnmatch import fnmatch
import json

logger = logging.getLogger(__name__)


@dataclass
class PermissionRule:
    """Rule definition for permissions."""

    tool: str     # Tool name
    content: str  # What tool does (pattern)
    behavior: str # 'deny'/'allow'/'ask'


class PermissionManager:
    """4-stage permission control: block rules -> mode -> allow rules -> ask user."""

    def __init__(self, mode: str = "default", rules: list = None):
        self.modes: list[str] = ["default", "plan", "auto"]
        if mode not in self.modes:
            raise ValueError(f"Unknown mode: {mode}")
        self.mode = mode
        default_rules: list[PermissionRule] = [
            PermissionRule(tool='bash', content='rm -rf /', behavior='deny'),
            PermissionRule(tool='bash', content='sudo *', behavior='deny'),
            PermissionRule(tool='read_file', content='*', behavior='allow')
        ]
        self.rules = rules or default_rules
        self.write_tools = ["bash", "write_file", "edit_file"]
        self.read_tools = ["read_file"]

    def check(self, tool_name: str, tool_args: dict) -> dict:
        """
        Check whether a tool is allowed to execute.

        Returns dict with "behavior" and "reason" keys.
        """
        # Stage 1: Check block rules
        for rule in self.rules:
            if rule.behavior == 'deny' and self._match(rule, tool_name, tool_args):
                logger.debug("Stage 1: blocked by deny rule")
                return {"behavior": "deny", "reason": f"Blocked by deny rule: {rule}"}

        # Stage 2: Check mode
        if self.mode == "plan":
            if tool_name in self.read_tools:
                return {"behavior": "allow", "reason": "Plan mode: read operation is allowed"}
            elif tool_name in self.write_tools:
                return {"behavior": "deny", "reason": "Plan mode: write operation is denied"}
        if self.mode == "auto":
            if tool_name in self.read_tools:
                return {"behavior": "allow", "reason": "Auto mode: read operation is allowed"}
            elif tool_name in self.write_tools:
                return {"behavior": "ask", "reason": "Auto mode: write operation is asked"}

        # Stage 3: Check allow rules
        for rule in self.rules:
            if rule.behavior == 'allow' and self._match(rule, tool_name, tool_args):
                logger.debug("Stage 3: matched allow rule")
                return {"behavior": "allow", "reason": f"Always-allow rule: {rule}"}

        # Stage 4: Ask user for any unmatched tool
        logger.debug("Stage 4: no rule matched, asking user")
        return {"behavior": "ask", "reason": f"No rule matches for tool {tool_name}, asking user"}

    def ask_user(self, tool_name: str, tool_args: dict) -> bool:
        """Ask user for permission to execute a tool."""
        args = json.dumps(tool_args, ensure_ascii=False)
        logger.info("Asked for permission for tool [%s] with arguments [%s]", tool_name, args)
        try:
            response = input("  Allow (y/n/always-allow): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            logger.info("User interrupted the permission request.")
            return False
        if response in ("always-allow", "always"):
            self.rules.append(PermissionRule(tool=tool_name, content='*', behavior='allow'))
            return True
        elif response in ("y", "yes"):
            return True
        logger.info("User denied permission.")
        return False

    def _match(self, rule: PermissionRule, tool_name: str, tool_args: dict) -> bool:
        """Check if a tool matches a rule using fnmatch patterns."""
        if rule.tool != tool_name:
            return False

        if tool_args.get("command", ""):
            logger.debug("Matching command: %s", tool_args["command"])
            return fnmatch(tool_args["command"], rule.content)
        if tool_args.get("path", ""):
            logger.debug("Matching path: %s", tool_args["path"])
            return fnmatch(tool_args["path"], rule.content)
        return False
