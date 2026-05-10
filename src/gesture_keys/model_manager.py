from __future__ import annotations

import shutil
import socket
import urllib.error
import urllib.request
from pathlib import Path

from gesture_keys.constants import MODEL_URL

_DOWNLOAD_TIMEOUT = 60  # seconds, applied per-read on the underlying socket


def ensure_model(models_dir: Path) -> Path:
    model_path = models_dir / "gesture_recognizer.task"
    if model_path.exists():
        return model_path

    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading gesture recognizer model to {model_path}...")

    tmp_path = model_path.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=_DOWNLOAD_TIMEOUT) as resp, \
                open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        tmp_path.rename(model_path)
        print("Model downloaded successfully.")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Failed to download gesture model from {MODEL_URL}: {e}\n"
            "Check your internet connection and try again."
        ) from e

    return model_path
