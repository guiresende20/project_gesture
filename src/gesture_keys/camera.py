from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2

log = logging.getLogger("gesture_keys")

MAX_CAMERA_PROBE_INDEX = 4


@dataclass
class CameraInfo:
    index: int
    available: bool
    current: bool = False


def list_cameras(current_index: int, max_index: int = MAX_CAMERA_PROBE_INDEX) -> list[CameraInfo]:
    """Probe camera indices 0..max_index and return availability info.

    The current camera index is reported as available without re-probing — the
    engine already holds it open and OpenCV cannot reliably open the same
    device twice from one process. Other indices are opened briefly with
    DirectShow (Windows) or the default backend and released."""
    results: list[CameraInfo] = []
    for i in range(max_index + 1):
        if i == current_index:
            results.append(CameraInfo(index=i, available=True, current=True))
            continue
        results.append(CameraInfo(index=i, available=_probe(i), current=False))
    return results


def _probe(index: int) -> bool:
    cap = None
    try:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return True
        cap.release()
        cap = cv2.VideoCapture(index)
        return cap.isOpened()
    except Exception:
        log.debug("camera probe failed for index %d", index, exc_info=True)
        return False
    finally:
        if cap is not None:
            cap.release()
