# ASScii: Video-to-ASS ASCII subtitle generator

[日本語](README.ja.md)

ASScii is a desktop tool that turns any video into live ASCII art and exports the frames as Aegisub-compatible ASS subtitles. The Tkinter UI shows the original feed and the ASCII rendering side by side, letting you fine-tune visual parameters and immediately push the same settings into a frame-by-frame subtitle export.

## Features
- Dual previews so you can compare the source video and the ASCII rendition in real time.
- Rich tuning parameters: grid columns/rows, FPS, gamma, contrast, brightness, inversion, and multiple character sets (Blocks / Classic / Dense).
- On-canvas erase/restore brushes for hiding sensitive areas before you export.
- Frame controls with slider/spinbox plus hotkeys for play/pause (`Space`), open (`o`), rewind (`r`), and export (`e`).
- ASS exporter that maps each rendered frame to a dialogue event with adjustable start time, duration, position, font, and PlayRes.
- Prefetch cache to keep playback smooth while scrubbing or looping.

## Requirements
- Python 3.10+ with Tkinter available.
- Python packages: `numpy`, `opencv-python`, `pillow`.
- macOS, Windows, and Linux are supported (ensure your Python build ships with Tk on macOS).
- Keep enough disk space and RAM when processing large clips; `big_buck_bunny_1080p_h264.mov` is included for testing.

## Setup
1. Create a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   ```
2. Install dependencies.
   ```bash
   python -m pip install --upgrade pip
   python -m pip install numpy opencv-python pillow
   ```
3. Fonts: the app looks for `DejaVuSansMono.ttf` by default. Place another monospace font next to the script or type the name in the export dialog if you prefer different lettering.

## Usage
### Launch the previewer
```bash
python ascii_video_preview.py               # pick a video via file dialog
python ascii_video_preview.py sample.mp4    # pass a path directly
```
Hotkeys:
- `o` — open video
- `Space` — toggle play/pause
- `r` — rewind to frame 0
- `e` — open the ASS export dialog

### Tune the ASCII renderer
- **Cols / Rows** set the ASCII grid resolution. Enable Lock aspect to maintain the video aspect ratio.
- **FPS** controls playback and export cadence. Higher FPS increases file size.
- **Gamma / Contrast / Brightness** adjust luminance before mapping pixels to characters.
- **Charset / Invert / Font size** customize the glyph palette, polarity, and on-screen font size.
- **Eraser / Restore** lets you paint masks directly on the ASCII preview per frame.
- **Frame slider / spinbox** jumps to any frame; playback loops when the file ends.

### Export ASS subtitles
1. Press `Export ASS (e)` to open the dialog.
2. Fill out:
   - `Start / Duration (sec)` — time window to render.
   - `Position X / Y` — ASS coordinates relative to `PlayResX / PlayResY`.
   - `Font name / Font size` — subtitle style; e.g., `DejaVu Sans Mono`.
   - `PlayResX / PlayResY` — target script resolution (e.g., 1920×1080).
3. Choose an `.ass` destination. Each frame becomes a `Dialogue` event with `\an7\pos(...)` so you can overlay anywhere.
4. Suggested pipeline: verify in Aegisub → convert via YTSubConverter → upload to YouTube.

## Tuning tips
- Higher column/row counts yield detail but explode processing time and subtitle size. Around `cols=100`, `fps=10–12` works well for YouTube captions.
- `Dense (16)` gives the smallest luminance steps, while `Blocks (5)` emphasizes chunky art styles.
- Use gamma and contrast to rescue crushed shadows or blown highlights.
- Drop brightness slightly if you want to limit flicker on bright scenes.
- Masks persist per frame/video; hit `Clear Eraser (frame)` to reset.

## Troubleshooting
- **Video fails to load** — re-encode to H.264 MP4.
  ```bash
  ffmpeg -i input.mov -c:v libx264 -crf 18 -preset veryfast -c:a aac output.mp4
  ```
- **Missing Tkinter** — install the OS package (e.g., `sudo apt install python3-tk` on Debian/Ubuntu).
- **Font misalignment** — stick to monospaced fonts and match the preview font to your export font.

## Sample clip
- Use the bundled `big_buck_bunny_1080p_h264.mov` to try the workflow immediately.

## License
A license file is not included yet. Add an appropriate license before distributing the project.
