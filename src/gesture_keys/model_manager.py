from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path

from gesture_keys.constants import MODEL_URL

_DOWNLOAD_TIMEOUT = 60  # seconds


def ensure_model(models_dir: Path) -> Path:
    model_path = models_dir / "gesture_recognizer.task"
    if model_path.exists():
        return model_path

    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading gesture recognizer model to {model_path}...")

    tmp_path = model_path.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp_path)
        tmp_path.rename(model_path)
        print("Model downloaded successfully.")
    except (urllib.error.URLError, OSError) as e:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Failed to download gesture model from {MODEL_URL}: {e}\n"
            "Check your internet connection and try again."
        ) from e

    return model_path
