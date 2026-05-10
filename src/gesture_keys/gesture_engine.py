from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import logging
import cv2
import numpy as np

from gesture_keys.constants import (
    CAMERA_HEIGHT,
    CAMERA_RETRY_SLEEP_S,
    CAMERA_WIDTH,
    MAX_CAMERA_READ_FAILURES,
    PAUSED_SLEEP_S,
    TARGET_FPS,
)

log = logging.getLogger("gesture_keys")


# MediaPipe hand connections (21 landmarks, pairs of indices)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # index
    (0, 9), (9, 10), (10, 11), (11, 12),   # middle
    (0, 13), (13, 14), (14, 15), (15, 16), # ring
    (0, 17), (17, 18), (18, 19), (19, 20), # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]


class GestureEngine(threading.Thread):
    def __init__(
        self,
        model_path: Path,
        confidence_threshold: float = 0.7,
        on_gesture: Callable[[str, float], None] | None = None,
        on_frame: Callable[[np.ndarray], None] | None = None,
        camera_index: int = 0,
    ) -> None:
        super().__init__(daemon=True)
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._on_gesture = on_gesture
        self._on_frame = on_frame
        self._camera_index = camera_index

        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()

        self._current_gesture: str | None = None
        self._current_confidence: float = 0.0
        self._latest_frame: np.ndarray | None = None

    @property
    def current_gesture(self) -> str | None:
        with self._lock:
            return self._current_gesture

    @property
    def current_confidence(self) -> float:
        with self._lock:
            return self._current_confidence

    @property
    def latest_frame(self) -> np.ndarray | None:
        # Reference read is GIL-atomic. The engine never mutates a frame after
        # publishing it (each loop iteration creates a fresh array), so callers
        # can safely read this reference without a lock or copy.
        return self._latest_frame

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    @property
    def confidence_threshold(self) -> float:
        with self._lock:
            return self._confidence_threshold

    @confidence_threshold.setter
    def confidence_threshold(self, value: float) -> None:
        with self._lock:
            self._confidence_threshold = value

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except Exception as e:
            log.error("[GestureEngine] Failed to import mediapipe: %s", e, exc_info=True)
            return

        self._mp = mp

        try:
            base_options = mp_python.BaseOptions(
                model_asset_path=str(self._model_path)
            )
            options = vision.GestureRecognizerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception as e:
            log.error("[GestureEngine] Failed to configure mediapipe options: %s", e, exc_info=True)
            return

        cap = None
        recognizer = None
        try:
            recognizer = vision.GestureRecognizer.create_from_options(options)
            # Try DirectShow first (more reliable in frozen .exe on Windows),
            # fall back to default backend if it fails.
            cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                log.warning("CAP_DSHOW failed for camera %d, trying default backend.", self._camera_index)
                cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                log.error("Could not open camera %d. Check if the camera is connected and not in use.", self._camera_index)
                return

            # Reduce camera resolution for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

            self._recognition_loop(cap, recognizer)
        except Exception as e:
            log.error("[GestureEngine] Fatal error: %s", e)
        finally:
            if cap is not None:
                cap.release()
            if recognizer is not None:
                recognizer.close()

    def _recognition_loop(self, cap, recognizer) -> None:
        frame_interval = 1.0 / TARGET_FPS
        read_failures = 0

        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            frame = self._read_next_frame(cap)
            if frame is None:
                read_failures += 1
                if read_failures >= MAX_CAMERA_READ_FAILURES:
                    log.error(
                        "Camera read failed %d times in a row; stopping engine "
                        "(camera disconnected or in use by another process).",
                        read_failures,
                    )
                    return
                time.sleep(CAMERA_RETRY_SLEEP_S)
                continue
            read_failures = 0

            if self._paused.is_set():
                self._publish_paused(frame)
                time.sleep(PAUSED_SLEEP_S)
                continue

            gesture_name, gesture_score = self._recognize(recognizer, frame)
            self._publish(frame, gesture_name, gesture_score)

            # FPS limiter
            elapsed = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _read_next_frame(self, cap) -> np.ndarray | None:
        ret, frame = cap.read()
        if not ret:
            return None
        return cv2.flip(frame, 1)

    def _recognize(
        self, recognizer, frame: np.ndarray
    ) -> tuple[str | None, float]:
        """Run MediaPipe on `frame`, mutate it in-place to draw landmarks, and
        return (gesture_name, score) — name is None when below threshold."""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            result = recognizer.recognize(mp_image)
        except Exception as e:
            log.error("[GestureEngine] Recognition error: %s", e)
            return None, 0.0

        if result.hand_landmarks:
            self._draw_landmarks_cv2(frame, result.hand_landmarks[0])

        if result.gestures and result.gestures[0]:
            top = result.gestures[0][0]
            if top.category_name != "None" and top.score >= self.confidence_threshold:
                return top.category_name, top.score

        return None, 0.0

    def _publish(
        self,
        frame: np.ndarray,
        gesture_name: str | None,
        gesture_score: float,
    ) -> None:
        # Small lock guards only the cheap scalar fields. Frame is published
        # via atomic reference assignment so MJPEG/UI readers don't block.
        with self._lock:
            self._current_gesture = gesture_name
            self._current_confidence = gesture_score
        self._latest_frame = frame

        if self._on_frame:
            self._on_frame(frame)
        if gesture_name and self._on_gesture:
            self._on_gesture(gesture_name, gesture_score)

    def _publish_paused(self, frame: np.ndarray) -> None:
        self._latest_frame = frame
        if self._on_frame:
            self._on_frame(frame)

    def _draw_landmarks_cv2(self, frame: np.ndarray, hand_landmarks: list) -> None:
        """Draw hand landmarks using pure OpenCV (no protobuf conversion)."""
        h, w = frame.shape[:2]

        points = []
        for lm in hand_landmarks:
            px = int(lm.x * w)
            py = int(lm.y * h)
            points.append((px, py))

        for start_idx, end_idx in _HAND_CONNECTIONS:
            if start_idx < len(points) and end_idx < len(points):
                cv2.line(frame, points[start_idx], points[end_idx],
                         (255, 255, 255), 1, cv2.LINE_AA)

        for px, py in points:
            cv2.circle(frame, (px, py), 3, (0, 255, 0), -1, cv2.LINE_AA)
