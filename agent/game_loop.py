import logging
import os
import time
from pathlib import Path
from typing import Any

from agent.window_capture import WindowCapture
from agent.state_processor import StateProcessor
from agent.ollama_client import OllamaClient
from agent.action_parser import ActionParser
from agent.input_simulator import InputSimulator

log = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"


def _load_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "You are an AI that plays retro video games. Choose the best controller input."


class GameLoop:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config
        self._system_prompt = _load_system_prompt()

        emu_cfg = config.get("emulator", {})
        self._capture = WindowCapture(
            window_title_contains=emu_cfg.get("window_title_contains", "RetroArch"),
        )
        self._processor = StateProcessor(config)
        self._llm = OllamaClient(config)
        self._parser = ActionParser()
        self._input: InputSimulator | None = None

        self._step = 0
        self._last_action_time = 0.0
        self._held_buttons: set[str] = set()
        self._running_right = False

    def _ensure_moving_right(self) -> None:
        if not self._running_right and self._input is not None:
            self._input.hold_continuous("DPAD_RIGHT")
            self._held_buttons.add("DPAD_RIGHT")
            self._running_right = True

    def _stop_moving_right(self) -> None:
        if self._running_right and self._input is not None:
            self._input.release_button("DPAD_RIGHT")
            self._held_buttons.discard("DPAD_RIGHT")
            self._running_right = False

    def setup(self) -> bool:
        log.info("Looking for emulator window...")
        if not self._capture.wait_for_window(timeout=30):
            log.error("Emulator window not found. Available windows:")
            for w in self._capture.list_windows():
                log.info("  hwnd=%d title='%s'", w["hwnd"], w["title"])
            return False

        log.info("Found emulator window (hwnd=%d)", self._capture.hwnd)

        self._input = InputSimulator(self._cfg, target_hwnd=self._capture.hwnd)

        if not self._llm.is_available():
            log.error("Ollama is not running at %s", self._llm.model)
            return False

        log.info("Ollama available. Using model: %s", self._llm.model)

        log.info("Input method ready")

        return True

    def step(self) -> bool:
        loop_cfg = self._cfg.get("game_loop", {})
        max_steps = loop_cfg.get("max_steps", 0)
        if max_steps > 0 and self._step >= max_steps:
            self._stop_moving_right()
            log.info("Reached max steps (%d)", max_steps)
            return False

        screenshot_scale = loop_cfg.get("screenshot_scale", 0.5)

        # Keep the character moving right by default while the LLM thinks
        self._ensure_moving_right()

        raw_img = self._capture.capture(scale=screenshot_scale)
        if raw_img is None:
            log.warning("Failed to capture emulator window")
            time.sleep(0.5)
            return True

        processed = self._processor.process(raw_img)
        state_text = processed.get("state_text", "No state data")

        full_prompt = f"{state_text}\n\n{self._system_prompt}\n\nWhat action?"

        log.debug("LLM state context: %s", state_text[:500])
        response = self._llm.generate(prompt=full_prompt)
        log.info("LLM response: %s", response)

        action = self._parser.parse(response)
        log.info("Parsed action: %s", action)

        self._execute_action(action)

        # After executing a decision (jump, etc.), resume moving right
        self._ensure_moving_right()

        self._step += 1
        return True

    def _execute_action(self, action: Any) -> None:
        from agent.action_parser import ParsedAction
        act = action  # type: ParsedAction

        if act.action == "press":
            self._held_buttons.discard(act.button)
            self._input.press_button(act.button, act.hold_ms)

        elif act.action == "hold":
            self._held_buttons.add(act.button)
            self._input.hold_button(act.button, act.hold_ms)

        elif act.action == "release":
            self._held_buttons.discard(act.button)
            self._input.release_button(act.button)

        elif act.action == "tap":
            self._input.tap_button(act.button, act.taps, act.hold_ms)

        elif act.action == "wait":
            self._input.wait(act.hold_ms)

    def run(self) -> None:
        log.info("Starting game loop")
        try:
            while True:
                if not self.step():
                    break
        except KeyboardInterrupt:
            log.info("Stopped by user")
        finally:
            self._stop_moving_right()
            if self._input is not None:
                self._input.shutdown()
            log.info("Agent stopped after %d steps", self._step)
