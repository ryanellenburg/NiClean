#!/usr/bin/env python3
"""
NiClean v0.4.1
License: Apache-2.0 (see LICENSE)
Third party disclosures: (see NOTICE)
Ni! 🌿
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import messagebox

# --- Constants ---
APP_NAME = "NiClean"
APP_VERSION = "0.4.1"
DEFAULT_OUTPUT_FOLDER = "NiClean_cleaned"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


@dataclass
class Settings:
    naming: str = "iphone"              # iphone | android | original
    output_mode: str = "subfolder"      # subfolder | replace
    output_folder: str = DEFAULT_OUTPUT_FOLDER
    include_subfolders: bool = False    # scan recursively when True


def get_tool_path(tool_name: str) -> Optional[str]:
    """Find ffmpeg/exiftool in bundled tools (Windows) or system PATH."""
    if platform.system() == "Windows":
        tool_exe = f"{tool_name}.exe"
        local_tool = Path(__file__).parent / "tools" / tool_exe
        if local_tool.exists():
            return str(local_tool)
    return shutil.which(tool_name)


def convert_with_ffmpeg(src: Path, dest: Path) -> bool:
    """Convert src -> dest using ffmpeg. Returns True if conversion succeeded."""
    ffmpeg = get_tool_path("ffmpeg")
    if not ffmpeg:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(src),
        "-map_metadata", "-1",  # drop container metadata (still scrub with exiftool after)
        str(dest),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print("FFmpeg failed:", e.stderr.decode(errors="ignore"))
        return False


def create_output_file(src: Path, dest: Path) -> None:
    """
    Create dest from src.
    - If extension changes AND src is video, attempt ffmpeg conversion.
    - Otherwise, do a normal copy (preserves file content exactly).
    """
    wants_conversion = src.suffix.lower() != dest.suffix.lower()

    if wants_conversion and src.suffix.lower() in VIDEO_EXTS:
        ok = convert_with_ffmpeg(src, dest)
        if ok:
            return

    # Default: plain copy (no format conversion)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def clean_metadata(file_path: Path) -> bool:
    """Strip metadata in-place using ExifTool. Returns True on success."""
    tool = get_tool_path("exiftool")
    if not tool:
        return False

    cmd = [tool, "-all=", "-overwrite_original", str(file_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def make_output_name(path: Path, settings: Settings, counter: int) -> str:
    """
    Create a new filename.
    Note: For images, we preserve the original extension to avoid "renaming PNG to .JPG"
    without actually converting. Videos may change extension (and trigger ffmpeg).
    """
    if settings.naming == "original":
        return path.name

    ext = path.suffix  # preserve original case for "original"; for generated names we format below
    is_image = path.suffix.lower() in IMAGE_EXTS
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if settings.naming == "android":
        # Android-style: IMG_YYYYMMDD_HHMMSS_0001.ext (keep ext)
        return f"IMG_{ts}_{counter:04d}{ext.lower()}"

    # iPhone-style: IMG_0001.EXT
    if is_image:
        # preserve image ext to avoid incorrect renames (png stays png, etc.)
        return f"IMG_{counter:04d}{ext.upper()}"
    else:
        # For video, default to MOV naming (can trigger conversion)
        return f"IMG_{counter:04d}.MOV"


class NiCleanApp(ctk.CTk):
    def __init__(self, initial_dir: Path):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("550x650")
        self.input_dir = initial_dir

        # Top-right GitHub button
        self.gh_btn = ctk.CTkButton(
            self,
            text="GitHub 🌿",
            width=90,
            fg_color="transparent",
            border_width=1,
            command=lambda: webbrowser.open("https://github.com/TheDevWhoSaysNi/NiClean"),
        )
        self.gh_btn.pack(pady=10, padx=20, anchor="ne")

        self.label = ctk.CTkLabel(self, text="NiClean Media Scrubber", font=("Arial", 24, "bold"))
        self.label.pack(pady=10)

        # Status + progress
        self.status_label = ctk.CTkLabel(self, text="Ready to clean metadata", font=("Arial", 14))
        self.status_label.pack(pady=(20, 0))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # Settings container
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=20, padx=40, fill="both", expand=True)

        # Naming convention
        ctk.CTkLabel(self.settings_frame, text="Naming Convention:").grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.naming_var = ctk.StringVar(value="iphone")
        self.name_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=["iphone", "android", "original"],
            variable=self.naming_var,
        )
        self.name_menu.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

        # Include subfolders (restored)
        self.subfolders_var = ctk.BooleanVar(value=False)
        self.subfolders_switch = ctk.CTkSwitch(
            self.settings_frame,
            text="Include subfolders",
            variable=self.subfolders_var,
        )
        self.subfolders_switch.grid(row=1, column=0, columnspan=2, pady=(10, 10), sticky="w", padx=20)

        # Output mode (replace)
        self.replace_var = ctk.BooleanVar(value=False)
        self.replace_switch = ctk.CTkSwitch(
            self.settings_frame,
            text="Replace existing files",
            variable=self.replace_var,
        )
        self.replace_switch.grid(row=2, column=0, columnspan=2, pady=(10, 20), sticky="w", padx=20)

        # Expand right column nicely
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Run button
        self.run_btn = ctk.CTkButton(
            self,
            text="Run Ni!",
            command=self.start_processing,
            height=50,
            width=220,
            font=("Arial", 18, "bold"),
        )
        self.run_btn.pack(pady=(0, 40))

    def start_processing(self) -> None:
        self.run_btn.configure(state="disabled")
        self.progress_bar.set(0)

        settings = Settings(
            naming=self.naming_var.get(),
            output_mode="replace" if self.replace_var.get() else "subfolder",
            include_subfolders=bool(self.subfolders_var.get()),
        )

        threading.Thread(target=self.process_logic, args=(settings,), daemon=True).start()

    def _set_status(self, text: str) -> None:
        # NOTE: UI updates from a thread can be flaky on some systems.
        # Using `after()` keeps it safe.
        self.after(0, lambda: self.status_label.configure(text=text))

    def _set_progress(self, value: float) -> None:
        self.after(0, lambda: self.progress_bar.set(value))

    def _enable_run(self) -> None:
        self.after(0, lambda: self.run_btn.configure(state="normal"))

    def process_logic(self, settings: Settings) -> None:
        # 1) Gather media files
        def is_media(p: Path) -> bool:
            return p.is_file() and (p.suffix.lower() in IMAGE_EXTS or p.suffix.lower() in VIDEO_EXTS)

        if settings.include_subfolders:
            files = [p for p in self.input_dir.rglob("*") if is_media(p)]
        else:
            files = [p for p in self.input_dir.iterdir() if is_media(p)]

        total = len(files)
        if total == 0:
            self._set_status("No media found in this folder. The Knights Who Say Ni demand a sacrifice!")
            self._enable_run()
            return

        # 2) Setup output root
        if settings.output_mode == "subfolder":
            out_root = self.input_dir / settings.output_folder
            out_root.mkdir(exist_ok=True)
        else:
            out_root = self.input_dir  # replace mode

        # Tool availability warning (non-fatal)
        if not get_tool_path("exiftool"):
            self._set_status("Warning: ExifTool not found. Files will be copied/converted but not scrubbed.")
        else:
            self._set_status("Starting...")

        # 3) Processing loop
        scrubbed = 0
        failed = 0

        for ni, src in enumerate(files, start=1):
            self._set_progress(ni / total)
            self._set_status(f"Cleaning {ni} of {total}: {src.name} Ni. Ping. Nee-womm.")

            new_name = make_output_name(src, settings, ni)

            # Determine destination path
            if settings.output_mode == "replace":
                dest = src  # overwrite in place
            else:
                if settings.include_subfolders:
                    rel_parent = src.parent.relative_to(self.input_dir)
                    dest_dir = out_root / rel_parent
                else:
                    dest_dir = out_root
                dest = dest_dir / new_name

            try:
                if settings.output_mode == "replace":
                    # Create into a temp file first, then replace original
                    with tempfile.TemporaryDirectory() as td:
                        tmp_out = Path(td) / new_name
                        create_output_file(src, tmp_out)
                        shutil.move(str(tmp_out), str(dest))
                else:
                    create_output_file(src, dest)

                if get_tool_path("exiftool"):
                    if clean_metadata(dest):
                        scrubbed += 1
                    else:
                        failed += 1
                else:
                    # If exiftool missing, we count it as "processed" but not scrubbed.
                    failed += 1

            except Exception as e:
                failed += 1
                print(f"Ni! Error processing {src}: {e}")

        # 4) Final state
        self._set_progress(1.0)
        self._set_status("Done! I mean... Ni! 🌿")
        self._enable_run()

        self.after(
            0,
            lambda: messagebox.showinfo(
                "NiClean Complete",
                f"Processed: {total}\nScrubbed: {scrubbed}\nIssues: {failed}\n\nNi!",
            ),
        )


if __name__ == "__main__":
    input_p = Path.cwd()
    app = NiCleanApp(input_p)
    app.mainloop()
