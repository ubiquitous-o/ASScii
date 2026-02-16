"""ASCII変換や描画に関するユーティリティ群."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, NamedTuple

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
    color: bool = False
    binarize: bool = False
    binarize_threshold: int = 128
    binarize_custom_mode: str = "gradient"
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


def frame_to_ascii(gray: np.ndarray, params: AsciiParams, drop_leading_char: bool = False) -> list[str]:
    """グレースケールフレームをASCII行配列に変換."""
    small = cv2.resize(gray, (params.cols, params.rows), interpolation=cv2.INTER_AREA)
    small = apply_tone(small, params.gamma, params.contrast, params.brightness)

    binary_mask: np.ndarray | None = None
    if params.binarize:
        thresh = int(np.clip(params.binarize_threshold, 0, 255))
        binary_mask = small >= thresh
        small = np.where(binary_mask, 255, 0).astype(np.uint8)

    if params.invert:
        small = 255 - small
        if binary_mask is not None:
            binary_mask = ~binary_mask

    custom_charset = (params.custom_charset or "").rstrip("\n")
    custom_selected = params.charset_name == "Custom" and custom_charset
    if custom_selected:
        charset = custom_charset
    else:
        charset = CHARSETS.get(params.charset_name, CHARSETS["Blocks (5)"])
    if not charset:
        charset = CHARSETS["Blocks (5)"]
    if drop_leading_char and charset and charset[0] == " " and len(charset) > 1:
        charset = charset[1:]

    use_pattern = (
        params.binarize and
        custom_selected and
        params.binarize_custom_mode == "pattern" and
        binary_mask is not None
    )

    if use_pattern:
        pattern = charset
        if len(pattern) == 0:
            pattern = CHARSETS["Blocks (5)"]
        pat_len = len(pattern)
        idx = 0
        lines: list[str] = []
        mask = binary_mask
        for r in range(mask.shape[0]):
            row_chars: list[str] = []
            for c in range(mask.shape[1]):
                if mask[r, c]:
                    row_chars.append(pattern[idx % pat_len])
                    idx += 1
                else:
                    row_chars.append(" ")
            lines.append("".join(row_chars))
        return lines

    n = len(charset)
    idx = (small.astype(np.float32) / 255.0) * (n - 1)
    idx = (n - 1 - idx).astype(np.int32)
    return ["".join(charset[i] for i in row) for row in idx]


class AsciiResult(NamedTuple):
    lines: list[str]
    colors: np.ndarray | None  # shape (rows, cols, 3) RGB uint8


def frame_to_ascii_result(frame_bgr: np.ndarray, params: AsciiParams) -> AsciiResult:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    lines = frame_to_ascii(gray, params)
    colors: np.ndarray | None = None

    if params.color:
        small_bgr = cv2.resize(frame_bgr, (params.cols, params.rows), interpolation=cv2.INTER_AREA)
        toned = np.empty_like(small_bgr)
        for ch in range(3):  # B, G, R order
            toned[..., ch] = apply_tone(small_bgr[..., ch], params.gamma, params.contrast, params.brightness)
        if params.binarize:
            thresh = int(np.clip(params.binarize_threshold, 0, 255))
            mask = (cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY) >= thresh)
            if params.invert:
                mask = ~mask
            toned = np.where(mask[..., None], 255, 0).astype(np.uint8)
        # convert to RGB for Pillow / ASS
        colors = cv2.cvtColor(toned, cv2.COLOR_BGR2RGB)

    return AsciiResult(lines=lines, colors=colors)


def render_ascii_image(
    lines: Iterable[str],
    font: ImageFont.FreeTypeFont,
    colors: np.ndarray | None = None,
    pad: int = 8,
    fg=(245, 245, 245),
    bg=(10, 10, 10),
) -> Image.Image:
    """ASCIIテキストをPillow画像に描画（カラー対応）。"""
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

    has_colors = colors is not None and hasattr(colors, "shape")

    y = pad
    for r, line in enumerate(lines):
        if has_colors:
            # 1行を同色連続ランでまとめて描画し回数を削減
            row_colors = colors[r] if r < colors.shape[0] else None
        else:
            row_colors = None

        if row_colors is None:
            draw.text((pad, y), line, font=font, fill=fg)
        else:
            run_chars: list[str] = []
            run_color = tuple(int(x) for x in row_colors[0]) if len(row_colors) else fg
            run_start = 0

            def flush_run(end_idx: int):
                nonlocal run_start, run_chars, run_color
                if not run_chars:
                    return
                x = pad + run_start * cell_w
                draw.text((x, y), "".join(run_chars), font=font, fill=run_color)
                run_chars = []

            for c, ch in enumerate(line):
                col_val = tuple(int(x) for x in row_colors[c]) if c < len(row_colors) else fg
                if not run_chars:
                    run_chars.append(ch)
                    run_color = col_val
                    run_start = c
                elif col_val == run_color:
                    run_chars.append(ch)
                else:
                    flush_run(c)
                    run_chars = [ch]
                    run_color = col_val
                    run_start = c
            flush_run(len(line))
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


def apply_mask_to_colors(colors: np.ndarray | None, mask: np.ndarray | None, bg=(10, 10, 10)) -> np.ndarray | None:
    """マスク位置を背景色に置き換えたカラー配列を返す."""
    if colors is None or mask is None:
        return colors
    rows = min(colors.shape[0], mask.shape[0])
    cols = min(colors.shape[1], mask.shape[1])
    result = colors.copy()
    result[:rows, :cols][mask[:rows, :cols]] = np.array(bg, dtype=result.dtype)
    return result
