from __future__ import annotations

import time
from pynput.keyboard import Key, KeyCode, Controller


_MODIFIER_MAP: dict[str, Key] = {
    "ctrl": Key.ctrl_l,
    "control": Key.ctrl_l,
    "alt": Key.alt_l,
    "shift": Key.shift_l,
    "cmd": Key.cmd,
    "super": Key.cmd,
    "win": Key.cmd,
}

_SPECIAL_KEY_MAP: dict[str, Key] = {
    "enter": Key.enter,
    "return": Key.enter,
    "esc": Key.esc,
    "escape": Key.esc,
    "tab": Key.tab,
    "space": Key.space,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "insert": Key.insert,
    "home": Key.home,
    "end": Key.end,
    "pageup": Key.page_up,
    "pagedown": Key.page_down,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "capslock": Key.caps_lock,
    "numlock": Key.num_lock,
    "printscreen": Key.print_screen,
    "scrolllock": Key.scroll_lock,
    "pause": Key.pause,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
    "volumeup": Key.media_volume_up,
    "volumedown": Key.media_volume_down,
    "volumemute": Key.media_volume_mute,
    "playpause": Key.media_play_pause,
    "nexttrack": Key.media_next,
    "prevtrack": Key.media_previous,
}


def parse_key(key_str: str) -> Key | KeyCode | None:
    k = key_str.lower().strip()
    if k in _MODIFIER_MAP:
        return _MODIFIER_MAP[k]
    if k in _SPECIAL_KEY_MAP:
        return _SPECIAL_KEY_MAP[k]
    if len(key_str.strip()) == 1:
        return KeyCode.from_char(key_str.strip())
    return None


class KeyExecutor:
    def __init__(self, cooldown_ms: int = 800) -> None:
        self._controller = Controller()
        self._cooldown_ms = cooldown_ms
        self._last_fire: dict[str, float] = {}

    @property
    def cooldown_ms(self) -> int:
        return self._cooldown_ms

    @cooldown_ms.setter
    def cooldown_ms(self, value: int) -> None:
        self._cooldown_ms = max(0, value)

    def execute(self, gesture: str, keys: list[str]) -> bool:
        if not keys:
            return False

        now_ms = time.monotonic_ns() // 1_000_000
        last = self._last_fire.get(gesture, 0)
        if now_ms - last < self._cooldown_ms:
            return False

        self._last_fire[gesture] = now_ms

        modifiers: list[Key] = []
        regular: list[Key | KeyCode] = []

        for k in keys:
            k_lower = k.lower().strip()
            if k_lower in _MODIFIER_MAP:
                modifiers.append(_MODIFIER_MAP[k_lower])
            else:
                parsed = parse_key(k)
                if parsed is not None:
                    regular.append(parsed)

        if not modifiers and not regular:
            return False

        for m in modifiers:
            self._controller.press(m)
        try:
            for r in regular:
                self._controller.press(r)
                self._controller.release(r)
        finally:
            for m in reversed(modifiers):
                self._controller.release(m)

        return True
