# ASScii: Video-to-ASS ASCII subtitle generator

[日本語](README.ja.md)

ASScii is a Tkinter-based desktop tool that converts videos into live ASCII art and exports every rendered frame as Aegisub-compatible ASS subtitles. It is optimized for creators who want to author stylized overlays or subtitles that can later be synced and published on video platforms.

![screenshot](imgs/screenshot.png)
[Sample Video is here.](https://youtu.be/F6egk1YDVNs?si=4CGu6RdAGxIfq4wy)

[Side by Side Ver.](https://youtube.com/shorts/jswRuja-WOU)

## Highlights
- Real-time dual preview so you can see the original frame and the ASCII rendition side by side.
- Rich tone and layout controls: grid size, FPS, gamma, contrast, brightness, inversion, charset presets, and font metrics with optional aspect locking.
- Per-frame erase/restore masks to hide areas directly on the ASCII canvas *and* carry those edits into the exported ASS.
- Frame-accurate ASS exporter with selectable ranges (full video / current frame / custom window) that writes one Dialogue event per rendered frame with configurable position, PlayRes, and style, automatically scaling the ASCII block to fit the video resolution.
- Smart monospace font detection (prefers `lucida-console.ttf`, falls back to Courier New, Menlo, DejaVu Sans Mono, etc.) so both the preview and exported subtitles share the same metrics.
- Modular code split across `ascii_core.py` (conversion utilities) and `ass_exporter.py` (subtitle writer) so you can script custom pipelines if needed.

## Repository layout
- `asscii_app.py` – GUI entry point (Tkinter + OpenCV + Pillow). Launch this script to run the previewer/exporter.
- `ascii_core.py` – reusable ASCII conversion helpers (`AsciiParams`, tone curve, image renderer, masking utility).
- `ass_exporter.py` – standalone ASS writer invoked by the GUI; can be imported into other scripts for batch jobs.

## Requirements
- Python 3.10 or newer with Tkinter available.
- Python packages:
  ```text
  numpy
  opencv-python
  pillow
  customtkinter
  ```
- A video file encoded with a format supported by OpenCV (H.264 MP4 works best).

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install numpy opencv-python pillow customtkinter
```
Optional: place your preferred monospace font (e.g., `lucida-console.ttf`, `DejaVuSansMono.ttf`) next to the scripts or install it system-wide. The app will auto-detect several popular fonts and mirror that selection in the export dialog.

## Usage
### Launching
```bash
python asscii_app.py            # open a file dialog
python asscii_app.py input.mp4  # skip the dialog
```

### Hotkeys & controls
- `o` – pick a video.
- `Space` – play/pause.
- `r` – rewind to frame 0.
- `e` – open the ASS export dialog.
- `Export Text` button – save the current ASCII frame as a plain `.txt` file.
- Slider/spinbox – jump to an arbitrary frame (loops when the end is reached).
- Lock aspect – ties row count to the current video aspect ratio using the active font metrics.
- Eraser (left drag) / Restore (right drag) – toggle per-cell masks; `Clear Eraser (frame)` resets the current frame mask.
  - Playback starts paused and aspect lock is enabled by default so you can tweak settings before rendering.

### Exporting ASS subtitles
1. Press `Export ASS (e)`.
2. Pick an export range: **Full video**, **Current frame** (one-frame snapshot), or **Custom** (manual start/duration). Provide position `(pos_x, pos_y)`, font info, and PlayRes values. Each rendered ASCII frame becomes a Dialogue event anchored with `\an7\pos(...)`.
3. Choose an output path to write the `.ass` file. Any erased cells are baked into the output.
4. Recommended workflow: review in Aegisub → convert via [YTSubConverter](https://github.com/arcusmaximus/YTSubConverter) if necessary → upload to YouTube (or similar).

### Exporting ASCII text
Press `Export Text` to dump the currently displayed ASCII frame (after masks) to a UTF-8 `.txt` file—handy for sharing static art or debugging.

### Programmatic use
If you want to batch-process footage, import `AsciiParams`, `frame_to_ascii`, or `export_ass` from `ascii_core.py` / `ass_exporter.py` and call them from your own scripts. The helper functions are pure Python and stay independent from the GUI.

## Tips
- Higher column/row counts drastically increase render time and subtitle size. Values around `cols=100`, `rows≈45`, `fps=10–12` offer a good balance for web playback.
- Try the `Dense (16)` charset for smooth gradients or `Blocks (5)` for bold posterized art.
- Adjust gamma and contrast before raising brightness; this keeps highlights from clipping.
- Use inversion when targeting light-on-dark video overlays.

## Sample media
This repository purposely does **not** bundle large videos. Download the Creative Commons film **Big Buck Bunny** from the Blender Foundation: [https://peach.blender.org/](https://peach.blender.org/) and point the previewer to the downloaded clip for testing.

## License
[MIT](LICENSE)
