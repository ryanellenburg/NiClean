# NiClean
Metadata cleaner for image and video files

NiClean copies image/video files into a subfolder, strips metadata, and renames them into iPhone or Android style filenames.

- Default: iPhone naming (`IMG_0001.jpg`, `VID_0001.mp4`)
- Optional: Android naming (`IMG_YYYYMMDD_HHMMSS.jpg`, `VID_YYYYMMDD_HHMMSS.mp4`)
- Does **not** modify originals

## Requirements (recommended)
NiClean is lossless when these are available:

- **exiftool** (images)
- **ffmpeg** (videos)

NiClean will try:
1) `./tools/` (optional)
2) System PATH

If missing, NiClean will still copy+rename, but may skip stripping.

## Quick start

### macOS / Linux
```bash
python3 niclean.py