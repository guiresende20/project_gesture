from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from gesture_keys.constants import (
    GESTURE_NAMES,
    DEFAULT_COOLDOWN_MS,
    DEFAULT_CONFIDENCE_THRESHOLD,
)


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
            cooldown_ms=raw.get("cooldown_ms", DEFAULT_COOLDOWN_MS),
            confidence_threshold=raw.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD),
        )

        raw_mappings = raw.get("mappings", {})
        for name in GESTURE_NAMES:
            if name in raw_mappings:
                m = raw_mappings[name]
                config.mappings[name] = GestureMapping(
                    keys=m.get("keys", []),
                    enabled=m.get("enabled", False),
                )
            else:
                config.mappings[name] = GestureMapping()

        return config
