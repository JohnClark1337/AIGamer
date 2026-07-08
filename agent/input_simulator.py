import logging
import time
from typing import Any

log = logging.getLogger(__name__)

KEY_MAP = {
    "A": 0x5A,          # Z
    "B": 0x58,          # X
    "X": 0x41,          # A
    "Y": 0x53,          # S
    "DPAD_UP": 0x26,    # UP
    "DPAD_DOWN": 0x28,  # DOWN
    "DPAD_LEFT": 0x25,  # LEFT
    "DPAD_RIGHT": 0x27, # RIGHT
    "START": 0x0D,      # RETURN
    "BACK": 0x08,       # BACKSPACE
    "LEFT_SHOULDER": 0x51,  # Q
    "RIGHT_SHOULDER": 0x57, # W
}

GAMEPAD_MAP = {
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
}


class InputSimulator:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config.get("actions", {})
        self._method = config.get("input", {}).get("method", "keyboard")
        self._key_map = dict(KEY_MAP)

        user_keys = config.get("input", {}).get("keys", {})
        for k, v in user_keys.items():
            if isinstance(v, str) and len(v) == 1:
                self._key_map[k] = ord(v.upper())
            elif isinstance(v, int):
                self._key_map[k] = v

        self._vg = None
        self._init_input()

    def _init_input(self) -> None:
        if self._method == "gamepad":
            try:
                import vgamepad as vg
                self._vg = vg.VX360Gamepad()
                log.info("ViGEmBus gamepad initialized")
            except Exception as e:
                log.warning("Gamepad init failed, falling back to keyboard: %s", e)
                self._method = "keyboard"

        log.info("Input method: %s", self._method)

    def _send_key(self, vk_code: int, press: bool) -> None:
        import win32api
        import win32con
        flags = 0
        if not press:
            flags = win32con.KEYEVENTF_KEYUP
        win32api.keybd_event(vk_code, 0, flags, 0)

    def _press_key(self, button: str, hold_ms: int) -> None:
        vk = self._key_map.get(button)
        if vk is None:
            log.warning("No key mapping for: %s", button)
            return
        self._send_key(vk, True)
        time.sleep(hold_ms / 1000.0)
        self._send_key(vk, False)

    def _press_gamepad(self, button: str, hold_ms: int) -> None:
        b = GAMEPAD_MAP.get(button)
        if b is None or self._vg is None:
            return
        btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)
        if btn_enum is None:
            return
        self._vg.press_button(btn_enum)
        self._vg.update()
        time.sleep(hold_ms / 1000.0)
        self._vg.release_button(btn_enum)
        self._vg.update()

    def press_button(self, button: str, hold_ms: int | None = None) -> None:
        duration = hold_ms or self._cfg.get("button_hold_duration", 100)
        if self._method == "keyboard":
            self._press_key(button, duration)
        else:
            self._press_gamepad(button, duration)

    def hold_button(self, button: str, hold_ms: int = 200) -> None:
        if self._method == "keyboard":
            vk = self._key_map.get(button)
            if vk is None:
                return
            self._send_key(vk, True)
            time.sleep(hold_ms / 1000.0)
        else:
            b = GAMEPAD_MAP.get(button)
            if b is None or self._vg is None:
                return
            btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)
            self._vg.press_button(btn_enum)
            self._vg.update()
            time.sleep(hold_ms / 1000.0)

    def release_button(self, button: str) -> None:
        if self._method == "keyboard":
            vk = self._key_map.get(button)
            if vk is None:
                return
            self._send_key(vk, False)
        else:
            b = GAMEPAD_MAP.get(button)
            if b is None or self._vg is None:
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
        if self._method == "gamepad" and self._vg is not None:
            self._vg.reset()
            self._vg.update()

    def shutdown(self) -> None:
        if self._method == "keyboard":
            for button in ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]:
                vk = self._key_map.get(button)
                if vk is not None:
                    try:
                        self._send_key(vk, False)
                    except Exception:
                        pass
        self.reset()
        self._vg = None
