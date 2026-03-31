from __future__ import annotations

import urllib.request
from pathlib import Path

from gesture_keys.constants import MODEL_URL


def ensure_model(models_dir: Path) -> Path:
    model_path = models_dir / "gesture_recognizer.task"
    if model_path.exists():
        return model_path

    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading gesture recognizer model to {model_path}...")
    urllib.request.urlretrieve(MODEL_URL, model_path)
    print("Model downloaded successfully.")
    return model_path
