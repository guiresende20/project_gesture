import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gesture_keys.config import Config, GestureMapping
from gesture_keys.constants import GESTURE_NAMES, DEFAULT_COOLDOWN_MS, DEFAULT_CONFIDENCE_THRESHOLD


class TestConfigDefault:
    def test_default_has_all_gestures(self):
        cfg = Config.default()
        assert set(cfg.mappings.keys()) == set(GESTURE_NAMES)

    def test_default_values(self):
        cfg = Config.default()
        assert cfg.cooldown_ms == DEFAULT_COOLDOWN_MS
        assert cfg.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD

    def test_default_mappings_disabled(self):
        cfg = Config.default()
        for m in cfg.mappings.values():
            assert m.enabled is False
            assert m.keys == []


class TestConfigSaveLoad:
    def test_round_trip(self, tmp_path):
        cfg = Config.default()
        cfg.mappings["Thumb_Up"].keys = ["enter"]
        cfg.mappings["Thumb_Up"].enabled = True
        cfg.mappings["Closed_Fist"].keys = ["alt", "F4"]
        cfg.mappings["Closed_Fist"].enabled = True
        cfg.cooldown_ms = 1000
        cfg.confidence_threshold = 0.8

        path = tmp_path / "config.json"
        cfg.save(path)

        loaded = Config.load(path)
        assert loaded.cooldown_ms == 1000
        assert loaded.confidence_threshold == 0.8
        assert loaded.mappings["Thumb_Up"].keys == ["enter"]
        assert loaded.mappings["Thumb_Up"].enabled is True
        assert loaded.mappings["Closed_Fist"].keys == ["alt", "F4"]
        assert loaded.mappings["Closed_Fist"].enabled is True

    def test_load_missing_file_creates_default(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        cfg = Config.load(path)
        assert path.exists()
        assert set(cfg.mappings.keys()) == set(GESTURE_NAMES)

    def test_load_partial_config(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "cooldown_ms": 500,
            "mappings": {
                "Victory": {"keys": ["ctrl", "v"], "enabled": True},
            },
        }))
        cfg = Config.load(path)
        assert cfg.cooldown_ms == 500
        assert cfg.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert cfg.mappings["Victory"].keys == ["ctrl", "v"]
        assert cfg.mappings["Victory"].enabled is True
        # Missing gestures should get defaults
        assert cfg.mappings["Thumb_Up"].keys == []
        assert cfg.mappings["Thumb_Up"].enabled is False

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "config.json"
        cfg = Config.default()
        cfg.save(path)
        assert path.exists()
