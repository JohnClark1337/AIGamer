import numpy as np
import cv2
from PIL import Image
from typing import Any


# Generic game colors in HSV
_COLOR_RANGES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "blue_cyan": ((90, 30, 30), (130, 255, 255)),
    "red": ((0, 100, 80), (10, 255, 255)),
    "red_alt": ((160, 100, 80), (180, 255, 255)),
    "gold_yellow": ((20, 80, 80), (45, 255, 255)),
    "green": ((40, 30, 30), (85, 200, 200)),
    "white_bright": ((0, 0, 200), (180, 30, 255)),
}


class StateProcessor:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config.get("state_processing", {})
        self._prev_gray: np.ndarray | None = None
        self._frame_count = 0

    def process(self, img: Image.Image) -> dict[str, Any]:
        self._frame_count += 1
        result: dict[str, Any] = {"image": img}

        arr = np.array(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape

        # Crop to gameplay area (skip top ~12% for score, bottom ~8% for HUD)
        game_top = int(h * 0.12)
        game_bot = int(h * 0.92)
        game_h = game_bot - game_top
        game_gray = gray[game_top:game_bot, :]
        game_hsv = cv2.cvtColor(arr[game_top:game_bot, :, :], cv2.COLOR_RGB2HSV)

        # -- Left / Center / Right brightness --
        cw = w // 3
        left_region = game_gray[:, :cw]
        center_region = game_gray[:, cw : 2 * cw]
        right_region = game_gray[:, 2 * cw :]

        left_bright = float(np.mean(left_region))
        center_bright = float(np.mean(center_region))
        right_bright = float(np.mean(right_region))

        # -- Edge density per strip --
        edges = cv2.Canny(game_gray, 40, 120)
        edge_density = float(np.mean(edges)) / 255.0
        left_edges = float(np.mean(edges[:, :cw])) / 255.0
        center_edges = float(np.mean(edges[:, cw : 2 * cw])) / 255.0
        right_edges = float(np.mean(edges[:, 2 * cw :])) / 255.0

        # -- Ground detection (lower 40% of game area) --
        lower_half = game_gray[game_h * 3 // 5 :, :]
        lower_edges = float(np.mean(cv2.Canny(lower_half, 40, 120))) / 255.0
        lower_mean = float(np.mean(lower_half))
        lower_std = float(np.std(lower_half))

        # Look for a horizontal ground line: strong horizontal edges in lower portion
        sobel_x = np.abs(cv2.Sobel(lower_half, cv2.CV_64F, 1, 0, ksize=3))
        horiz_edge_strength = float(np.mean(sobel_x)) / 255.0

        # Check if the bottom portion has significant brightness change (ground/sky boundary)
        bottom_row = game_gray[game_h - 5 :, :]
        row_above = game_gray[game_h - 15 : game_h - 10, :]
        bottom_mean = float(np.mean(bottom_row))
        above_mean = float(np.mean(row_above))

        has_ground = lower_edges > 0.08 or horiz_edge_strength > 0.03 or abs(bottom_mean - above_mean) > 20

        # -- Color analysis --
        hsv_full = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)

        def color_pct(lower, upper, hsv_img=hsv_full) -> float:
            mask = cv2.inRange(hsv_img, np.array(lower), np.array(upper))
            return float(np.mean(mask)) / 255.0

        blue_pct = color_pct(_COLOR_RANGES["blue_cyan"][0], _COLOR_RANGES["blue_cyan"][1])
        red_pct = max(
            color_pct(_COLOR_RANGES["red"][0], _COLOR_RANGES["red"][1]),
            color_pct(_COLOR_RANGES["red_alt"][0], _COLOR_RANGES["red_alt"][1]),
        )
        gold_pct = color_pct(_COLOR_RANGES["gold_yellow"][0], _COLOR_RANGES["gold_yellow"][1])
        green_pct = color_pct(_COLOR_RANGES["green"][0], _COLOR_RANGES["green"][1])

        # -- Motion --
        motion = 0.0
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            diff = cv2.absdiff(self._prev_gray, gray)
            motion = float(np.mean(diff)) / 255.0
        self._prev_gray = gray.copy()

        # -- Build description --
        lines: list[str] = []
        lines.append(f"Screen: {w}x{h}")
        lines.append(f"Frame: {self._frame_count} Motion: {motion:.2f}")
        lines.append(f"Edges: L={left_edges:.2f} C={center_edges:.2f} R={right_edges:.2f}")
        lines.append(f"Brightness: L={left_bright:.0f} C={center_bright:.0f} R={right_bright:.0f}")
        lines.append(f"Colors: blue={blue_pct:.2f} red={red_pct:.2f} gold={gold_pct:.2f} green={green_pct:.2f}")

        if has_ground:
            lines.append("Ground below")
        else:
            lines.append("No ground below")

        if center_bright < left_bright - 8 and center_bright < right_bright - 8:
            lines.append("Dark area in center")
        if left_edges > 0.12 and center_edges < 0.08:
            lines.append("Detail on left")
        if right_edges > 0.12 and center_edges < 0.08:
            lines.append("Detail on right")
        if left_edges < 0.03 and center_edges < 0.03 and right_edges < 0.03:
            lines.append("Low detail (open area or menu)")

        if blue_pct > 0.04:
            lines.append("Player (blue) detected")
        if red_pct > 0.03:
            lines.append("Enemy (red) detected")
        if gold_pct > 0.03:
            lines.append("Rings (gold) detected")
        if motion > 0.04:
            lines.append(f"Motion: {motion:.2f}")

        result["state_text"] = "\n".join(lines)
        result["processed_image"] = img
        result["width"] = w
        result["height"] = h

        return result
