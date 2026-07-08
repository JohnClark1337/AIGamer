import logging
import time
import ctypes
import threading
from ctypes import wintypes
from typing import Any

log = logging.getLogger(__name__)

PUL = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ki", _KEYBDINPUT),
    ]


KEY_MAP = {
    "A": 0x5A,  # Z
    "B": 0x58,  # X
    "X": 0x41,  # A
    "Y": 0x53,  # S
    "DPAD_UP": 0x26,  # UP
    "DPAD_DOWN": 0x28,  # DOWN
    "DPAD_LEFT": 0x25,  # LEFT
    "DPAD_RIGHT": 0x27,  # RIGHT
    "START": 0x0D,  # RETURN
    "BACK": 0x08,  # BACKSPACE
    "LEFT_SHOULDER": 0x51,  # Q
    "RIGHT_SHOULDER": 0x57,  # W
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

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_sendinput = ctypes.windll.user32.SendInput
_sendinput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
_sendinput.restype = wintypes.UINT


def _send_input(vk_code: int, press: bool) -> None:
    flags = 0
    if not press:
        flags = _KEYEVENTF_KEYUP
    inp = _INPUT(type=_INPUT_KEYBOARD)
    inp.ki = _KEYBDINPUT(vk_code, 0, flags, 0, None)
    _sendinput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


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
        self._held_keys: dict[str, threading.Event] = {}
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

    def _press_key(self, button: str, hold_ms: int) -> None:
        vk = self._key_map.get(button)
        if vk is None:
            log.warning("No key mapping for: %s", button)
            return
        _send_input(vk, True)
        time.sleep(hold_ms / 1000.0)
        _send_input(vk, False)

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
        vk = self._key_map.get(button)
        if vk is None:
            return
        _send_input(vk, True)
        time.sleep(hold_ms / 1000.0)

    def _repeat_key(self, button: str, vk: int, stop: threading.Event) -> None:
        _send_input(vk, True)
        while not stop.is_set():
            stop.wait(0.15)
            if stop.is_set():
                break
            _send_input(vk, True)

    def hold_continuous(self, button: str) -> None:
        if button in self._held_keys:
            return
        vk = self._key_map.get(button)
        if vk is None:
            return
        stop = threading.Event()
        self._held_keys[button] = stop
        if self._method == "keyboard":
            t = threading.Thread(target=self._repeat_key, args=(button, vk, stop), daemon=True)
            t.start()
        else:
            b = GAMEPAD_MAP.get(button)
            if b is None or self._vg is None:
                return
            btn_enum = getattr(self._vg.XUSB_BUTTON, b, None)
            self._vg.press_button(btn_enum)
            self._vg.update()

    def release_button(self, button: str) -> None:
        stop = self._held_keys.pop(button, None)
        if stop is not None:
            stop.set()
        vk = self._key_map.get(button)
        if vk is None:
            return
        if self._method == "keyboard":
            _send_input(vk, False)
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
        for btn in list(self._held_keys.keys()):
            self.release_button(btn)
        if self._method == "keyboard":
            for button in ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]:
                vk = self._key_map.get(button)
                if vk is not None:
                    try:
                        _send_input(vk, False)
                    except Exception:
                        pass
        self.reset()
        self._vg = None
