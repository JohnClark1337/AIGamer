from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
from typing import Any


class StateProcessor:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config.get("state_processing", {})
        self._ocr_available = False
        self._ocr = None

        if self._cfg.get("enable_ocr", False):
            try:
                import pytesseract
                self._ocr = pytesseract
                self._ocr_available = True
            except ImportError:
                pass

    def process(self, img: Image.Image) -> dict[str, Any]:
        result: dict[str, Any] = {"image": img}

        processed = img.copy()

        if self._cfg.get("grayscale", True):
            processed = processed.convert("L").convert("RGB")

        if self._cfg.get("contrast_enhance", False):
            enhancer = ImageEnhance.Contrast(processed)
            processed = enhancer.enhance(1.5)

        result["processed_image"] = processed

        if self._ocr_available:
            try:
                text = self._ocr.image_to_string(
                    processed,
                    lang=self._cfg.get("ocr_lang", "eng"),
                )
                result["ocr_text"] = text.strip()
            except Exception:
                result["ocr_text"] = ""

        result["width"] = img.width
        result["height"] = img.height

        return result
