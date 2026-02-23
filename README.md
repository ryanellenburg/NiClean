# NiClean

**NiClean** is a lightweight, open-source tool that:

- copies images/videos into a subfolder (never modifies originals)
- strips metadata (EXIF/XMP/IPTC for images; container metadata for videos)
- renames files into an **iPhone** or **Android**-style filename convention

**Why did I build it?**

- Easy privacy tool to wipe any metadata from images and videos.
- MetadataCleaner alternative to OS outside of Linux/Flatpak.
- ExifPurge limited to image files.
- I have not found solutions that adjust file naming convention in bulk.

**Default output folder:** `NiClean_cleaned`

## Download & Use (recommended)

Go to the **Releases** page and download the zip for your OS:

- **Windows:** NiClean-Windows.zip → run `NiClean.exe` TESTING AND WORKING OUT BUGS
- **macOS:** NiClean-macOS.zip → run `NiClean.app` NOT TESTED YET
- **Linux:** NiClean-Linux.zip → run `NiClean` NOT TESTED YET

### Basic use (no terminal)
1) Put NiClean in a folder containing photos/videos (or point at requested directory)
2) Double-click NiClean  
3) Choose **iPhone** or **Android** preset  
4) Click **Clean this folder**

Outputs are written to: `NiClean_cleaned/`  
Original files are never modified.

## CLI use (optional)

You can still run NiClean from a terminal:

```bash
NiClean --naming iphone
NiClean --naming android
```
Options:

--input <folder>
--output <folder>
--include-subfolders
--dry-run
--gui

## Filename conventions

- **iPhone (default):** `IMG_0001.JPG`, `VID_0001.MP4`
- **Android:** `IMG_YYYYMMDD_HHMMSS.JPG`, `VID_YYYYMMDD_HHMMSS.MP4`

## What metadata gets removed?

- **Images:** EXIF/IPTC/XMP and other common tags (using `exiftool -all=`).
- **Videos:** container metadata is removed by remuxing (no re-encode) when possible.

NiClean does **not** attempt to **add** or **fake** metadata. If you want “most realistic,” the safest non-fabricated approach is usually: *keep originals untouched* and *strip metadata on copies only*.

## Presets

### iPhone preset
- Images → **JPG**
- Videos → **MOV**
- Filenames: `IMG_0001.JPG`, `VID_0001.MOV`

### Android preset
- Images → **JPG**
- Videos → **MP4**
- Filenames: `IMG_YYYYMMDD_HHMMSS.JPG`, `VID_YYYYMMDD_HHMMSS.MP4`



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

See `NOTICE` for details and attribution.

## License

See `LICENSE`.

## Ni

Ni

## Notes and Updates

- Light mode / dark mode
- Make app look like it isn't from windows 95
- Fixed a few grammar issues, look for more
- Images testing successfully
- Videos testing (need to find videos with a lot of EXIF)
- Plan to include to leave file names as is
- Plan to include option to overwrite files
- Reference to knights who say ni