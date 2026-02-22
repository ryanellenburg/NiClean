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
APP_VERSION = "0.2.0"
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



def get_runtime_root() -> Path:
    """Return a base directory for bundled resources (PyInstaller) or source checkout."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parent


def get_default_target_dir() -> Path:
    """Folder to clean when user double-clicks the executable/app."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # If running as a macOS .app bundle, prefer the folder containing the .app.
        for parent in [exe] + list(exe.parents):
            if parent.name.endswith(".app"):
                return parent.parent
        return exe.parent
    # When running from source, default to current working directory.
    return Path.cwd()
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
    Find tool in bundled ./tools first, then PATH.
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


def should_launch_gui() -> bool:
    # If user passes any CLI args, assume CLI.
    if len(sys.argv) > 1:
        return False
    # If there's no TTY (common when double-clicking), GUI feels more natural.
    try:
        return not sys.stdout.isatty()
    except Exception:
        return True


def get_best_timestamp(p: Path) -> datetime:
    # For now, use file modified time (local) as a stable, non-fabricated timestamp.
    return get_file_datetime_local(p)


def make_output_name(naming: str, kind: str, ext: str, counter: int, ts: Optional[datetime]) -> str:
    prefix = "IMG" if kind == "image" else "VID"
    # iPhone filenames are typically uppercase extensions; keep that look without changing formats.
    out_ext = ext.upper()
    if naming == "android":
        dt = ts or get_file_datetime_local(Path("."))
        return format_android_name(prefix, dt, out_ext)
    return format_iphone_name(prefix, counter, out_ext)

def run_gui(default_input_dir: Path) -> int:
    """Tiny stdlib GUI (tkinter) for non-CLI users."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        # No tkinter (rare) -> fall back to CLI.
        return run_cli(default_input_dir, Settings(), open_output=True)

    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION}")

    # State
    naming_var = tk.StringVar(value="iphone")
    subfolders_var = tk.BooleanVar(value=False)
    strict_var = tk.BooleanVar(value=False)

    # Layout
    frm = tk.Frame(root, padx=12, pady=12)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text=f"{APP_NAME}", font=("Arial", 16, "bold")).pack(anchor="w")
    tk.Label(frm, text=f"Folder to clean:\n{default_input_dir}", justify="left").pack(anchor="w", pady=(4, 10))

    box1 = tk.LabelFrame(frm, text="Filename style", padx=10, pady=8)
    box1.pack(fill="x", pady=(0, 10))
    tk.Radiobutton(box1, text="iPhone (IMG_0001 / VID_0001)", variable=naming_var, value="iphone").pack(anchor="w")
    tk.Radiobutton(box1, text="Android (IMG_YYYYMMDD_HHMMSS)", variable=naming_var, value="android").pack(anchor="w")

    box2 = tk.LabelFrame(frm, text="Options", padx=10, pady=8)
    box2.pack(fill="x", pady=(0, 10))
    tk.Checkbutton(box2, text="Include subfolders", variable=subfolders_var).pack(anchor="w")
    tk.Checkbutton(box2, text="Strict mode (fail if tools missing)", variable=strict_var).pack(anchor="w")

    btns = tk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))

    def on_run() -> None:
        s = Settings(
            naming=naming_var.get(),
            include_subfolders=bool(subfolders_var.get()),
            strict_tools=bool(strict_var.get()),
        )
        rc = run_cli(default_input_dir, s, open_output=True)
        if rc == 0:
            messagebox.showinfo(APP_NAME, "Done! Check the output folder.")
            root.destroy()
        else:
            messagebox.showerror(APP_NAME, f"Finished with errors (code {rc}).\nSee console/log output for details.")

    def on_cancel() -> None:
        root.destroy()

    tk.Button(btns, text="Clean this folder", command=on_run).pack(side="left")
    tk.Button(btns, text="Cancel", command=on_cancel).pack(side="right")

    root.mainloop()
    return 0


def run_cli(input_dir: Path, preset: Settings, open_output: bool) -> int:
    """Core execution used by both GUI and CLI."""
    runtime_root = get_runtime_root()
    app_home = get_default_target_dir()

    # Load config (first match in input folder, else next to executable/app)
    conf_path: Optional[Path] = None
    for ni in CONF_FILENAMES:
        p1 = input_dir / ni
        p2 = app_home / ni
        if p1.exists():
            conf_path = p1
            break
        if p2.exists():
            conf_path = p2
            break

    conf = load_conf(conf_path) if conf_path else {}
    settings = merge_settings(preset, conf)

    output_dir = (input_dir / settings.output_folder).resolve()
    safe_makedirs(output_dir, settings.dry_run)

    exiftool = which_tool("exiftool", runtime_root)
    ffmpeg = which_tool("ffmpeg", runtime_root)

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
        eprint(f"[{APP_NAME}] No media files found in {input_dir}")
        return 0

    image_counter = 0
    video_counter = 0

    for ni, src in enumerate(files, start=1):
        kind = classify_media(src)
        if kind not in {"image", "video"}:
            continue

        ts = get_best_timestamp(src) if settings.keep_timestamps else None
        if kind == "image":
            image_counter += 1
            counter = image_counter
        else:
            video_counter += 1
            counter = video_counter

        new_name = make_output_name(
            naming=settings.naming,
            kind=kind,
            ext=src.suffix.lower(),
            counter=counter,
            ts=ts,
        )

        dest = unique_path(output_dir / new_name)
        if settings.dry_run:
            print(f"[DRY] {src.name} -> {dest.name}")
            continue

        copy_file(src, dest, settings.dry_run)

        # Strip metadata in-place on the copied file
        if kind == "image" and exiftool is not None:
            strip_image_metadata_exiftool(exiftool, dest, settings.dry_run)
        elif kind == "video" and ffmpeg is not None:
            strip_video_metadata_ffmpeg(ffmpeg, dest, settings.dry_run)

        preserve_timestamps(src, dest, settings.keep_timestamps, settings.dry_run)
        mac_clear_xattrs(dest, settings.dry_run)

    print(f"[{APP_NAME}] Done. Output: {output_dir}")
    if open_output and not settings.dry_run:
        maybe_open_folder(output_dir)
    return 0

    counters = {"image": 0, "video": 0}
    used_names: set[str] = set()

    for ni, p in enumerate(files, start=1):
        kind = classify_media(p)
        if kind not in {"image", "video"}:
            continue

        ts = get_best_timestamp(p) if settings.keep_timestamps else None
        new_name = make_output_name(
            naming=settings.naming,
            kind=kind,
            ext=p.suffix.lower(),
            index=(counters[kind] + 1),
            ts=ts,
            used_names=used_names,
        )
        counters[kind] += 1

        dest = output_dir / new_name
        if settings.dry_run:
            print(f"[DRY] {p.name} -> {dest.name}")
            continue

        shutil.copy2(p, dest)

        # Strip metadata
        if kind == "image" and exiftool is not None:
            strip_image_metadata(exiftool, dest)
        elif kind == "video" and ffmpeg is not None:
            strip_video_metadata(ffmpeg, dest)

        # Keep timestamps similar to original if requested
        if settings.keep_timestamps and ts is not None:
            try:
                os.utime(dest, (ts.timestamp(), ts.timestamp()))
            except Exception:
                pass

    print(f"[{APP_NAME}] Done. Output: {output_dir}")
    if open_output and not settings.dry_run:
        maybe_open_folder(output_dir)
    return 0


def main() -> int:
    default_input = get_default_target_dir()

    # Double-click friendly GUI (no args)
    if should_launch_gui():
        return run_gui(default_input)

    parser = argparse.ArgumentParser(
        prog="NiClean",
        description="NiClean: strip metadata + rename media into iPhone/Android-style filenames (copies into a subfolder).",
    )
    parser.add_argument("--input", "-in", default=None, help="Input folder (default: folder containing the app/exe).")
    parser.add_argument("--output", "-out", default=None, help=f"Output subfolder name (default: {DEFAULT_OUTPUT_FOLDER}).")
    parser.add_argument("--naming", choices=["iphone", "android"], default=None, help="Filename convention.")
    parser.add_argument("--include-subfolders", action="store_true", help="Process subfolders too.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen, without writing files.")
    parser.add_argument("--no-open", action="store_true", help="Don't open output folder when done.")
    parser.add_argument("--strict-tools", action="store_true", help="Fail if exiftool/ffmpeg are missing.")
    parser.add_argument("--gui", action="store_true", help="Launch the simple GUI instead of running immediately.")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve() if args.input else default_input.resolve()
    if args.gui:
        return run_gui(input_dir)

    if not input_dir.exists() or not input_dir.is_dir():
        eprint(f"[{APP_NAME}] Error: Input folder not found: {input_dir}")
        return 2

    s = Settings()
    if args.output is not None:
        s.output_folder = args.output
    if args.naming is not None:
        s.naming = args.naming
    if args.include_subfolders:
        s.include_subfolders = True
    if args.dry_run:
        s.dry_run = True
    if args.strict_tools:
        s.strict_tools = True

    return run_cli(input_dir, s, open_output=(not args.no_open))


if __name__ == "__main__":
    raise SystemExit(main())
