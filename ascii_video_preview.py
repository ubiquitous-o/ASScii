
import sys
import time
import math
import threading
import queue
from pathlib import Path

import numpy as np
import cv2

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from PIL import Image, ImageTk, ImageFont

from ascii_core import (
    CHARSETS,
    AsciiParams,
    apply_mask_to_ascii_lines,
    frame_to_ascii,
    render_ascii_image,
)
from ass_exporter import export_ass


# ---------- UI App ----------

class App:
    def __init__(self, root: ctk.CTk, video_path: Path | None = None):
        self.root = root
        self.root.title("ASScii")
        self.root.geometry("1920x1080")
        self.root.resizable(False, False)

        self.cap = None
        self.video_path: Path | None = None
        self.video_fps = 30.0
        self.video_w = 1280
        self.video_h = 720
        self.video_frames = 0
        self.frame_index = 0
        self.paused = True
        self.last_tick = time.time()

        self.params = AsciiParams()
        self.erase_masks: dict[int, np.ndarray] = {}
        self._last_frame_bgr: np.ndarray | None = None
        self._last_frame_index: int | None = None
        self._ascii_render_size = (1, 1)
        self._ascii_display_size = (1, 1)
        self._ascii_render_grid_size = (1, 1)
        self._ascii_pad = 10
        self._rows_updating = False
        self._suppress_frame_var = False
        self.ascii_cache: dict[int, list[str]] = {}
        self._cache_lock = threading.Lock()
        self._prefetch_pending: set[int] = set()
        self._prefetch_radius = 8
        self._preload_queue: queue.Queue[int | None] | None = None
        self._preload_thread: threading.Thread | None = None
        self._preload_stop: threading.Event | None = None

        # Try load a monospace font; fallbackを順に試す
        self.fontname = "lucida-console.ttf"
        self._font_display_name = "Lucida Console"
        self.fontsize = 18
        self._font = self._load_font(self.fontsize)

        self._build_ui()

        if video_path:
            self.open_video(video_path)

        self.root.bind("<space>", self.toggle_pause)
        self.root.bind("o", lambda e: self.ask_open())
        self.root.bind("r", lambda e: self.rewind())
        self.root.bind("e", lambda e: self.ask_export())

        self._loop()

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        # Search common fonts
        candidates = [
            ("Lucida Console", self.fontname),
            ("Lucida Console", "lucida console.ttf"),
            ("Lucida Console", "Lucida Console.ttf"),
            ("Lucida Console", "lucon.ttf"),
            ("Lucida Console", "C:/Windows/Fonts/lucida-console.ttf"),
            ("Lucida Console", "C:/Windows/Fonts/lucon.ttf"),
            ("Lucida Console", "/Library/Fonts/Lucida Console.ttf"),
            ("Lucida Console", "/System/Library/Fonts/Lucida Console.ttf"),
            ("Courier New", "C:/Windows/Fonts/cour.ttf"),
            ("Courier New", "Courier New.ttf"),
            ("Courier New", "C:/Windows/Fonts/couri.ttf"),
            ("DejaVu Sans Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
            ("Menlo", "/Library/Fonts/Menlo.ttc"),
            ("Menlo", "/System/Library/Fonts/Menlo.ttc"),
            ("Courier", "/usr/share/fonts/truetype/freefont/FreeMono.ttf"),
        ]
        for display_name, path in candidates:
            try:
                font = ImageFont.truetype(path, size=size)
                self._font_display_name = display_name
                return font
            except Exception:
                continue
        # fallback
        self._font_display_name = "TkDefaultFont"
        return ImageFont.load_default()

    def _build_ui(self):
        main = ctk.CTkFrame(self.root, corner_radius=12)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        preview = ctk.CTkFrame(main, corner_radius=12)
        preview.pack(fill="both", expand=True)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_columnconfigure(1, weight=1)
        preview.grid_rowconfigure(0, weight=1)

        def build_preview_card(parent, title: str, column: int):
            card = ctk.CTkFrame(parent)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 12, 0), pady=12)
            card.grid_rowconfigure(1, weight=1)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=title, anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
            container = ctk.CTkFrame(card, fg_color="transparent")
            container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)
            img_label = tk.Label(container, text="", bg="#111111", fg="#f5f5f5", bd=0, highlightthickness=0)
            img_label.grid(row=0, column=0, sticky="nsew")
            return img_label

        self.orig_label = build_preview_card(preview, "Original", 0)
        self.ascii_label = build_preview_card(preview, "ASCII", 1)
        self.ascii_label.bind("<Button-1>", self._on_ascii_erase)
        self.ascii_label.bind("<B1-Motion>", self._on_ascii_erase)
        self.ascii_label.bind("<Button-3>", self._on_ascii_restore)
        self.ascii_label.bind("<B3-Motion>", self._on_ascii_restore)
        self.ascii_label.bind("<Button-2>", self._on_ascii_restore)
        self.ascii_label.bind("<B2-Motion>", self._on_ascii_restore)
        self.ascii_label.bind("<Control-Button-1>", self._on_ascii_restore)
        self.ascii_label.bind("<Control-B1-Motion>", self._on_ascii_restore)

        transport = ctk.CTkFrame(main, corner_radius=12)
        transport.pack(fill="x", pady=(8, 0))

        self.frame_entry_var = tk.StringVar(value="0")

        transport_buttons = ctk.CTkFrame(transport, fg_color="transparent")
        transport_buttons.pack(fill="x", padx=8, pady=(8, 4))
        transport_buttons.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(transport_buttons, text="Open (o)", command=self.ask_open).grid(
            row=0, column=0, padx=4, pady=4, sticky="ew"
        )
        ctk.CTkButton(transport_buttons, text="Pause/Play (space)", command=self.toggle_pause).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew"
        )
        ctk.CTkButton(transport_buttons, text="Rewind (r)", command=self.rewind).grid(
            row=0, column=2, padx=4, pady=4, sticky="ew"
        )

        frame_ctrl = ctk.CTkFrame(transport)
        frame_ctrl.pack(fill="x", padx=8, pady=(0, 8))
        frame_ctrl.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_ctrl, text="Frame").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.frame_slider = ctk.CTkSlider(frame_ctrl, from_=0, to=1, command=self._on_frame_slider)
        self.frame_slider.grid(row=0, column=1, sticky="ew")

        self.frame_entry = ctk.CTkEntry(frame_ctrl, textvariable=self.frame_entry_var, width=80, justify="center")
        self.frame_entry.grid(row=0, column=2, padx=(12, 0))
        self.frame_entry.bind("<Return>", self._on_frame_entry_commit)
        self.frame_entry.bind("<FocusOut>", self._on_frame_entry_commit)

        self.frame_label_var = tk.StringVar(value="Frame 0 / 0")
        ctk.CTkLabel(frame_ctrl, textvariable=self.frame_label_var).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        self.info_var = tk.StringVar(
            value="Open a video to start. (hotkeys: o open, space pause, r rewind, e export)"
        )
        ctk.CTkLabel(transport, textvariable=self.info_var, anchor="w").pack(
            fill="x", padx=8, pady=(0, 8)
        )

        controls = ctk.CTkFrame(main, corner_radius=12)
        controls.pack(fill="x", pady=(8, 0))

        actions = ctk.CTkFrame(controls, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(8, 4))
        actions.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(actions, text="Export ASS (e)", command=self.ask_export).grid(
            row=0, column=0, padx=4, pady=4, sticky="ew"
        )
        ctk.CTkButton(actions, text="Export Text", command=self.ask_export_text).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew"
        )
        ctk.CTkButton(actions, text="Clear Eraser", command=self._clear_erase_mask).grid(
            row=0, column=2, padx=4, pady=4, sticky="ew"
        )

        opts = ctk.CTkFrame(controls)
        opts.pack(fill="x", padx=8, pady=(4, 0))
        for c in range(9):
            opts.grid_columnconfigure(c, weight=1)

        self.cols_var = tk.IntVar(value=self.params.cols)
        self.rows_var = tk.IntVar(value=self.params.rows)
        self.fps_var = tk.IntVar(value=int(round(self.params.fps)))
        self.gamma_var = tk.DoubleVar(value=self.params.gamma)
        self.contrast_var = tk.DoubleVar(value=self.params.contrast)
        self.brightness_var = tk.DoubleVar(value=self.params.brightness)
        self.invert_var = tk.BooleanVar(value=self.params.invert)
        self.charset_var = tk.StringVar(value=self.params.charset_name)
        self.fontsize_var = tk.StringVar(value=str(self.fontsize))
        self.lock_aspect_var = tk.BooleanVar(value=True)
        self.frame_var = tk.IntVar(value=0)

        self.cols_display = tk.StringVar(value=str(self.params.cols))
        self.rows_display = tk.StringVar(value=str(self.params.rows))

        def bind_int_display(source: tk.Variable, target: tk.StringVar):
            def sync(*_):
                try:
                    target.set(str(int(source.get())))
                except Exception:
                    try:
                        target.set(str(source.get()))
                    except Exception:
                        target.set("?")
            source.trace_add("write", sync)
            sync()

        def add_slider(row, col, label, var, frm, to, step=None, display_var=None):
            base_col = col * 3
            ctk.CTkLabel(opts, text=label).grid(row=row, column=base_col, sticky="w", padx=(0, 6), pady=6)
            slider = ctk.CTkSlider(opts, from_=frm, to=to)
            slider.grid(row=row, column=base_col + 1, sticky="ew", padx=(0, 10))
            val_var = display_var if display_var is not None else var
            ctk.CTkLabel(opts, textvariable=val_var, width=60, anchor="w").grid(row=row, column=base_col + 2, sticky="w")

            def on_move(value, var=var, step=step):
                snapped = float(value)
                if step:
                    snapped = round(snapped / step) * step
                if isinstance(var, tk.IntVar):
                    var.set(int(round(snapped)))
                else:
                    var.set(snapped)

            slider.configure(command=on_move)

            def sync_from_var(*_):
                try:
                    slider.set(float(var.get()))
                except Exception:
                    pass

            var.trace_add("write", sync_from_var)
            sync_from_var()
            return slider

        add_slider(0, 0, "Cols", self.cols_var, 20, 200, step=1.0, display_var=self.cols_display)
        self.rows_slider = add_slider(0, 1, "Rows", self.rows_var, 10, 120, step=1.0, display_var=self.rows_display)
        add_slider(0, 2, "FPS", self.fps_var, 2, 30, step=1.0)

        add_slider(1, 0, "Gamma", self.gamma_var, 0.3, 3.0)
        add_slider(1, 1, "Contrast", self.contrast_var, 0.3, 3.0)
        add_slider(1, 2, "Brightness", self.brightness_var, -100, 100)

        extra = ctk.CTkFrame(controls)
        extra.pack(fill="x", padx=8, pady=(8, 0))

        ctk.CTkLabel(extra, text="Charset").pack(side="left", padx=(0, 6))
        charset_menu = ctk.CTkOptionMenu(extra, variable=self.charset_var, values=list(CHARSETS.keys()))
        charset_menu.pack(side="left")

        ctk.CTkSwitch(extra, text="Invert", variable=self.invert_var).pack(side="left", padx=10)

        ctk.CTkLabel(extra, text="Font size").pack(side="left", padx=(10, 6))
        font_entry = ctk.CTkEntry(extra, textvariable=self.fontsize_var, width=60, justify="center")
        font_entry.pack(side="left")
        font_entry.bind("<Return>", lambda *_: self._on_fontsize())
        font_entry.bind("<FocusOut>", lambda *_: self._on_fontsize())

        ctk.CTkSwitch(extra, text="Lock aspect", variable=self.lock_aspect_var).pack(side="left", padx=(12, 0))

        # transport frame already includes playback info and frame controls

        for var in [
            self.cols_var,
            self.rows_var,
            self.fps_var,
            self.gamma_var,
            self.contrast_var,
            self.brightness_var,
            self.invert_var,
            self.charset_var,
        ]:
            var.trace_add("write", lambda *args: self._sync_params())

        self.cols_var.trace_add("write", lambda *args: self._maybe_lock_aspect())
        bind_int_display(self.cols_var, self.cols_display)
        bind_int_display(self.rows_var, self.rows_display)
        self.fontsize_var.trace_add("write", lambda *args: self._on_fontsize_var())
        self.lock_aspect_var.trace_add("write", lambda *args: self._on_aspect_lock_toggle())
        self.frame_var.trace_add("write", self._on_frame_var_changed)
        self.frame_var.trace_add("write", lambda *args: self.frame_entry_var.set(str(max(0, int(self.frame_var.get())))))

        self._on_aspect_lock_toggle()
        self._update_frame_controls()

    def _on_fontsize(self):
        try:
            self.fontsize = int(self.fontsize_var.get())
            self._font = self._load_font(self.fontsize)
        except Exception:
            pass
        self._apply_aspect_lock()

    def _on_fontsize_var(self, *args):
        self._on_fontsize()

    def _sync_params(self):
        prev = AsciiParams(**vars(self.params))
        self.params.cols = max(10, int(self.cols_var.get()))
        self.params.rows = max(5, int(self.rows_var.get()))
        self.params.fps = max(0.1, float(self.fps_var.get()))
        self.params.gamma = float(self.gamma_var.get())
        self.params.contrast = float(self.contrast_var.get())
        self.params.brightness = float(self.brightness_var.get())
        self.params.invert = bool(self.invert_var.get())
        self.params.charset_name = self.charset_var.get()

        dims_changed = self.params.cols != prev.cols or self.params.rows != prev.rows
        tone_changed = (
            self.params.gamma != prev.gamma or
            self.params.contrast != prev.contrast or
            self.params.brightness != prev.brightness or
            self.params.invert != prev.invert or
            self.params.charset_name != prev.charset_name
        )

        if dims_changed:
            self._reset_all_masks()
        if dims_changed or tone_changed:
            self._clear_ascii_cache()
            self._refresh_ascii_preview()

    def _set_frame_index(self, idx: int, update_slider: bool = True):
        idx = max(0, idx)
        self.frame_index = idx
        if update_slider and hasattr(self, "frame_var"):
            self._suppress_frame_var = True
            try:
                self.frame_var.set(idx)
            finally:
                self._suppress_frame_var = False
        self._update_frame_label()

    def _update_frame_label(self):
        if not hasattr(self, "frame_label_var"):
            return
        if self.video_frames > 0:
            max_idx = self.video_frames - 1
            clamped = max(0, min(self.frame_index, max_idx))
            self.frame_label_var.set(f"Frame {clamped} / {max_idx}")
        else:
            self.frame_label_var.set("Frame - / -")

    def _update_frame_controls(self):
        max_idx = max(0, self.video_frames - 1)
        if hasattr(self, "frame_slider"):
            to_value = max(1, max_idx)
            self.frame_slider.configure(to=to_value)
        if hasattr(self, "frame_var"):
            self._suppress_frame_var = True
            try:
                self.frame_var.set(max(0, min(self.frame_index, max_idx)))
            finally:
                self._suppress_frame_var = False
        if hasattr(self, "frame_slider"):
            self.frame_slider.set(max(0, min(self.frame_index, max_idx)))
        if hasattr(self, "frame_entry_var"):
            self.frame_entry_var.set(str(max(0, min(self.frame_index, max_idx))))
        self._update_frame_label()

    def _on_frame_slider(self, value):
        if self._suppress_frame_var:
            return
        self.frame_var.set(int(round(float(value))))

    def _on_frame_entry_commit(self, *_):
        try:
            idx = int(self.frame_entry_var.get())
        except ValueError:
            self.frame_entry_var.set(str(max(0, self.frame_index)))
            return
        if self.video_frames > 0:
            idx = max(0, min(idx, self.video_frames - 1))
        else:
            idx = max(0, idx)
        self.frame_var.set(idx)

    def _on_frame_var_changed(self, *args):
        if self._suppress_frame_var or self.cap is None or self.video_frames <= 0:
            return
        try:
            idx = int(self.frame_var.get())
        except Exception:
            return
        idx = max(0, min(idx, self.video_frames - 1))
        self._seek_to_frame(idx)

    def _seek_to_frame(self, idx: int, pause: bool = True):
        if self.cap is None:
            return
        if self.video_frames > 0:
            idx = max(0, min(idx, self.video_frames - 1))
        else:
            idx = max(0, idx)
        if pause:
            self.paused = True
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if not ok:
            return
        self._set_frame_index(idx)
        self._update_previews(frame)
        self.last_tick = time.time()

    def _get_font_cell_size(self) -> tuple[int, int]:
        cell_w = max(1, int(self.fontsize * 0.6))
        cell_h = max(1, int(self.fontsize))
        try:
            ascent, descent = self._font.getmetrics()
            cell_h = max(1, ascent + descent)
        except Exception:
            pass
        try:
            length = self._font.getlength("M")
        except Exception:
            length = None
        if length is None:
            try:
                bbox = self._font.getbbox("M")
                length = bbox[2] - bbox[0]
            except Exception:
                length = None
        if length is not None:
            cell_w = max(1, int(math.ceil(length)))
        else:
            try:
                cell_w = max(1, self._font.getsize("M")[0])
            except Exception:
                pass
        return cell_w, cell_h

    def _get_ascii_grid_pixel_size(self) -> tuple[int, int]:
        cached = getattr(self, "_ascii_render_grid_size", None)
        if cached and cached[0] > 0 and cached[1] > 0:
            return cached
        cell_w, cell_h = self._get_font_cell_size()
        return max(1, cell_w * max(1, self.params.cols)), max(1, cell_h * max(1, self.params.rows))

    def _clone_params(self) -> AsciiParams:
        return AsciiParams(**vars(self.params))

    def _clear_ascii_cache(self):
        with self._cache_lock:
            self.ascii_cache.clear()
            self._prefetch_pending.clear()

    def _store_ascii_lines(self, frame_idx: int | None, lines: list[str]):
        if frame_idx is None:
            return
        with self._cache_lock:
            self.ascii_cache[frame_idx] = lines
            self._prefetch_pending.discard(frame_idx)

    def _get_cached_ascii_lines(self, frame_idx: int | None) -> list[str] | None:
        if frame_idx is None:
            return None
        with self._cache_lock:
            return self.ascii_cache.get(frame_idx)

    def _ensure_ascii_lines(self, frame_idx: int | None, frame_bgr: np.ndarray | None,
                            params: AsciiParams | None = None) -> list[str] | None:
        cached = self._get_cached_ascii_lines(frame_idx)
        if cached is not None:
            return cached
        if frame_bgr is None:
            return None
        use_params = params or self.params
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        lines = frame_to_ascii(gray, use_params)
        self._store_ascii_lines(frame_idx, lines)
        return lines

    def _reset_all_masks(self):
        self.erase_masks.clear()

    def _get_mask_for_frame(self, frame_idx: int | None, create: bool = False) -> np.ndarray | None:
        if frame_idx is None or frame_idx < 0:
            return None
        expected_shape = (self.params.rows, self.params.cols)
        mask = self.erase_masks.get(frame_idx)
        if mask is None and create:
            mask = np.zeros(expected_shape, dtype=bool)
            self.erase_masks[frame_idx] = mask
        elif mask is not None and mask.shape != expected_shape:
            if create:
                mask = np.zeros(expected_shape, dtype=bool)
                self.erase_masks[frame_idx] = mask
            else:
                return None
        return mask

    def _clear_erase_mask(self):
        idx = self.frame_index if self.frame_index is not None else None
        if idx is None:
            return
        if idx in self.erase_masks:
            del self.erase_masks[idx]
            self._refresh_ascii_preview()

    def _refresh_ascii_preview(self):
        if self._last_frame_bgr is None:
            return
        max_w, max_h = self._get_preview_target_size(self.ascii_label)
        idx = self._last_frame_index if self._last_frame_index is not None else self.frame_index
        self._render_ascii_frame(self._last_frame_bgr, idx, max_w, max_h)

    def _schedule_prefetch(self, center_idx: int):
        if self.video_frames <= 0 or self._preload_queue is None:
            return
        for offset in range(1, self._prefetch_radius + 1):
            for candidate in (center_idx + offset, center_idx - offset):
                self._enqueue_prefetch(candidate)

    def _enqueue_prefetch(self, idx: int):
        if self._preload_queue is None or self.video_frames <= 0:
            return
        if idx < 0 or idx >= self.video_frames:
            return
        with self._cache_lock:
            if idx in self.ascii_cache or idx in self._prefetch_pending:
                return
            self._prefetch_pending.add(idx)
        try:
            self._preload_queue.put_nowait(idx)
        except Exception:
            with self._cache_lock:
                self._prefetch_pending.discard(idx)

    def _start_preload_worker(self):
        self._stop_preload_worker()
        if self.video_path is None:
            return
        self._preload_stop = threading.Event()
        self._preload_queue = queue.Queue()
        self._preload_thread = threading.Thread(target=self._prefetch_worker, daemon=True)
        self._preload_thread.start()

    def _stop_preload_worker(self):
        if self._preload_stop is not None:
            self._preload_stop.set()
        if self._preload_queue is not None:
            try:
                self._preload_queue.put_nowait(None)
            except Exception:
                pass
        if self._preload_thread is not None:
            self._preload_thread.join(timeout=1.0)
        self._preload_thread = None
        self._preload_queue = None
        self._preload_stop = None
        with self._cache_lock:
            self._prefetch_pending.clear()

    def _prefetch_worker(self):
        path = self.video_path
        if path is None:
            return
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return
        while self._preload_stop is not None and not self._preload_stop.is_set():
            try:
                idx = self._preload_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if idx is None:
                break
            with self._cache_lock:
                if idx in self.ascii_cache:
                    self._prefetch_pending.discard(idx)
                    continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                with self._cache_lock:
                    self._prefetch_pending.discard(idx)
                continue
            params = self._clone_params()
            self._ensure_ascii_lines(idx, frame, params=params)
        cap.release()

    def _render_ascii_frame(self, frame_bgr: np.ndarray | None, frame_idx: int | None,
                            max_w: int, max_h: int):
        base_lines = self._ensure_ascii_lines(frame_idx, frame_bgr)
        if base_lines is None:
            return
        lines = self._apply_erase_mask_to_lines(base_lines, frame_idx)

        pad = 10
        ascii_img = render_ascii_image(lines, font=self._font, pad=pad)
        render_size = ascii_img.size
        grid_render_w = max(render_size[0] - pad * 2, 1)
        grid_render_h = max(render_size[1] - pad * 2, 1)
        ascii_img.thumbnail((max_w, max_h), Image.BICUBIC)
        display_size = ascii_img.size

        self._ascii_pad = pad
        self._ascii_render_size = render_size
        self._ascii_display_size = display_size
        self._ascii_render_grid_size = (grid_render_w, grid_render_h)

        self._ascii_tk = ImageTk.PhotoImage(ascii_img)
        self.ascii_label.configure(image=self._ascii_tk)

    def _get_preview_target_size(self, label, min_w: int = 320, min_h: int = 240) -> tuple[int, int]:
        try:
            w = max(1, int(label.winfo_width()))
            h = max(1, int(label.winfo_height()))
            if w > 1 and h > 1:
                return max(min_w, w - 16), max(min_h, h - 16)
        except Exception:
            pass
        fallback_w = max(min_w, self.root.winfo_width() // 2 - 32)
        fallback_h = max(min_h, self.root.winfo_height() - 220)
        return fallback_w, fallback_h

    def _apply_erase_mask_to_lines(self, lines: list[str], frame_idx: int | None) -> list[str]:
        mask = self._get_mask_for_frame(frame_idx, create=False)
        return apply_mask_to_ascii_lines(lines, mask)

    def _event_to_ascii_cell(self, event) -> tuple[int, int] | None:
        disp_w, disp_h = self._ascii_display_size
        render_w, render_h = self._ascii_render_size
        if disp_w <= 0 or disp_h <= 0:
            return None
        try:
            label_w = max(1, self.ascii_label.winfo_width())
            label_h = max(1, self.ascii_label.winfo_height())
        except Exception:
            label_w = disp_w
            label_h = disp_h

        offset_x = max((label_w - disp_w) / 2.0, 0.0)
        offset_y = max((label_h - disp_h) / 2.0, 0.0)

        local_x = event.x - offset_x
        local_y = event.y - offset_y

        if local_x < 0 or local_y < 0 or local_x >= disp_w or local_y >= disp_h:
            return None

        x = local_x * (render_w / disp_w)
        y = local_y * (render_h / disp_h)
        pad = getattr(self, "_ascii_pad", 0)
        grid_w, grid_h = getattr(self, "_ascii_render_grid_size", (1, 1))
        cols = max(1, self.params.cols)
        rows = max(1, self.params.rows)
        if grid_w <= 0 or grid_h <= 0:
            return None
        cell_w = grid_w / cols
        cell_h = grid_h / rows
        slack_x = max(cell_w * 0.5, 2.0)
        slack_y = max(cell_h * 0.5, 2.0)
        grid_left = pad
        grid_top = pad
        grid_right = pad + grid_w
        grid_bottom = pad + grid_h
        if (x < grid_left - slack_x or x > grid_right + slack_x or
                y < grid_top - slack_y or y > grid_bottom + slack_y):
            return None

        norm_x = (x - pad) / max(cell_w, 1e-6)
        norm_y = (y - pad) / max(cell_h, 1e-6)
        norm_x = min(max(norm_x, 0.0), cols - 1e-6)
        norm_y = min(max(norm_y, 0.0), rows - 1e-6)
        col = int(norm_x)
        row = int(norm_y)
        return row, col

    def _apply_erase_event(self, event, erase: bool):
        if self._last_frame_bgr is None:
            return
        cell = self._event_to_ascii_cell(event)
        if cell is None:
            return
        mask = self._get_mask_for_frame(self.frame_index, create=True)
        if mask is None:
            return
        row, col = cell
        if mask[row, col] == erase:
            return
        mask[row, col] = erase
        self._refresh_ascii_preview()

    def _on_ascii_erase(self, event):
        self._apply_erase_event(event, True)

    def _on_ascii_restore(self, event):
        self._apply_erase_event(event, False)

    def _current_video_ratio(self) -> float | None:
        if self.video_w <= 0 or self.video_h <= 0:
            return None
        return self.video_w / self.video_h

    def _apply_aspect_lock(self):
        if self._rows_updating or not self.lock_aspect_var.get():
            return
        ratio = self._current_video_ratio()
        if not ratio:
            return
        cell_w, cell_h = self._get_font_cell_size()
        if cell_h <= 0 or cell_w <= 0:
            return
        cols = max(10, int(self.cols_var.get()))
        target_rows = max(5, int(round((cols * cell_w) / (ratio * cell_h))))
        if target_rows == int(self.rows_var.get()):
            return
        self._rows_updating = True
        try:
            self.rows_var.set(target_rows)
        finally:
            self._rows_updating = False

    def _maybe_lock_aspect(self, *args):
        if self.lock_aspect_var.get():
            self._apply_aspect_lock()

    def _on_aspect_lock_toggle(self):
        if hasattr(self, "rows_slider"):
            state = "disabled" if self.lock_aspect_var.get() else "normal"
            self.rows_slider.configure(state=state)
        if self.lock_aspect_var.get():
            self._apply_aspect_lock()

    def ask_open(self):
        p = filedialog.askopenfilename(
            title="Open video",
            filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi *.webm"), ("All files", "*.*")]
        )
        if p:
            self.open_video(Path(p))

    def open_video(self, path: Path):
        self._stop_preload_worker()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self._clear_ascii_cache()
        self._reset_all_masks()
        self._last_frame_bgr = None
        self._last_frame_index = None

        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open video. Try converting it to H.264 MP4.")
            return

        self.video_path = path
        self.video_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.video_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        self.video_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        self.video_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if self.video_frames < 0:
            self.video_frames = 0
        self._set_frame_index(0)
        self.paused = True
        self.erase_masks.clear()
        self._update_frame_controls()

        frames_text = f" | {self.video_frames} frames" if self.video_frames else ""
        self.info_var.set(f"Loaded: {path.name}  |  {self.video_w}x{self.video_h} @ {self.video_fps:.2f}fps{frames_text}")
        self._apply_aspect_lock()
        self._start_preload_worker()
        self._seek_to_frame(0, pause=False)

    def toggle_pause(self, event=None):
        self.paused = not self.paused

    def rewind(self):
        if self.cap is None:
            return
        self._seek_to_frame(0)

    def _read_next_frame(self):
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok:
            # loop
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
            if not ok:
                return None
        pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES) or 1) - 1
        if pos < 0:
            pos = 0
        self._set_frame_index(pos)
        return frame

    def _update_previews(self, frame_bgr: np.ndarray):
        # Original preview: resize to fit label area (approx)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        orig = Image.fromarray(frame_rgb)
        self._last_frame_bgr = frame_bgr.copy()
        self._last_frame_index = self.frame_index

        max_w, max_h = self._get_preview_target_size(self.orig_label)
        orig.thumbnail((max_w, max_h), Image.BICUBIC)

        self._orig_tk = ImageTk.PhotoImage(orig)
        self.orig_label.configure(image=self._orig_tk)

        # ASCII preview
        ascii_w, ascii_h = self._get_preview_target_size(self.ascii_label)
        self._render_ascii_frame(frame_bgr, self.frame_index, ascii_w, ascii_h)
        self._schedule_prefetch(self.frame_index)

    def ask_export(self):
        if self.video_path is None:
            messagebox.showinfo("Export", "Open a video first.")
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Export ASS (frame-by-frame)")
        dlg.geometry("560x420")

        start_var = tk.DoubleVar(value=0.0)
        dur_var = tk.DoubleVar(value=5.0)
        x_var = tk.IntVar(value=0)
        y_var = tk.IntVar(value=0)
        fontsize_var = tk.IntVar(value=self.fontsize)
        playx_var = tk.IntVar(value=int(self.video_w) if self.video_w else 1920)
        playy_var = tk.IntVar(value=int(self.video_h) if self.video_h else 1080)
        fontname_var = tk.StringVar(value=getattr(self, "_font_display_name", "Lucida Console"))
        mode_var = tk.StringVar(value="range")

        frm = ctk.CTkFrame(dlg, corner_radius=12)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        def row(label, var, r, hint=""):
            ctk.CTkLabel(frm, text=label).grid(row=r, column=0, sticky="w", pady=4)
            ent = ctk.CTkEntry(frm, textvariable=var)
            ent.grid(row=r, column=1, sticky="ew", pady=4)
            if hint:
                ctk.CTkLabel(frm, text=hint).grid(row=r, column=2, sticky="w", padx=8)
            return ent

        frm.columnconfigure(1, weight=1)

        start_entry = row("Start (sec)", start_var, 0, "e.g., 12.5")
        dur_entry = row("Duration (sec)", dur_var, 1, "keep small; ASS gets huge")
        row("Position X", x_var, 2, "PlayRes coords")
        row("Position Y", y_var, 3, "PlayRes coords")
        row("Font name", fontname_var, 4, "ASS style")
        row("Font size", fontsize_var, 5, "")
        row("PlayResX", playx_var, 6, "")
        row("PlayResY", playy_var, 7, "")

        ctk.CTkLabel(frm, text="Export range").grid(row=8, column=0, sticky="w", pady=(12, 0))
        range_opts = ctk.CTkFrame(frm)
        range_opts.grid(row=8, column=1, columnspan=2, sticky="w", pady=(12, 0))

        def update_range_state(*_):
            state = "normal" if mode_var.get() == "range" else "disabled"
            for widget in (start_entry, dur_entry):
                widget.configure(state=state)

        ctk.CTkRadioButton(range_opts, text="Full video", value="full",
                           variable=mode_var, command=update_range_state).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(range_opts, text="Current frame", value="current",
                           variable=mode_var, command=update_range_state).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(range_opts, text="Custom", value="range",
                           variable=mode_var, command=update_range_state).pack(side="left")

        update_range_state()

        def do_export():
            out = filedialog.asksaveasfilename(
                title="Save .ass",
                defaultextension=".ass",
                filetypes=[("Aegisub ASS", "*.ass")]
            )
            if not out:
                return
            try:
                self._sync_params()
                mode = mode_var.get()
                start_sec = max(float(start_var.get()), 0.0)
                dur_sec: float | None
                if mode == "full":
                    start_sec = 0.0
                    dur_sec = None
                elif mode == "current":
                    if self.frame_index is None:
                        raise RuntimeError("No frame selected for export.")
                    frame_idx = max(int(self.frame_index), 0)
                    video_fps = max(float(self.video_fps), 1e-6)
                    start_sec = frame_idx / video_fps
                    dur_sec = 1.0 / max(self.params.fps, 1e-6)
                else:
                    dur_value = float(dur_var.get())
                    if dur_value <= 0:
                        raise ValueError("Duration must be positive.")
                    dur_sec = dur_value

                expected_shape = (self.params.rows, self.params.cols)

                def mask_lookup(idx: int) -> np.ndarray | None:
                    if idx is None:
                        return None
                    mask = self.erase_masks.get(int(idx))
                    if mask is None or mask.shape != expected_shape:
                        return None
                    return mask

                grid_pixel_w, grid_pixel_h = self._get_ascii_grid_pixel_size()

                export_ass(
                    video_path=self.video_path,
                    out_path=Path(out),
                    params=self.params,
                    start_sec=start_sec,
                    dur_sec=dur_sec,
                    pos_x=int(x_var.get()),
                    pos_y=int(y_var.get()),
                    fontname=str(fontname_var.get()),
                    fontsize=int(fontsize_var.get()),
                    play_res_x=int(playx_var.get()),
                    play_res_y=int(playy_var.get()),
                    grid_pixel_w=grid_pixel_w,
                    grid_pixel_h=grid_pixel_h,
                    mask_lookup=mask_lookup,
                )
                messagebox.showinfo("Export", f"Saved:\n{out}\n\nTip: run through Aegisub → YTSubConverter → YouTube.")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Export error", str(e))

        ctk.CTkButton(frm, text="Export", command=do_export).grid(row=9, column=0, pady=12)
        ctk.CTkButton(frm, text="Cancel", command=dlg.destroy).grid(row=9, column=1, pady=12, sticky="w")

    def ask_export_text(self):
        if self._last_frame_bgr is None:
            messagebox.showinfo("Export", "Render a frame first.")
            return
        self._sync_params()
        lines = self._ensure_ascii_lines(self.frame_index, self._last_frame_bgr)
        if lines is None:
            messagebox.showerror("Export", "Could not convert current frame to ASCII.")
            return
        lines = self._apply_erase_mask_to_lines(lines, self.frame_index)
        out = filedialog.asksaveasfilename(
            title="Save ASCII text",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")]
        )
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Export", f"Saved ASCII text:\n{out}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def _loop(self):
        # target tick
        target_dt = 1.0 / max(self.params.fps, 0.1)

        now = time.time()
        elapsed = now - self.last_tick

        if not self.paused and elapsed >= target_dt:
            self.last_tick = now
            frame = self._read_next_frame()
            if frame is not None:
                self._update_previews(frame)

        self.root.after(10, self._loop)


def main():
    video_path = None
    if len(sys.argv) >= 2:
        video_path = Path(sys.argv[1]).expanduser().resolve()
        if not video_path.exists():
            print(f"File not found: {video_path}")
            sys.exit(1)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = App(root, video_path=video_path)
    root.mainloop()

if __name__ == "__main__":
    main()
