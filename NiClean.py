#!/usr/bin/env python3
"""
NiClean v0.4.1
License: Apache-2.0 (see LICENSE)
Third party disclosures: (see NOTICE)
Ni! 🌿
"""

from __future__ import annotations

import platform
import sys
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
from tkinter import messagebox, filedialog

# --- Constants ---
APP_NAME = "NiClean"
APP_VERSION = "0.4.1"
DEFAULT_OUTPUT_FOLDER = "NiClean_cleaned"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


@dataclass
class Settings:
    naming: str = "iPhone"              # iPhone | Android | Original
    output_mode: str = "subfolder"      # subfolder | replace
    output_folder: str = DEFAULT_OUTPUT_FOLDER
    include_subfolders: bool = False    # scan recursively when True


def subprocess_kwargs_no_window() -> dict:
    if platform.system() == "Windows":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": si,
        }
    return {}


def resource_path(relative: str) -> str:
    """Absolute path to resource; works in dev and PyInstaller (onefile/onedir)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return str(base / relative)


def default_input_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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
        subprocess.run(cmd, check=True, capture_output=True, **subprocess_kwargs_no_window())
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


def clean_metadata(file_path: Path, exiftool_path: Optional[str]) -> bool:
    """Strip metadata in-place using ExifTool. Returns True on success."""
    if not exiftool_path:
        return False

    cmd = [exiftool_path, "-all=", "-overwrite_original", str(file_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, **subprocess_kwargs_no_window())
        return True
    except subprocess.CalledProcessError:
        return False


def make_output_name(path: Path, settings: Settings, counter: int) -> str:
    """
    Create a new filename.
    Note: For images, we preserve the original extension to avoid "renaming PNG to .JPG"
    without actually converting. Videos may change extension (and trigger ffmpeg).
    """
    if settings.naming == "Original":
        return path.name

    ext = path.suffix  # preserve original case for "Original"; for generated names we format below
    is_image = path.suffix.lower() in IMAGE_EXTS
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if settings.naming == "Android":
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

        self.input_dir = initial_dir

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("550x650")
        self.minsize(550, 650)

        # Set window/taskbar icon (runtime)
        try:
            if platform.system() == "Windows":
                self.iconbitmap(resource_path("assets/niclean.ico"))
            else:
                # macOS/Linux prefer PNG via iconphoto
                import tkinter as tk
                img = tk.PhotoImage(file=resource_path("assets/niclean.png"))
                self.iconphoto(True, img)
                self._icon_img = img  # keep a reference so it doesn't get GC'd
        except Exception:
            pass

        # Input directory picker
        self.dir_frame = ctk.CTkFrame(self)
        self.dir_frame.pack(padx=40, pady=(10, 10), fill="x")

        ctk.CTkLabel(self.dir_frame, text="folder to clean:").pack(anchor="w", padx=12, pady=(10, 0))

        self.dir_label = ctk.CTkLabel(self.dir_frame, text=str(self.input_dir), wraplength=430, justify="left")
        self.dir_label.pack(anchor="w", padx=12, pady=(4, 10))

        self.choose_dir_btn = ctk.CTkButton(
            self.dir_frame,
            text="choose folder",
            command=self.choose_input_dir,
            width=140
        )
        self.choose_dir_btn.pack(anchor="w", padx=12, pady=(0, 12))

        # Top-right GitHub button
        self.github_btn = ctk.CTkButton(
            self,
            text="GitHub 🌿",
            width=90,
            fg_color="transparent",
            border_width=1,
            text_color=("black", "white"),        # light, dark
            border_color=("black", "white"),      # optional, but looks crisp
            command=lambda: webbrowser.open("https://github.com/TheDevWhoSaysNi/NiClean"),
        )
        self.github_btn.pack(pady=10, padx=20, anchor="ne")

        self.label = ctk.CTkLabel(self, text="NiClean Metadata Cleaner", font=("Arial", 24, "bold"))
        self.label.pack(pady=10)

        # Status + progress
        self.status_label = ctk.CTkLabel(self, text="Ready To Clean Metadata", font=("Arial", 14))
        self.status_label.pack(pady=(20, 0))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # Settings container
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=20, padx=40, fill="both", expand=True)

        # Naming convention
        ctk.CTkLabel(self.settings_frame, text="Naming Convention:").grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.naming_var = ctk.StringVar(value="iPhone")
        self.name_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=["iPhone", "Android", "Original"],
            variable=self.naming_var,
        )
        self.name_menu.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

        # Include subfolders (restored)
        self.subfolders_var = ctk.BooleanVar(value=False)
        self.subfolders_switch = ctk.CTkSwitch(
            self.settings_frame,
            text="Include Subfolders",
            variable=self.subfolders_var,
        )
        self.subfolders_switch.grid(row=1, column=0, columnspan=2, pady=(10, 10), sticky="w", padx=20)

        # Output mode (replace)
        self.replace_var = ctk.BooleanVar(value=False)
        self.replace_switch = ctk.CTkSwitch(
            self.settings_frame,
            text="Replace Existing Files",
            variable=self.replace_var,
        )
        self.replace_switch.grid(row=2, column=0, columnspan=2, pady=(10, 20), sticky="w", padx=20)

        # Expand right column nicely
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Run button
        self.run_btn = ctk.CTkButton(
            self,
            text="Run! Ni!",
            command=self.start_processing,
            height=50,
            width=220,
            font=("Arial", 18, "bold"),
        )
        self.run_btn.pack(pady=(0, 40))

    def choose_input_dir(self) -> None:
        folder = filedialog.askdirectory(initialdir=str(self.input_dir))
        if folder:
            self.input_dir = Path(folder)
            self.dir_label.configure(text=str(self.input_dir))
            self.status_label.configure(text="Ready to clean metadata")
            self.progress_bar.set(0)
    
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
        
        exiftool_path = get_tool_path("exiftool")
        ffmpeg_path = get_tool_path("ffmpeg")  # optional if you want it cached too
        has_exiftool = bool(exiftool_path)

        # Tool availability warning (non-fatal)
        if not has_exiftool:
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

                if has_exiftool:
                    if clean_metadata(dest, exiftool_path):
                        scrubbed += 1
                    else:
                        failed += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                print(f"Ni! Error processing {src}: {e}")

        # 4) Final state
        self._set_progress(1.0)
        self._set_status("Complete!")
        self._enable_run()

        self.after(
            0,
            lambda: messagebox.showinfo(
                "NiClean Complete",
                f"Processed: {total}\nScrubbed: {scrubbed}\nIssues: {failed}\n\nDone. I mean, Ni!",
            ),
        )


if __name__ == "__main__":
    input_p = default_input_dir()
    app = NiCleanApp(input_p)
    app.mainloop()
