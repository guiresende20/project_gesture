import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gesture_keys.gesture_engine import GestureEngine


class TestGestureEngineInit:
    def test_initial_state(self, tmp_path):
        model_path = tmp_path / "fake_model.task"
        model_path.touch()
        engine = GestureEngine(model_path=model_path)
        assert engine.current_gesture is None
        assert engine.current_confidence == 0.0
        assert engine.latest_frame is None
        assert engine.is_paused is False

    def test_pause_resume(self, tmp_path):
        model_path = tmp_path / "fake_model.task"
        model_path.touch()
        engine = GestureEngine(model_path=model_path)
        engine.pause()
        assert engine.is_paused is True
        engine.resume()
        assert engine.is_paused is False


class TestGestureEngineCallbacks:
    def test_on_gesture_callback_stored(self, tmp_path):
        model_path = tmp_path / "fake_model.task"
        model_path.touch()
        callback = MagicMock()
        engine = GestureEngine(
            model_path=model_path,
            on_gesture=callback,
        )
        assert engine._on_gesture is callback

    def test_on_frame_callback_stored(self, tmp_path):
        model_path = tmp_path / "fake_model.task"
        model_path.touch()
        callback = MagicMock()
        engine = GestureEngine(
            model_path=model_path,
            on_frame=callback,
        )
        assert engine._on_frame is callback
