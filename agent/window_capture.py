import time
import win32gui
import win32ui
import win32con
import win32api
import numpy as np
from PIL import Image
from typing import Tuple


class WindowCapture:
    def __init__(self, window_title_contains: str = "RetroArch"):
        self._title_filter = window_title_contains
        self._hwnd: int | None = None
        self._retry_count = 0

    def find_window(self) -> bool:
        def enum_cb(hwnd: int, _) -> None:
            if self._hwnd is not None:
                return
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if self._title_filter.lower() in title.lower():
                self._hwnd = hwnd

        self._hwnd = None
        win32gui.EnumWindows(enum_cb, None)
        return self._hwnd is not None

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    def wait_for_window(self, timeout: float = 30.0, poll: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.find_window():
                return True
            time.sleep(poll)
        return False

    def capture(self, scale: float = 1.0) -> Image.Image | None:
        if self._hwnd is None:
            if not self.find_window():
                return None

        hwnd = self._hwnd

        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w = right - left
        h = bottom - top
        if w <= 0 or h <= 0:
            return None

        left_screen, top_screen = win32gui.ClientToScreen(hwnd, (0, 0))

        hwnd_dc = win32gui.GetDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)

        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

        bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer("RGBA", (w, h), bits, "raw", "BGRA", 0, 1).convert("RGB")

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        if scale < 1.0:
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            img = img.resize((nw, nh), Image.LANCZOS)

        return img

    def list_windows(self, filter_str: str = "") -> list[dict]:
        results: list[dict] = []

        def enum_cb(hwnd: int, _) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if filter_str and filter_str.lower() not in title.lower():
                return
            rect = win32gui.GetWindowRect(hwnd)
            results.append({
                "hwnd": hwnd,
                "title": title,
                "rect": rect,
            })

        win32gui.EnumWindows(enum_cb, None)
        return results
