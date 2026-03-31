from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

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

MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULT_COOLDOWN_MS = 800
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

WEB_HOST = "127.0.0.1"
WEB_PORT = 5123
