"""ASCII変換や描画に関するユーティリティ群."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


CHARSETS = {
    "Blocks (5)": " ░▒▓█",
    "Classic (10)": " .:-=+*#%@",
    "Dense (16)": " .'`\",:;Il!i><~+_-?][}{1)(|\\/*tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
}


@dataclass
class AsciiParams:
    cols: int = 80
    rows: int = 45
    fps: float = 12.0
    charset_name: str = "Blocks (5)"
    custom_charset: str = ""
    invert: bool = True
    binarize: bool = False
    binarize_threshold: int = 128
    gamma: float = 1.0
    contrast: float = 1.0
    brightness: float = 0.0  # -100..100


def apply_tone(gray: np.ndarray, gamma: float, contrast: float, brightness: float) -> np.ndarray:
    """トーン調整。"""
    x = gray.astype(np.float32) / 255.0
    x = np.power(np.clip(x, 0.0, 1.0), 1.0 / max(gamma, 1e-6))
    x = (x - 0.5) * contrast + 0.5
    x = x + (brightness / 100.0) * 0.5
    x = np.clip(x, 0.0, 1.0)
    return (x * 255.0).astype(np.uint8)


def frame_to_ascii(gray: np.ndarray, params: AsciiParams) -> list[str]:
    """グレースケールフレームをASCII行配列に変換."""
    small = cv2.resize(gray, (params.cols, params.rows), interpolation=cv2.INTER_AREA)
    small = apply_tone(small, params.gamma, params.contrast, params.brightness)

    if params.binarize:
        thresh = int(np.clip(params.binarize_threshold, 0, 255))
        small = np.where(small >= thresh, 255, 0).astype(np.uint8)

    if params.invert:
        small = 255 - small

    custom_charset = (params.custom_charset or "").rstrip("\n")
    if params.charset_name == "Custom" and custom_charset:
        charset = custom_charset
    else:
        charset = CHARSETS.get(params.charset_name, CHARSETS["Blocks (5)"])
    if not charset:
        charset = CHARSETS["Blocks (5)"]
    n = len(charset)
    idx = (small.astype(np.float32) / 255.0) * (n - 1)
    idx = (n - 1 - idx).astype(np.int32)
    return ["".join(charset[i] for i in row) for row in idx]


def render_ascii_image(
    lines: Iterable[str],
    font: ImageFont.FreeTypeFont,
    pad: int = 8,
    fg=(245, 245, 245),
    bg=(10, 10, 10),
) -> Image.Image:
    """ASCIIテキストをPillow画像に描画."""
    lines = list(lines)
    ascent, descent = font.getmetrics()
    char_length = None
    try:
        char_length = font.getlength("M")
    except Exception:
        pass
    if char_length is None:
        try:
            bbox = font.getbbox("M")
            char_length = bbox[2] - bbox[0]
        except Exception:
            pass
    if char_length is None:
        try:
            char_length = font.getsize("M")[0]
        except Exception:
            pass
    if char_length is not None:
        cell_w = max(1, int(np.ceil(char_length)))
    else:
        cell_w = 1
    cell_h = max(1, ascent + descent)

    cols = max((len(s) for s in lines), default=0)
    rows = len(lines)

    w = pad * 2 + cols * cell_w
    h = pad * 2 + rows * cell_h

    img = Image.new("RGB", (max(1, w), max(1, h)), color=bg)
    draw = ImageDraw.Draw(img)

    y = pad
    for line in lines:
        draw.text((pad, y), line, font=font, fill=fg)
        y += cell_h
    return img


def apply_mask_to_ascii_lines(lines: list[str], mask: np.ndarray | None) -> list[str]:
    """指定されたマスクでASCII行を消去."""
    if mask is None:
        return lines
    rows = min(len(lines), mask.shape[0])
    if rows == 0:
        return lines
    masked: list[str] = []
    for r in range(rows):
        line_chars = list(lines[r])
        mask_row = mask[r]
        cols = min(len(line_chars), mask_row.shape[0])
        for c in range(cols):
            if mask_row[c]:
                line_chars[c] = " "
        masked.append("".join(line_chars))
    return masked + lines[rows:]
