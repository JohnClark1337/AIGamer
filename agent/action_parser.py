import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

VALID_BUTTONS = frozenset({
    "A", "B", "X", "Y",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
    "START", "BACK",
    "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_THUMB", "RIGHT_THUMB",
})

VALID_ACTIONS = frozenset({"press", "hold", "release", "wait", "tap"})


class ParsedAction:
    def __init__(self, data: dict[str, Any]):
        self.action: str = data.get("action", "wait")
        self.button: str = data.get("button", "")
        self.hold_ms: int = data.get("hold_ms", 100)
        self.taps: int = data.get("taps", 1)

    @property
    def valid(self) -> bool:
        if self.action not in VALID_ACTIONS:
            return False
        if self.action != "wait" and self.button not in VALID_BUTTONS:
            return False
        return True

    def __repr__(self) -> str:
        if self.action == "wait":
            return f"wait({self.hold_ms}ms)"
        if self.action == "tap":
            return f"tap({self.button} x{self.taps} {self.hold_ms}ms)"
        return f"{self.action}({self.button} {self.hold_ms}ms)"


class ActionParser:
    def parse(self, llm_response: str) -> ParsedAction:
        cleaned = llm_response.strip()

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning("Failed to parse JSON from: %s", llm_response[:200])
            return ParsedAction({"action": "wait", "hold_ms": 500})

        action = ParsedAction(data)

        if not action.valid:
            log.warning("Invalid action parsed: %s", action)
            return ParsedAction({"action": "wait", "hold_ms": 500})

        return action
