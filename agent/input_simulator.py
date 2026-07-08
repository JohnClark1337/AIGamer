import logging
import time
from typing import Any

log = logging.getLogger(__name__)

BUTTON_MAP = {
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "DPAD_UP": "DPAD_UP",
    "DPAD_DOWN": "DPAD_DOWN",
    "DPAD_LEFT": "DPAD_LEFT",
    "DPAD_RIGHT": "DPAD_RIGHT",
    "START": "START",
    "BACK": "BACK",
    "LEFT_SHOULDER": "LEFT_SHOULDER",
    "RIGHT_SHOULDER": "RIGHT_SHOULDER",
    "LEFT_THUMB": "LEFT_THUMB",
    "RIGHT_THUMB": "RIGHT_THUMB",
}


class InputSimulator:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config.get("actions", {})
        self._vg = None
        self._available = False
        self._init_vgamepad()

    def _init_vgamepad(self) -> None:
        try:
            import vgamepad as vg
            self._vg = vg.VX360Gamepad()
            self._available = True
            log.info("ViGEmBus gamepad initialized")
        except ImportError:
            log.warning("vgamepad not installed; install with: pip install vgamepad")
        except Exception as e:
            log.warning("Failed to initialize vgamepad: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    def press_button(self, button: str, hold_ms: int | None = None) -> None:
        if not self._available or self._vg is None:
            log.debug("Simulated press: %s", button)
            return

        b = BUTTON_MAP.get(button)
        if b is None:
            log.warning("Unknown button: %s", button)
            return

        duration = hold_ms or self._cfg.get("button_hold_duration", 100)
        btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)
        if btn_enum is None:
            log.warning("No XUSB enum for button: %s", b)
            return

        self._vg.press_button(btn_enum)
        self._vg.update()
        time.sleep(duration / 1000.0)
        self._vg.release_button(btn_enum)
        self._vg.update()

    def hold_button(self, button: str, hold_ms: int = 200) -> None:
        if not self._available or self._vg is None:
            log.debug("Simulated hold: %s %dms", button, hold_ms)
            return

        b = BUTTON_MAP.get(button)
        if b is None:
            return

        btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)

        self._vg.press_button(btn_enum)
        self._vg.update()
        time.sleep(hold_ms / 1000.0)

    def release_button(self, button: str) -> None:
        if not self._available or self._vg is None:
            return

        b = BUTTON_MAP.get(button)
        if b is None:
            return

        btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)
        self._vg.release_button(btn_enum)
        self._vg.update()

    def tap_button(self, button: str, taps: int = 2, hold_ms: int = 50) -> None:
        for _ in range(taps):
            self.press_button(button, hold_ms)
            time.sleep(0.05)

    def wait(self, ms: int) -> None:
        time.sleep(ms / 1000.0)

    def reset(self) -> None:
        if not self._available or self._vg is None:
            return
        self._vg.reset()
        self._vg.update()

    def shutdown(self) -> None:
        self.reset()
        self._vg = None
        self._available = False
