from pathlib import Path
import sys


def _is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _get_bundle_dir() -> Path:
    """Directory where bundled data files live (PyInstaller _MEIPASS)."""
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent.parent


def _get_app_dir() -> Path:
    """Writable directory next to the .exe (or project root in dev)."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


BUNDLE_DIR = _get_bundle_dir()
APP_DIR = _get_app_dir()

GESTURE_NAMES: list[str] = [
    "Closed_Fist",
    "Open_Palm",
    "Pointing_Up",
    "Thumb_Down",
    "Thumb_Up",
    "Victory",
    "ILoveYou",
]

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/latest/"
    "gesture_recognizer.task"
)

# Model and config live next to the .exe (writable), not inside the bundle
MODELS_DIR = APP_DIR / "models"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_COOLDOWN_MS = 800
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

WEB_HOST = "127.0.0.1"
WEB_PORT = 5123
