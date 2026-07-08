import yaml
import os
from typing import Any


DEFAULT_CONFIG = {
    "ollama": {
        "host": "http://localhost:11434",
        "model": "llama3.2-vision:11b",
        "temperature": 0.2,
        "num_predict": 128,
    },
    "game_loop": {
        "fps": 4,
        "max_steps": 0,
        "cooldown_after_action": 0.3,
        "screenshot_scale": 0.5,
    },
    "emulator": {
        "window_title_contains": "RetroArch",
        "capture_method": "windows",
    },
    "state_processing": {
        "enable_ocr": False,
        "ocr_lang": "eng",
        "grayscale": True,
        "contrast_enhance": False,
    },
    "actions": {
        "allowed_buttons": [
            "A", "B", "X", "Y",
            "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
            "START", "BACK",
            "LEFT_SHOULDER", "RIGHT_SHOULDER",
        ],
        "button_hold_duration": 0.1,
        "dpad_hold_duration": 0.15,
    },
    "logging": {
        "level": "INFO",
        "save_screenshots": False,
        "screenshot_dir": "screenshots",
    },
}


def load_config(path: str | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)

    search_paths = [
        path,
        os.environ.get("OGA_CONFIG"),
        "config.yaml",
        os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
    ]

    for sp in search_paths:
        if sp and os.path.isfile(sp):
            with open(sp, encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            _deep_merge(cfg, user)
            break

    return cfg


def _deep_merge(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
