from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np


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
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

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
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp

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

        cap = None
        recognizer = None
        try:
            recognizer = vision.GestureRecognizer.create_from_options(options)
            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                print(f"Error: Could not open camera {self._camera_index}")
                return

            # Reduce camera resolution for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self._recognition_loop(cap, recognizer)
        except Exception as e:
            print(f"[GestureEngine] Fatal error: {e}")
        finally:
            if cap is not None:
                cap.release()
            if recognizer is not None:
                recognizer.close()

    def _recognition_loop(self, cap, recognizer) -> None:
        mp = self._mp
        target_fps = 15
        frame_interval = 1.0 / target_fps

        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)

            if self._paused.is_set():
                with self._lock:
                    self._latest_frame = frame
                if self._on_frame:
                    self._on_frame(frame)
                time.sleep(0.03)
                continue

            # Recognize gesture
            gesture_name = None
            gesture_score = 0.0

            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = recognizer.recognize(mp_image)

                if result.hand_landmarks:
                    self._draw_landmarks_cv2(frame, result.hand_landmarks[0])

                if result.gestures and result.gestures[0]:
                    top = result.gestures[0][0]
                    threshold = self.confidence_threshold
                    if top.category_name != "None" and top.score >= threshold:
                        gesture_name = top.category_name
                        gesture_score = top.score
            except Exception as e:
                print(f"[GestureEngine] Recognition error: {e}")

            with self._lock:
                self._current_gesture = gesture_name
                self._current_confidence = gesture_score
                self._latest_frame = frame

            if self._on_frame:
                self._on_frame(frame)

            if gesture_name and self._on_gesture:
                self._on_gesture(gesture_name, gesture_score)

            # FPS limiter
            elapsed = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

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
