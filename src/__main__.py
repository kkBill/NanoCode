"""Entry point for the NanoCode agent."""
from pathlib import Path

from .agent import agent_loop, build_system_prompt
from .core import skill_loader


def main():
    """Main entry point for the agent."""
    system_prompt = build_system_prompt()
    history = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            query = input("\033[36mNanoCode >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        print(f"\033[32mNanoCode << {response_content}\033[0m")
        print()


if __name__ == "__main__":
    main()
