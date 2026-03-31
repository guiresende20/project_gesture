import os
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# pynput requires a display; set a dummy if missing
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

try:
    from pynput.keyboard import Key, KeyCode
    from gesture_keys.key_executor import KeyExecutor, parse_key
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PYNPUT_AVAILABLE, reason="pynput not available (no display)")


class TestParseKey:
    def test_modifier_keys(self):
        assert parse_key("ctrl") == Key.ctrl_l
        assert parse_key("alt") == Key.alt_l
        assert parse_key("shift") == Key.shift_l

    def test_special_keys(self):
        assert parse_key("enter") == Key.enter
        assert parse_key("space") == Key.space
        assert parse_key("f4") == Key.f4
        assert parse_key("esc") == Key.esc

    def test_single_char(self):
        result = parse_key("a")
        assert isinstance(result, KeyCode)

    def test_unknown_key(self):
        assert parse_key("unknownkey") is None

    def test_case_insensitive(self):
        assert parse_key("CTRL") == Key.ctrl_l
        assert parse_key("Enter") == Key.enter
        assert parse_key("F12") == Key.f12


class TestKeyExecutor:
    def test_execute_simple_key(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=0)
        result = executor.execute("Thumb_Up", ["enter"])
        assert result is True
        mock_ctrl.press.assert_called_once()
        mock_ctrl.release.assert_called_once()

    def test_execute_combo(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=0)
        result = executor.execute("Closed_Fist", ["alt", "F4"])
        assert result is True

        # alt pressed, F4 pressed+released, alt released
        press_calls = mock_ctrl.press.call_args_list
        release_calls = mock_ctrl.release.call_args_list
        assert press_calls[0] == call(Key.alt_l)
        assert press_calls[1] == call(Key.f4)
        assert release_calls[0] == call(Key.f4)
        assert release_calls[1] == call(Key.alt_l)

    def test_cooldown_blocks_rapid_fire(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=500)
        result1 = executor.execute("Thumb_Up", ["enter"])
        result2 = executor.execute("Thumb_Up", ["enter"])
        assert result1 is True
        assert result2 is False

    def test_cooldown_per_gesture(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=500)
        result1 = executor.execute("Thumb_Up", ["enter"])
        result2 = executor.execute("Victory", ["space"])
        assert result1 is True
        assert result2 is True

    def test_empty_keys_returns_false(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=0)
        assert executor.execute("Thumb_Up", []) is False

    def test_cooldown_setter(self, mocker):
        mock_ctrl = MagicMock()
        mocker.patch(
            "gesture_keys.key_executor.Controller",
            return_value=mock_ctrl,
        )
        executor = KeyExecutor(cooldown_ms=100)
        executor.cooldown_ms = 500
        assert executor.cooldown_ms == 500
        executor.cooldown_ms = -10
        assert executor.cooldown_ms == 0
