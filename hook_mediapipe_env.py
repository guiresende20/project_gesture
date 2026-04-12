"""
Runtime hook: configure environment before any imports run inside the frozen exe.
MediaPipe requires the pure-Python protobuf implementation when bundled with PyInstaller.
"""
import os
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
