# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Gesture Keys.

Build command (run from project root):
    pyinstaller gesture_keys.spec
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect mediapipe data files (models, etc.)
mediapipe_datas = collect_data_files("mediapipe")

# Project paths
src_dir = os.path.join(os.getcwd(), "src")

# Data files to bundle: web UI templates and static assets
datas = [
    (os.path.join(src_dir, "gesture_keys", "web_ui", "templates"), os.path.join("gesture_keys", "web_ui", "templates")),
    (os.path.join(src_dir, "gesture_keys", "web_ui", "static"), os.path.join("gesture_keys", "web_ui", "static")),
] + mediapipe_datas

# Hidden imports that PyInstaller may miss
hiddenimports = (
    collect_submodules("mediapipe")
    + collect_submodules("pynput")
    + [
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "flask",
        "jinja2",
        "cv2",
    ]
)

a = Analysis(
    [os.path.join(src_dir, "gesture_keys", "__main__.py")],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GestureKeys",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - runs with system tray + browser
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set to "icon.ico" if you add a custom icon
)
