#!/usr/bin/env python3
"""
ollama-game-agent – Let Ollama play video games via emulators.
"""

import argparse
import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import load_config
from agent.game_loop import GameLoop
from agent.ollama_client import OllamaClient


def setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)

    if args.model:
        config["ollama"]["model"] = args.model
    if args.emulator:
        config["emulator"]["window_title_contains"] = args.emulator
    if args.fps:
        config["game_loop"]["fps"] = args.fps
    if args.max_steps:
        config["game_loop"]["max_steps"] = args.max_steps
    if args.title:
        config["emulator"]["window_title_contains"] = args.title

    setup_logging(config.get("logging", {}).get("level", "INFO"))
    log = logging.getLogger("main")

    loop = GameLoop(config)
    if not loop.setup():
        log.error("Setup failed")
        return 1

    loop.run()
    return 0


def cmd_list_windows(args: argparse.Namespace) -> int:
    from agent.window_capture import WindowCapture
    cap = WindowCapture()
    windows = cap.list_windows(filter_str=args.filter or "")
    if not windows:
        print("No windows found." + (f" (filter: '{args.filter}')" if args.filter else ""))
        return 0
    print(f"{'HWND':>8}  {'Title'}")
    print("-" * 60)
    for w in windows:
        print(f"{w['hwnd']:>8}  {w['title']}")
    return 0


def cmd_list_models(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    client = OllamaClient(config)
    models = client.list_models()
    if not models:
        print("No models found. Is Ollama running?")
        return 1
    print(f"{'Name':<30}  {'Size':>8}  {'Modified'}")
    print("-" * 60)
    for m in models:
        name = m.get("name", "?")
        size = m.get("size", 0)
        modified = m.get("modified_at", "?")[:10]
        print(f"{name:<30}  {size:>8}  {modified}")
    return 0


def cmd_pull_model(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    client = OllamaClient(config)
    model = args.model or "llama3.2-vision:11b"
    print(f"Pulling model: {model} (this may take a while)...")
    client.pull_model(model)
    print("Done.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Let Ollama play video games via emulators.",
    )
    parser.add_argument("--config", "-c", help="Path to config YAML file")
    parser.add_argument("--model", "-m", help="Ollama model to use")
    parser.add_argument("--emulator", "-e", help="Emulator name (e.g. RetroArch, Dolphin)")
    parser.add_argument("--fps", type=float, help="Game loop iterations per second")
    parser.add_argument("--max-steps", type=int, help="Max steps before stopping (0=infinite)")
    parser.add_argument("--title", "-t", help="Window title filter for emulator capture")

    sub = parser.add_subparsers(dest="command", help="Commands")

    sub.add_parser("run", help="Run the game-playing agent (default)")

    list_wins = sub.add_parser("list-windows", help="List visible windows with titles")
    list_wins.add_argument("--filter", "-f", default="", help="Filter window titles")

    list_models = sub.add_parser("list-models", help="List available Ollama models")

    pull = sub.add_parser("pull-model", help="Download a vision model")
    pull.add_argument("model", nargs="?", default="llama3.2-vision:11b",
                      help="Model name to pull (default: llama3.2-vision:11b)")

    args = parser.parse_args()

    if args.command == "list-windows":
        return cmd_list_windows(args)
    elif args.command == "list-models":
        return cmd_list_models(args)
    elif args.command == "pull-model":
        return cmd_pull_model(args)
    else:
        return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
