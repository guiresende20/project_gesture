from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np


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
        return self._current_gesture

    @property
    def current_confidence(self) -> float:
        return self._current_confidence

    @property
    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

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
        self._vision = vision

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
        recognizer = vision.GestureRecognizer.create_from_options(options)

        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            print(f"Error: Could not open camera {self._camera_index}")
            return

        try:
            self._recognition_loop(cap, recognizer)
        finally:
            cap.release()
            recognizer.close()

    def _recognition_loop(self, cap, recognizer) -> None:
        mp = self._mp

        while not self._stop_event.is_set():
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

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = recognizer.recognize(mp_image)

            if result.hand_landmarks:
                self._draw_landmarks(frame, result.hand_landmarks[0])

            gesture_name = None
            gesture_score = 0.0

            if result.gestures and result.gestures[0]:
                top = result.gestures[0][0]
                if top.category_name != "None" and top.score >= self._confidence_threshold:
                    gesture_name = top.category_name
                    gesture_score = top.score

            self._current_gesture = gesture_name
            self._current_confidence = gesture_score

            with self._lock:
                self._latest_frame = frame

            if self._on_frame:
                self._on_frame(frame)

            if gesture_name and self._on_gesture:
                self._on_gesture(gesture_name, gesture_score)

    def _draw_landmarks(self, frame: np.ndarray, hand_landmarks: list) -> None:
        from mediapipe.framework.formats import landmark_pb2

        mp_drawing = self._mp.solutions.drawing_utils
        mp_hands = self._mp.solutions.hands

        landmark_list = landmark_pb2.NormalizedLandmarkList()
        for lm in hand_landmarks:
            landmark = landmark_list.landmark.add()
            landmark.x = lm.x
            landmark.y = lm.y
            landmark.z = lm.z

        mp_drawing.draw_landmarks(
            frame,
            landmark_list,
            mp_hands.HAND_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=1),
        )
