#!/usr/bin/env python3
"""
NiClean - strip metadata and rename media files into iPhone/Android-style filenames.
- Copies media files into an output subfolder (does not modify originals).
- Uses exiftool for images and ffmpeg for videos when available (recommended).
- Designed for both double-click launchers and CLI usage.

MIT License

So don't go selling this without my permission or the the knights who say NI will demand a shrubbery!
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

APP_NAME = "NiClean"
APP_VERSION = "0.1.0"
DEFAULT_OUTPUT_FOLDER = "NiClean_cleaned"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

CONF_FILENAMES = {"mediacleaner.conf", "niclean.conf", "NiClean.conf"}


@dataclass
class Settings:
    naming: str = "iphone"  # iphone | android | samsung (future)
    output_folder: str = DEFAULT_OUTPUT_FOLDER
    include_subfolders: bool = False
    dry_run: bool = False
    keep_timestamps: bool = True
    # If true, require exiftool/ffmpeg; if false, proceed with copies+renames even if stripping unavailable.
    strict_tools: bool = False


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def load_conf(conf_path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not conf_path.exists():
        return data

    try:
        txt = conf_path.read_text(encoding="utf-8", errors="replace")
    except Exception as ex:
        eprint(f"[{APP_NAME}] Warning: Could not read config {conf_path.name}: {ex}")
        return data

    for ni in txt.splitlines():
        line = ni.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip().lower()] = v.strip()
    return data


def parse_bool(val: str) -> bool:
    v = val.strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def merge_settings(base: Settings, overrides: Dict[str, str]) -> Settings:
    s = Settings(**vars(base))
    for k, v in overrides.items():
        if k == "naming":
            s.naming = v.strip().lower()
        elif k == "output_folder":
            s.output_folder = v.strip()
        elif k == "include_subfolders":
            s.include_subfolders = parse_bool(v)
        elif k == "dry_run":
            s.dry_run = parse_bool(v)
        elif k == "keep_timestamps":
            s.keep_timestamps = parse_bool(v)
        elif k == "strict_tools":
            s.strict_tools = parse_bool(v)
    return s


def which_tool(name: str, script_dir: Path) -> Optional[Path]:
    """
    Find tool in ./tools first, then PATH.
    Supports Windows (.exe) and unix.
    """
    tools_dir = script_dir / "tools"
    candidates: List[Path] = []

    if platform.system().lower() == "windows":
        candidates.append(tools_dir / f"{name}.exe")
        candidates.append(tools_dir / name)
    else:
        candidates.append(tools_dir / name)

    for ni in candidates:
        if ni.exists() and os.access(ni, os.X_OK):
            return ni

    found = shutil.which(name)
    if found:
        return Path(found)
    return None


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def is_media_file(p: Path) -> bool:
    ext = p.suffix.lower()
    return ext in IMAGE_EXTS or ext in VIDEO_EXTS


def classify_media(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


def collect_files(root: Path, include_subfolders: bool, output_folder_name: str) -> List[Path]:
    files: List[Path] = []

    if include_subfolders:
        for ni in root.rglob("*"):
            if not ni.is_file():
                continue
            # Skip output folder contents
            try:
                if output_folder_name and (root / output_folder_name) in ni.parents:
                    continue
            except Exception:
                pass
            if is_media_file(ni):
                files.append(ni)
    else:
        for ni in root.iterdir():
            if not ni.is_file():
                continue
            if is_media_file(ni):
                files.append(ni)

    # Stable sort by mtime then name
    files.sort(key=lambda p: (p.stat().st_mtime, p.name.lower()))
    return files


def safe_makedirs(p: Path, dry_run: bool) -> None:
    if dry_run:
        return
    p.mkdir(parents=True, exist_ok=True)


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stem = p.stem
    ext = p.suffix
    parent = p.parent
    for ni in range(1, 1000000):
        candidate = parent / f"{stem}_{ni}{ext}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create unique filename for {p.name}")


def format_iphone_name(prefix: str, counter: int, ext: str) -> str:
    # Classic iPhone look: IMG_0001.JPG / VID_0001.MOV
    return f"{prefix}_{counter:04d}{ext}"


def format_android_name(prefix: str, dt: datetime, ext: str) -> str:
    # Common Android camera style: IMG_YYYYMMDD_HHMMSS.jpg / VID_YYYYMMDD_HHMMSS.mp4
    return f"{prefix}_{dt.strftime('%Y%m%d_%H%M%S')}{ext}"


def get_file_datetime_local(p: Path) -> datetime:
    # Use modified time as a consistent default
    ts = p.stat().st_mtime
    return datetime.fromtimestamp(ts)


def copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    shutil.copy2(src, dst)


def preserve_timestamps(src: Path, dst: Path, keep: bool, dry_run: bool) -> None:
    if not keep or dry_run:
        return
    st = src.stat()
    os.utime(dst, (st.st_atime, st.st_mtime))


def mac_clear_xattrs(p: Path, dry_run: bool) -> None:
    if platform.system().lower() != "darwin":
        return
    if dry_run:
        return
    # Clear extended attributes (quarantine, etc.) on the output file
    try:
        subprocess.run(["xattr", "-c", str(p)], check=False, capture_output=True, text=True)
    except Exception:
        pass


def strip_image_metadata_exiftool(exiftool: Path, in_path: Path, dry_run: bool) -> bool:
    """
    Strip EXIF/IPTC/XMP/etc from image using exiftool.
    Operates in-place on the copy.
    """
    if dry_run:
        return True
    cmd = [
        str(exiftool),
        "-all=",
        "-overwrite_original",
        "-P",
        str(in_path),
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        eprint(f"[{APP_NAME}] exiftool failed on {in_path.name}: {err.strip() or out.strip()}")
        return False
    return True


def strip_video_metadata_ffmpeg(ffmpeg: Path, in_path: Path, out_path: Path, dry_run: bool) -> bool:
    """
    Strip metadata from video using ffmpeg losslessly (stream copy).
    Writes to out_path.
    """
    if dry_run:
        return True

    # -map_metadata -1 removes global metadata. We also drop chapters.
    # Use -c copy to avoid re-encoding.
    cmd = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(in_path),
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-c", "copy",
        str(out_path),
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        eprint(f"[{APP_NAME}] ffmpeg failed on {in_path.name}: {err.strip() or out.strip()}")
        return False
    return True


def open_folder_in_file_manager(folder: Path) -> None:
    try:
        sysname = platform.system().lower()
        if sysname == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        elif sysname == "windows":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="niclean",
        description="NiClean: strip metadata + rename media into iPhone/Android-style filenames (copies into a subfolder).",
    )
    parser.add_argument("--input", "-in", default=".", help="Input folder (default: current folder).")
    parser.add_argument("--output", "-out", default=None, help=f"Output subfolder name (default: {DEFAULT_OUTPUT_FOLDER}).")
    parser.add_argument("--naming", choices=["iphone", "android"], default=None, help="Filename convention.")
    parser.add_argument("--include-subfolders", action="store_true", help="Process subfolders too.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen, without writing files.")
    parser.add_argument("--no-open", action="store_true", help="Don't open output folder when done.")
    parser.add_argument("--strict-tools", action="store_true", help="Fail if exiftool/ffmpeg are missing.")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        eprint(f"[{APP_NAME}] Error: Input folder not found: {input_dir}")
        return 2

    script_dir = Path(__file__).resolve().parent

    # Load config (first match in input folder, else script dir)
    conf_path: Optional[Path] = None
    for ni in CONF_FILENAMES:
        p1 = input_dir / ni
        p2 = script_dir / ni
        if p1.exists():
            conf_path = p1
            break
        if p2.exists():
            conf_path = p2
            break

    conf = load_conf(conf_path) if conf_path else {}
    settings = merge_settings(Settings(), conf)

    # CLI overrides
    if args.output is not None:
        settings.output_folder = args.output
    if args.naming is not None:
        settings.naming = args.naming
    if args.include_subfolders:
        settings.include_subfolders = True
    if args.dry_run:
        settings.dry_run = True
    if args.strict_tools:
        settings.strict_tools = True

    output_dir = (input_dir / settings.output_folder).resolve()
    safe_makedirs(output_dir, settings.dry_run)

    exiftool = which_tool("exiftool", script_dir)
    ffmpeg = which_tool("ffmpeg", script_dir)

    missing = []
    if exiftool is None:
        missing.append("exiftool (images)")
    if ffmpeg is None:
        missing.append("ffmpeg (videos)")

    if missing:
        msg = f"[{APP_NAME}] Note: Missing tools: {', '.join(missing)}. "
        msg += "Will still copy+rename, but metadata stripping may be skipped for those types."
        eprint(msg)
        if settings.strict_tools:
            eprint(f"[{APP_NAME}] strict_tools enabled; exiting.")
            return 3

    files = collect_files(input_dir, settings.include_subfolders, settings.output_folder)
    if not files:
        print(f"[{APP_NAME}] No media files found in: {input_dir}")
        return 0

    # Counters for iPhone-style naming (separate sequences)
    img_counter = 1
    vid_counter = 1

    print(f"[{APP_NAME}] Input:  {input_dir}")
    print(f"[{APP_NAME}] Output: {output_dir}")
    if conf_path:
        print(f"[{APP_NAME}] Config: {conf_path.name}")
    print(f"[{APP_NAME}] Naming: {settings.naming}")
    print(f"[{APP_NAME}] Files:  {len(files)}")
    if settings.dry_run:
        print(f"[{APP_NAME}] Dry-run: ON (no files will be written)")

    processed = 0
    skipped_strip = 0
    failed = 0

    for ni in files:
        media_type = classify_media(ni)
        ext = ni.suffix  # preserve original extension case
        dt = get_file_datetime_local(ni)

        if settings.naming == "iphone":
            if media_type == "image":
                new_name = format_iphone_name("IMG", img_counter, ext)
                img_counter += 1
            elif media_type == "video":
                new_name = format_iphone_name("VID", vid_counter, ext)
                vid_counter += 1
            else:
                # Shouldn't happen due to filter
                continue
        elif settings.naming == "android":
            if media_type == "image":
                new_name = format_android_name("IMG", dt, ext)
            elif media_type == "video":
                new_name = format_android_name("VID", dt, ext)
            else:
                continue
        else:
            eprint(f"[{APP_NAME}] Unknown naming mode: {settings.naming}")
            return 4

        # Put all outputs flat in output folder (even when scanning subfolders).
        dest_path = unique_path(output_dir / new_name)

        try:
            if media_type == "image":
                # Copy then strip in-place if exiftool available
                copy_file(ni, dest_path, settings.dry_run)
                if exiftool is not None:
                    ok = strip_image_metadata_exiftool(exiftool, dest_path, settings.dry_run)
                    if not ok:
                        failed += 1
                        continue
                else:
                    skipped_strip += 1

                preserve_timestamps(ni, dest_path, settings.keep_timestamps, settings.dry_run)
                mac_clear_xattrs(dest_path, settings.dry_run)

            elif media_type == "video":
                if ffmpeg is not None:
                    # ffmpeg writes output file; then preserve timestamps + xattrs
                    ok = strip_video_metadata_ffmpeg(ffmpeg, ni, dest_path, settings.dry_run)
                    if not ok:
                        failed += 1
                        continue
                else:
                    # Fallback: just copy (metadata likely preserved)
                    copy_file(ni, dest_path, settings.dry_run)
                    skipped_strip += 1

                preserve_timestamps(ni, dest_path, settings.keep_timestamps, settings.dry_run)
                mac_clear_xattrs(dest_path, settings.dry_run)

            processed += 1
            print(f"[{APP_NAME}] ✔ {ni.name}  ->  {dest_path.name}")

        except Exception as ex:
            failed += 1
            eprint(f"[{APP_NAME}] ✖ Failed on {ni.name}: {ex}")

    print(f"[{APP_NAME}] Done. Processed={processed}, Failed={failed}, StripSkipped={skipped_strip}")

    if processed > 0 and not args.no_open and not settings.dry_run:
        open_folder_in_file_manager(output_dir)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())