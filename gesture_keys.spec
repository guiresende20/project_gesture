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

# Find OpenCV videoio DLLs needed for camera capture
import cv2 as _cv2
_cv2_dir = Path(_cv2.__file__).parent
_cv2_dlls = [(str(p), ".") for p in _cv2_dir.glob("opencv_videoio_*.dll")]

# Include python311.dll explicitly (required for one-directory builds)
import sysconfig as _sc
_py_dir = Path(_sc.get_config_var("BINDIR") or sys.executable).parent
_py_dll = _py_dir / "python311.dll"
if _py_dll.exists():
    _cv2_dlls.append((str(_py_dll), "."))

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
    + collect_submodules("google.protobuf")
    + [
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "flask",
        "jinja2",
        "cv2",
        "absl",
        "absl.logging",
        "absl.flags",
        "google",
        "google.protobuf",
        "google.protobuf.descriptor",
        "google.protobuf.descriptor_pool",
        "google.protobuf.reflection",
        "google.protobuf.symbol_database",
    ]
)

a = Analysis(
    [os.path.join(src_dir, "gesture_keys", "__main__.py")],
    pathex=[src_dir],
    binaries=_cv2_dlls,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hook_mediapipe_env.py"],
    excludes=["tkinter", "scipy", "pandas", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name="GestureKeys",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No console window - runs with system tray + browser
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set to "icon.ico" if you add a custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="GestureKeys",
)
