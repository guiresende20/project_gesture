import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gesture_keys.config import (
    Config,
    GestureMapping,
    Profile,
    find_active_profile,
    resolve_mapping,
)


def _make_config_with_profile():
    cfg = Config.default()
    cfg.mappings["Thumb_Up"] = GestureMapping(keys=["enter"], enabled=True)
    cfg.mappings["Victory"] = GestureMapping(keys=["ctrl", "c"], enabled=True)
    cfg.profiles = [
        Profile(
            name="Spotify",
            app_patterns=["spotify"],
            mappings={
                "Victory": GestureMapping(keys=["playpause"], enabled=True),
            },
        ),
    ]
    return cfg


class TestProfileSerialization:
    def test_round_trip(self, tmp_path):
        cfg = _make_config_with_profile()
        path = tmp_path / "config.json"
        cfg.save(path)

        loaded = Config.load(path)
        assert len(loaded.profiles) == 1
        p = loaded.profiles[0]
        assert p.name == "Spotify"
        assert p.app_patterns == ["spotify"]
        assert p.mappings["Victory"].keys == ["playpause"]
        assert p.mappings["Victory"].enabled is True

    def test_load_missing_profiles_is_empty(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"cooldown_ms": 500}))
        cfg = Config.load(path)
        assert cfg.profiles == []

    def test_load_invalid_profiles_is_empty(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"profiles": "not a list"}))
        cfg = Config.load(path)
        assert cfg.profiles == []

    def test_load_skips_malformed_entries(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "profiles": [
                "not an object",
                {"name": "Good", "app_patterns": ["chrome"], "mappings": {}},
            ],
        }))
        cfg = Config.load(path)
        assert len(cfg.profiles) == 1
        assert cfg.profiles[0].name == "Good"

    def test_load_strips_empty_patterns(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "profiles": [
                {"name": "X", "app_patterns": ["  ", "chrome", ""], "mappings": {}},
            ],
        }))
        cfg = Config.load(path)
        assert cfg.profiles[0].app_patterns == ["chrome"]

    def test_load_drops_unknown_gestures_in_profile(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "profiles": [
                {
                    "name": "X",
                    "app_patterns": ["x"],
                    "mappings": {
                        "Victory": {"keys": ["a"], "enabled": True},
                        "BogusGesture": {"keys": ["b"], "enabled": True},
                    },
                },
            ],
        }))
        cfg = Config.load(path)
        assert "Victory" in cfg.profiles[0].mappings
        assert "BogusGesture" not in cfg.profiles[0].mappings


class TestFindActiveProfile:
    def test_substring_match(self):
        cfg = _make_config_with_profile()
        assert find_active_profile(cfg.profiles, "spotify").name == "Spotify"

    def test_substring_match_with_path_like_active_app(self):
        cfg = _make_config_with_profile()
        # active_app comes from active_window as the exe stem (lowercased)
        assert find_active_profile(cfg.profiles, "spotify").name == "Spotify"

    def test_case_insensitive(self):
        cfg = _make_config_with_profile()
        assert find_active_profile(cfg.profiles, "SPOTIFY").name == "Spotify"

    def test_no_match(self):
        cfg = _make_config_with_profile()
        assert find_active_profile(cfg.profiles, "notepad") is None

    def test_none_active_app(self):
        cfg = _make_config_with_profile()
        assert find_active_profile(cfg.profiles, None) is None

    def test_first_match_wins(self):
        cfg = Config.default()
        cfg.profiles = [
            Profile(name="A", app_patterns=["chrome"]),
            Profile(name="B", app_patterns=["chrome"]),
        ]
        assert find_active_profile(cfg.profiles, "chrome").name == "A"

    def test_empty_pattern_ignored(self):
        cfg = Config.default()
        cfg.profiles = [Profile(name="X", app_patterns=["", "  "])]
        assert find_active_profile(cfg.profiles, "anything") is None


class TestResolveMapping:
    def test_profile_override_wins(self):
        cfg = _make_config_with_profile()
        m = resolve_mapping(cfg, "Victory", "spotify")
        assert m.keys == ["playpause"]

    def test_default_fires_when_no_app(self):
        cfg = _make_config_with_profile()
        m = resolve_mapping(cfg, "Victory", None)
        assert m.keys == ["ctrl", "c"]

    def test_default_fires_when_app_doesnt_match_any_profile(self):
        cfg = _make_config_with_profile()
        m = resolve_mapping(cfg, "Victory", "notepad")
        assert m.keys == ["ctrl", "c"]

    def test_profile_match_blocks_unoverridden_gesture(self):
        cfg = _make_config_with_profile()
        # Thumb_Up has a default mapping but the Spotify profile doesn't override it —
        # under the new strict semantics, no fallback to default inside a matched profile.
        assert resolve_mapping(cfg, "Thumb_Up", "spotify") is None

    def test_profile_match_blocks_when_override_disabled(self):
        cfg = _make_config_with_profile()
        cfg.profiles[0].mappings["Victory"].enabled = False
        assert resolve_mapping(cfg, "Victory", "spotify") is None

    def test_profile_match_blocks_when_override_has_no_keys(self):
        cfg = _make_config_with_profile()
        cfg.profiles[0].mappings["Victory"].keys = []
        assert resolve_mapping(cfg, "Victory", "spotify") is None

    def test_default_disabled_silences_unmatched_app(self):
        cfg = _make_config_with_profile()
        cfg.default_enabled = False
        assert resolve_mapping(cfg, "Victory", "notepad") is None
        assert resolve_mapping(cfg, "Thumb_Up", None) is None

    def test_default_disabled_does_not_affect_profile_matches(self):
        cfg = _make_config_with_profile()
        cfg.default_enabled = False
        m = resolve_mapping(cfg, "Victory", "spotify")
        assert m.keys == ["playpause"]

    def test_returns_none_for_unknown_gesture(self):
        cfg = Config.default()
        assert resolve_mapping(cfg, "NotAGesture", None) is None


class TestDefaultEnabledSerialization:
    def test_round_trip_true(self, tmp_path):
        cfg = Config.default()
        cfg.default_enabled = True
        path = tmp_path / "config.json"
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.default_enabled is True

    def test_round_trip_false(self, tmp_path):
        cfg = Config.default()
        cfg.default_enabled = False
        path = tmp_path / "config.json"
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.default_enabled is False

    def test_load_missing_defaults_to_true(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"cooldown_ms": 500}))
        cfg = Config.load(path)
        assert cfg.default_enabled is True

    def test_load_invalid_defaults_to_true(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"default_enabled": "yes"}))
        cfg = Config.load(path)
        assert cfg.default_enabled is True
