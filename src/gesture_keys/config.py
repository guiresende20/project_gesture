from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gesture_keys.constants import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    COOLDOWN_MAX_MS,
    COOLDOWN_MIN_MS,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_COOLDOWN_MS,
    GESTURE_NAMES,
)

log = logging.getLogger("gesture_keys")


@dataclass
class GestureMapping:
    keys: list[str] = field(default_factory=list)
    enabled: bool = False


@dataclass
class Profile:
    """Per-application override. `mappings` is partial — gestures not listed
    (or with empty keys) fall through to the default `Config.mappings`."""
    name: str = ""
    app_patterns: list[str] = field(default_factory=list)
    mappings: dict[str, GestureMapping] = field(default_factory=dict)


@dataclass
class Config:
    cooldown_ms: int = DEFAULT_COOLDOWN_MS
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    camera_index: int = 0
    default_enabled: bool = True
    mappings: dict[str, GestureMapping] = field(default_factory=dict)
    profiles: list[Profile] = field(default_factory=list)

    @staticmethod
    def default() -> Config:
        mappings = {name: GestureMapping() for name in GESTURE_NAMES}
        return Config(mappings=mappings)

    def save(self, path: Path) -> None:
        data = {
            "cooldown_ms": self.cooldown_ms,
            "confidence_threshold": self.confidence_threshold,
            "camera_index": self.camera_index,
            "default_enabled": self.default_enabled,
            "mappings": {
                name: {"keys": m.keys, "enabled": m.enabled}
                for name, m in self.mappings.items()
            },
            "profiles": [
                {
                    "name": p.name,
                    "app_patterns": p.app_patterns,
                    "mappings": {
                        name: {"keys": m.keys, "enabled": m.enabled}
                        for name, m in p.mappings.items()
                    },
                }
                for p in self.profiles
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> Config:
        if not path.exists():
            cfg = Config.default()
            cfg.save(path)
            return cfg

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("config: invalid JSON in %s; backing up and recreating default.", path)
            backup_path = _backup_invalid_config(path)
            if backup_path is not None:
                log.warning("config: invalid file backed up to %s.", backup_path)
            cfg = Config.default()
            cfg.save(path)
            return cfg
        if not isinstance(raw, dict):
            log.warning("config: root value in %s is not an object; recreating default.", path)
            cfg = Config.default()
            cfg.save(path)
            return cfg

        config = Config(
            cooldown_ms=_validate_cooldown(raw.get("cooldown_ms")),
            confidence_threshold=_validate_threshold(raw.get("confidence_threshold")),
            camera_index=_validate_camera_index(raw.get("camera_index")),
            default_enabled=_validate_default_enabled(raw.get("default_enabled")),
        )

        raw_mappings = raw.get("mappings") or {}
        if not isinstance(raw_mappings, dict):
            log.warning("config: 'mappings' is not an object; ignoring.")
            raw_mappings = {}

        for name in GESTURE_NAMES:
            config.mappings[name] = _validate_mapping(name, raw_mappings.get(name))

        config.profiles = _validate_profiles(raw.get("profiles"))

        return config


def find_active_profile(
    profiles: list[Profile], active_app: str | None
) -> Profile | None:
    """First profile whose any pattern substring-matches `active_app` (case-
    insensitive). Patterns are compared against the lowercased exe basename
    produced by `active_window.get_active_app`."""
    if not active_app:
        return None
    target = active_app.lower()
    for profile in profiles:
        for pattern in profile.app_patterns:
            if pattern and pattern.lower() in target:
                return profile
    return None


def resolve_mapping(
    config: Config, gesture: str, active_app: str | None
) -> GestureMapping | None:
    """Profile-scoped resolution:
    - If a profile matches the active app: only that profile's overrides fire.
      Gestures not overridden in the profile return None (no default fallback).
    - If no profile matches: the default mapping fires only when
      `default_enabled` is True. Otherwise return None."""
    profile = find_active_profile(config.profiles, active_app)
    if profile is not None:
        override = profile.mappings.get(gesture)
        if override is not None and override.keys and override.enabled:
            return override
        return None
    if not config.default_enabled:
        return None
    return config.mappings.get(gesture)


def _validate_cooldown(value: object) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        if value is not None:
            log.warning("config: cooldown_ms %r is not numeric; using default.", value)
        return DEFAULT_COOLDOWN_MS
    clamped = max(COOLDOWN_MIN_MS, min(int(value), COOLDOWN_MAX_MS))
    if clamped != value:
        log.warning(
            "config: cooldown_ms %r out of range [%d, %d]; clamped to %d.",
            value, COOLDOWN_MIN_MS, COOLDOWN_MAX_MS, clamped,
        )
    return clamped


def _validate_camera_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if value is not None:
            log.warning("config: camera_index %r is not an integer; using 0.", value)
        return 0
    idx = int(value)
    if idx < 0:
        log.warning("config: camera_index %r is negative; using 0.", value)
        return 0
    return idx


def _validate_default_enabled(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, bool):
        log.warning("config: default_enabled %r is not a bool; using True.", value)
        return True
    return value


def _validate_threshold(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        if value is not None:
            log.warning("config: confidence_threshold %r is not numeric; using default.", value)
        return DEFAULT_CONFIDENCE_THRESHOLD
    clamped = max(CONFIDENCE_MIN, min(float(value), CONFIDENCE_MAX))
    if clamped != value:
        log.warning(
            "config: confidence_threshold %r out of range [%.1f, %.1f]; clamped to %.2f.",
            value, CONFIDENCE_MIN, CONFIDENCE_MAX, clamped,
        )
    return clamped


def _validate_mapping(gesture: str, raw: object) -> GestureMapping:
    if raw is None:
        return GestureMapping()
    if not isinstance(raw, dict):
        log.warning("config: mapping for %s is not an object; using empty.", gesture)
        return GestureMapping()

    raw_keys = raw.get("keys", [])
    if not isinstance(raw_keys, list) or not all(isinstance(k, str) for k in raw_keys):
        log.warning("config: mapping for %s has invalid 'keys'; using empty.", gesture)
        keys: list[str] = []
    else:
        keys = raw_keys

    return GestureMapping(keys=keys, enabled=bool(raw.get("enabled", False)))


def _validate_profiles(raw: object) -> list[Profile]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        log.warning("config: 'profiles' is not a list; ignoring.")
        return []

    profiles: list[Profile] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            log.warning("config: profile #%d is not an object; skipping.", idx)
            continue

        name = item.get("name")
        if not isinstance(name, str):
            name = ""

        raw_patterns = item.get("app_patterns", [])
        if not isinstance(raw_patterns, list):
            log.warning("config: profile %r has invalid 'app_patterns'; using empty.", name)
            patterns: list[str] = []
        else:
            patterns = [p.strip() for p in raw_patterns if isinstance(p, str) and p.strip()]

        raw_mappings = item.get("mappings", {})
        mappings: dict[str, GestureMapping] = {}
        if isinstance(raw_mappings, dict):
            for gesture_name, mapping_raw in raw_mappings.items():
                if gesture_name in GESTURE_NAMES:
                    mappings[gesture_name] = _validate_mapping(gesture_name, mapping_raw)
        else:
            log.warning("config: profile %r has invalid 'mappings'; using empty.", name)

        profiles.append(Profile(name=name, app_patterns=patterns, mappings=mappings))

    return profiles


def _backup_invalid_config(path: Path) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.invalid-{timestamp}")
    try:
        path.replace(backup_path)
    except OSError:
        log.warning("config: failed to back up invalid config %s.", path, exc_info=True)
        return None
    return backup_path
