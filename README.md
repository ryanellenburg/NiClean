# NiClean

**NiClean** is a lightweight, open-source tool that:

- copies images/videos into a subfolder (never modifies originals)
- strips metadata (EXIF/XMP/IPTC for images; container metadata for videos)
- renames files into an **iPhone** or **Android**-style filename convention

**Default output folder:** `NiClean_cleaned`

## Download (recommended for non-technical users)

Go to the repo’s **Releases** page and download the build for your OS:

- **Windows:** `NiClean-windows-x64.exe` (double-click)
- **macOS:** `NiClean-macos-(arm64|x64).app` (double-click)
- **Linux:** `NiClean-linux-x64` (double-click or run from terminal)

These release builds bundle the needed helper binaries so you **do not** need to install anything extra.

> Note: on macOS/Linux, the image-cleaning helper (`exiftool`) is a script that usually runs using the system Perl that ships with macOS / most Linux distros. If your system lacks Perl (rare), NiClean will still copy+rename, and will skip stripping image metadata unless you provide a working `exiftool`.

## Quick use (double-click workflow) KISS - keep it simple stupid

1. Put the NiClean executable/app **inside the folder** that contains your media.
2. Double-click it.
3. Your cleaned copies appear in `NiClean_cleaned/`.

## CLI use (optional)

```bash
# Clean the current folder (or specify --input)
NiClean --naming iphone
NiClean --naming android --include-subfolders
NiClean --input "/path/to/folder" --output "cleaned"
```

## Filename conventions

- **iPhone (default):** `IMG_0001.JPG`, `VID_0001.MP4`
- **Android:** `IMG_YYYYMMDD_HHMMSS.JPG`, `VID_YYYYMMDD_HHMMSS.MP4`

## What metadata gets removed?

- **Images:** EXIF/IPTC/XMP and other common tags (using `exiftool -all=`).
- **Videos:** container metadata is removed by remuxing (no re-encode) when possible.

NiClean does **not** attempt to **add** or **fake** metadata. If you want “most realistic,” the safest non-fabricated approach is usually: *keep originals untouched* and *strip metadata on copies only*.

## Build from source (developers)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-build.txt
python NiClean.py --help
```

### Building executables

This repo includes a GitHub Actions workflow that builds release executables/apps for Windows, macOS, and Linux automatically.

If you want to build locally, use PyInstaller similarly to the workflow.

## Third-party notices

Release builds may redistribute:

- **ExifTool** (Phil Harvey) — used for image metadata removal. (ExifTool license: Perl Artistic License / GPL)
- **FFmpeg** — used for video metadata removal. (FFmpeg is licensed under LGPL/GPL depending on build/options)

See `THIRD_PARTY_NOTICES.md` for details and attribution.

## License

MIT — see `LICENSE`.

## Ni

Ni