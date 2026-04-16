from .agent import agent_loop
from .core import system_prompt_builder
from .core import cron_scheduler

def main():
    """Main entry point for the agent."""

    cron_scheduler.start()  # Start the cron scheduler background thread

    system_prompt = system_prompt_builder.build()
    history = [{"role": "system", "content": system_prompt}]

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

        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        print(f"\033[32mNanoCode << {response_content}\033[0m")
        print()

    cron_scheduler.stop()  # Stop the cron scheduler background thread before exiting


if __name__ == "__main__":
    main()
