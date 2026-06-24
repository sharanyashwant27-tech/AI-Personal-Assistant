"""CLI entry — launch Plane API server or run terminal mode."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Plane — Cursor agent terminal")
    parser.add_argument(
        "mode",
        nargs="?",
        default="serve",
        choices=["serve", "chat"],
        help="serve=API for desktop UI, chat=terminal fallback",
    )
    args = parser.parse_args()

    if args.mode == "serve":
        from api.server import main as serve

        serve()
        return

    from runtime import create_runtime

    state = create_runtime()
    print("Plane CLI — Cursor agent (type quit to exit)\n")

    while True:
        try:
            user_input = input("› ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break
        if user_input.lower() == "clear":
            state.assistant.clear_history()
            print("History cleared.")
            continue
        try:
            reply = state.assistant.run(user_input)
            print(f"\n{reply}\n")
        except (ValueError, RuntimeError) as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)
