import numpy as np
import cv2
from PIL import Image
from typing import Any


_COLOR_RANGES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "blue_cyan": ((90, 30, 30), (130, 255, 255)),
    "red": ((0, 100, 80), (10, 255, 255)),
    "red_alt": ((160, 100, 80), (180, 255, 255)),
    "gold_yellow": ((20, 80, 80), (45, 255, 255)),
    "green": ((40, 30, 30), (85, 200, 200)),
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

        # Crop to gameplay area (skip top ~12% for score, bottom 5% for HUD border)
        game_top = int(h * 0.12)
        game_bot = int(h * 0.95)
        game = gray[game_top:game_bot, :]
        gh, gw = game.shape
        cw = gw // 3

        # -- Left / Center / Right brightness --
        left = game[:, :cw]
        center = game[:, cw : 2 * cw]
        right = game[:, 2 * cw :]
        left_bright = float(np.mean(left))
        center_bright = float(np.mean(center))
        right_bright = float(np.mean(right))

        # -- Edge density --
        edges = cv2.Canny(game, 40, 120)
        edge_density = float(np.mean(edges)) / 255.0
        left_edges = float(np.mean(edges[:, :cw])) / 255.0
        center_edges = float(np.mean(edges[:, cw : 2 * cw])) / 255.0
        right_edges = float(np.mean(edges[:, 2 * cw :])) / 255.0

        # -- Ground detection: vertical brightness profile --
        # Find the row with the steepest brightness drop (sky → ground transition)
        row_means = np.array([np.mean(game[y, :]) for y in range(gh)])
        drops = np.diff(row_means)
        max_drop_idx = int(np.argmin(drops))  # most negative = biggest brightness drop
        max_drop = drops[max_drop_idx]

        # Ground line confidence: a sharp drop in the lower half of the screen
        ground_in_lower_half = max_drop_idx > gh // 2
        ground_confidence = 0.0
        if ground_in_lower_half and max_drop < -15:
            ground_confidence = min(1.0, -max_drop / 50.0)

        # Also check: does the bottom 30% of the game area have significantly darker pixels?
        bottom_section = game[int(gh * 0.7) :, :]
        bottom_mean = float(np.mean(bottom_section))
        top_mean = float(np.mean(game[: int(gh * 0.3), :]))
        sky_ground_gap = top_mean - bottom_mean  # positive = ground darker than sky

        has_ground = ground_confidence > 0.3 or sky_ground_gap > 15

        # -- Player position --
        hsv_full = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)

        def _pct(low, high, src=hsv_full):
            m = cv2.inRange(src, np.array(low), np.array(high))
            return float(np.mean(m)) / 255.0

        blue_pct = _pct(_COLOR_RANGES["blue_cyan"][0], _COLOR_RANGES["blue_cyan"][1])
        red_pct = max(
            _pct(_COLOR_RANGES["red"][0], _COLOR_RANGES["red"][1]),
            _pct(_COLOR_RANGES["red_alt"][0], _COLOR_RANGES["red_alt"][1]),
        )
        gold_pct = _pct(_COLOR_RANGES["gold_yellow"][0], _COLOR_RANGES["gold_yellow"][1])
        green_pct = _pct(_COLOR_RANGES["green"][0], _COLOR_RANGES["green"][1])

        # Blue pixel vertical position relative to game area
        blue_mask = cv2.inRange(hsv_full, np.array((90, 30, 30)), np.array((130, 255, 255)))
        blue_ys = np.where(blue_mask[game_top:game_bot, :] > 0)[0]
        blue_vert_pos = float(np.mean(blue_ys)) / gh if len(blue_ys) > 0 else 0.5

        # -- Motion --
        motion = 0.0
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            diff = cv2.absdiff(self._prev_gray, gray)
            motion = float(np.mean(diff)) / 255.0
        self._prev_gray = gray.copy()

        # -- Build description --
        lines: list[str] = []

        if has_ground:
            if blue_vert_pos < 0.4:
                lines.append("Ground below, player is in the air (jumping)")
            else:
                lines.append("Ground below, player on ground")
        else:
            lines.append("No ground visible")

        if motion > 0.05:
            lines.append(f"Screen scrolling (motion {motion:.2f})")
        elif motion > 0.02:
            lines.append(f"Slight motion ({motion:.2f})")

        if center_bright < left_bright - 8 and center_bright < right_bright - 8:
            lines.append("Something dark ahead")
        if left_edges > 0.12 and center_edges < 0.08:
            lines.append("Detail/obstacle on left")
        if right_edges > 0.12 and center_edges < 0.08:
            lines.append("Detail/obstacle on right")

        if blue_pct > 0.04:
            lines.append("Sonic (blue) visible")
        if red_pct > 0.03:
            lines.append("Enemy (red) visible")
        if gold_pct > 0.03:
            lines.append("Rings (gold) visible")

        if motion < 0.01 and not has_ground:
            lines.append("May be on menu/title screen")

        result["state_text"] = "\n".join(lines)
        result["processed_image"] = img
        result["width"] = w
        result["height"] = h

        return result
