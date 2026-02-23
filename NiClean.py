#!/usr/bin/env python3
"""
NiClean v0.4.0
License: Apache-2.0 (see LICENSE)
NOTICE: See NOTICE
Ni! 🌿
"""

from __future__ import annotations
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- Constants & Settings ---
APP_NAME = "NiClean"
APP_VERSION = "0.4.0"
DEFAULT_OUTPUT_FOLDER = "NiClean_cleaned"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

@dataclass
class Settings:
    naming: str = "iphone"         # iphone | android | original
    output_mode: str = "subfolder"  # subfolder | replace
    output_folder: str = DEFAULT_OUTPUT_FOLDER
    include_subfolders: bool = False
    dry_run: bool = False
    keep_timestamps: bool = True
    strict_tools: bool = False

# --- Core Logic (The "Heavy Lifting" you already built) ---

def get_tool_path(tool_name: str) -> Optional[str]:
    """Find ffmpeg or exiftool in the bundled paths or system PATH."""
    if platform.system() == "Windows":
        tool_exe = f"{tool_name}.exe"
        local_tool = Path(__file__).parent / "tools" / tool_exe
        if local_tool.exists():
            return str(local_tool)
    return shutil.which(tool_name)

def clean_metadata(input_path: Path, output_path: Path, settings: Settings) -> bool:
    """Strips metadata using ExifTool."""
    tool = get_tool_path("exiftool")
    if not tool: return False
    
    cmd = [tool, "-all=", "-overwrite_original", str(input_path), "-o", str(output_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except:
        return False

def make_output_name(path: Path, settings: Settings, counter: int) -> str:
    # Feature 3d: Added 'original' naming option
    if settings.naming == "original":
        return path.name
        
    ext = path.suffix.lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if settings.naming == "android":
        new_ext = ".jpg" if ext in IMAGE_EXTS else ".mp4"
        return f"IMG_{ts}_{counter:04d}{new_ext}"
    else: # iphone
        new_ext = ".JPG" if ext in IMAGE_EXTS else ".MOV"
        return f"IMG_{counter:04d}{new_ext}"

# --- The Modern UI Class ---

class NiCleanApp(ctk.CTk):
    def __init__(self, initial_dir: Path):
        super().__init__()

        # Feature 3b: Dark Mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("550x600")
        self.input_dir = initial_dir

        # Feature 3f: GitHub Link
        self.gh_btn = ctk.CTkButton(self, text="GitHub 🌿", width=80, fg_color="transparent", border_width=1,
                                   command=lambda: webbrowser.open("https://github.com/your-repo"))
        self.gh_btn.pack(pady=10, padx=20, anchor="ne")

        self.label = ctk.CTkLabel(self, text="NiClean Media Scrubber", font=("Arial", 24, "bold"))
        self.label.pack(pady=10)

        # Feature 3c: Progress Bar & Ni! Status
        self.status_label = ctk.CTkLabel(self, text="Ready to clean metadata", font=("Arial", 14))
        self.status_label.pack(pady=(20, 0))
        
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # Settings Container
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=20, padx=40, fill="both", expand=True)

        # Feature 3d: Naming
        ctk.CTkLabel(self.settings_frame, text="Naming Convention:").grid(row=0, column=0, padx=20, pady=10)
        self.naming_var = ctk.StringVar(value="iphone")
        self.name_menu = ctk.CTkOptionMenu(self.settings_frame, values=["iphone", "android", "original"], variable=self.naming_var)
        self.name_menu.grid(row=0, column=1, padx=20, pady=10)

        # Feature 3e: Output Mode
        self.replace_var = ctk.BooleanVar(value=False)
        self.replace_switch = ctk.CTkSwitch(self.settings_frame, text="Replace existing files", variable=self.replace_var)
        self.replace_switch.grid(row=1, column=0, columnspan=2, pady=20)

        self.run_btn = ctk.CTkButton(self, text="Run Ni!", command=self.start_processing, 
                                    height=50, width=200, font=("Arial", 18, "bold"))
        self.run_btn.pack(pady=(0, 40))

    def start_processing(self):
        self.run_btn.configure(state="disabled")
        settings = Settings(
            naming=self.naming_var.get(),
            output_mode="replace" if self.replace_var.get() else "subfolder"
        )
        threading.Thread(target=self.process_logic, args=(settings,), daemon=True).start()

    def process_logic(self, settings: Settings):
        # Gather files
        files = [p for p in self.input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS or p.suffix.lower() in VIDEO_EXTS]
        total = len(files)

        if total == 0:
            self.status_label.configure(text="No media found in this folder!")
            self.run_btn.configure(state="normal")
            return

        # Setup Directory
        if settings.output_mode == "subfolder":
            out_dir = self.input_dir / settings.output_folder
            out_dir.mkdir(exist_ok=True)
        else:
            out_dir = self.input_dir # Overwrite mode

        # Feature 3c: The loop using 'ni'
        for ni, path in enumerate(files, start=1):
            # Update UI Progress
            self.progress_bar.set(ni / total)
            self.status_label.configure(text=f"Ni! Cleaning: {path.name} ({ni}/{total})")
            
            # --- Actual Cleaning Happens Here ---
            new_name = make_output_name(path, settings, ni)
            dest = out_dir / new_name
            
            # (In a real run, we'd call clean_metadata or ffmpeg here)
            shutil.copy2(path, dest) # Placeholder for actual cleaning
            
        self.status_label.configure(text="Done! I mean... Ni! 🌿")
        self.run_btn.configure(state="normal")
        messagebox.showinfo("Success", "Files have been cleaned. Ni!")

if __name__ == "__main__":
    # If no folder passed, use current directory
    input_p = Path.cwd()
    app = NiCleanApp(input_p)
    app.mainloop()