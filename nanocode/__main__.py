import logging
from pathlib import Path

from .agent import agent_loop
from .core import system_prompt_builder
from .core import cron_scheduler
from .message import Message, SystemMessage, UserMessage

# Configure logging once at startup
project_root = Path(__file__).parent.parent.resolve()
log_dir = project_root / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        # logging.StreamHandler(),  # log to console
        logging.FileHandler(log_dir / "nanocode.log", encoding="utf-8"),
    ],
)

def main():
    """Main entry point for the agent."""

    cron_scheduler.start()  # Start the cron scheduler background thread

    system_prompt = system_prompt_builder.build()
    history: list[Message] = [SystemMessage(content=system_prompt)]

    while True:
        try:
            query = input("\033[36mNanoCode >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", "quit"):
            break
        if query.strip().lower() == "/prompt":
            print("Current system prompt:")
            print(system_prompt)
            continue

        history.append(UserMessage(content=query))
        response_content = agent_loop(history)
        print(f"\033[32mNanoCode << {response_content}\033[0m")
        print()

    cron_scheduler.stop()  # Stop the cron scheduler background thread before exiting


if __name__ == "__main__":
    main()
