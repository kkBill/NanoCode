"""Global configuration and constants for the agent."""
import os
from pathlib import Path

from openai import OpenAI


# Base paths
ROOT_DIR = Path(__file__).parent.parent.resolve()
SRC_DIR = ROOT_DIR / "src"
SKILLS_DIR = SRC_DIR / "skills"
WORKDIR = ROOT_DIR / "workspace"

# API Configuration
MODEL_NAME = "kimi-k2.5"
API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Initialize OpenAI client (via aliyun dashscope)
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# Memory extraction instructions for system prompt
MEMORY_EXTRACT_INSTRUCTIONS = """
When to save memories:
- User states a preference ("I like tabs", "always use pytest") -> type: user
- User corrects you ("don't do X", "that was wrong because...") -> type: feedback
- You learn a project fact that is not easy to infer from current code alone
  (for example: a rule exists because of compliance, or a legacy module must stay untouched for business reasons) -> type: project
- You learn where an external resource lives (ticket board, dashboard, docs URL) -> type: reference

When NOT to save:
- Anything easily derivable from code (function signatures, file structure, directory layout)
- Temporary task state (current branch, open PR numbers, current TODOs)
- Secrets or credentials (API keys, passwords)
"""
