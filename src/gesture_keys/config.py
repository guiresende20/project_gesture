from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
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
class Config:
    cooldown_ms: int = DEFAULT_COOLDOWN_MS
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    mappings: dict[str, GestureMapping] = field(default_factory=dict)

    @staticmethod
    def default() -> Config:
        mappings = {name: GestureMapping() for name in GESTURE_NAMES}
        return Config(mappings=mappings)

    def save(self, path: Path) -> None:
        data = {
            "cooldown_ms": self.cooldown_ms,
            "confidence_threshold": self.confidence_threshold,
            "mappings": {
                name: {"keys": m.keys, "enabled": m.enabled}
                for name, m in self.mappings.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> Config:
        if not path.exists():
            cfg = Config.default()
            cfg.save(path)
            return cfg

        raw = json.loads(path.read_text(encoding="utf-8"))

        config = Config(
            cooldown_ms=_validate_cooldown(raw.get("cooldown_ms")),
            confidence_threshold=_validate_threshold(raw.get("confidence_threshold")),
        )

        raw_mappings = raw.get("mappings") or {}
        if not isinstance(raw_mappings, dict):
            log.warning("config: 'mappings' is not an object; ignoring.")
            raw_mappings = {}

        for name in GESTURE_NAMES:
            config.mappings[name] = _validate_mapping(name, raw_mappings.get(name))

        return config


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
