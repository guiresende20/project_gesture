from __future__ import annotations

import webbrowser
from typing import Callable

from PIL import Image, ImageDraw
import pystray

from gesture_keys.constants import WEB_HOST, WEB_PORT


def _create_icon_image(color: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = (0, 180, 0, 255) if color == "green" else (180, 0, 0, 255)
    draw.ellipse([4, 4, size - 4, size - 4], fill=fill)
    # Draw a hand-like symbol (simplified)
    draw.text((size // 2 - 6, size // 2 - 8), "G", fill=(255, 255, 255, 255))
    return img


class TrayIcon:
    def __init__(
        self,
        on_toggle: Callable[[], bool],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._enabled = True
        self._icon: pystray.Icon | None = None

    def _toggle(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._enabled = self._on_toggle()
        self._update_icon()

    def _open_config(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        webbrowser.open(f"http://{WEB_HOST}:{WEB_PORT}")

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_quit()
        icon.stop()

    def _update_icon(self) -> None:
        if self._icon:
            color = "green" if self._enabled else "red"
            self._icon.icon = _create_icon_image(color)

    def run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Disable" if self._enabled else "Enable",
                self._toggle,
                default=True,
            ),
            pystray.MenuItem("Open Config", self._open_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

        self._icon = pystray.Icon(
            name="gesture_keys",
            icon=_create_icon_image("green"),
            title="Gesture Keys",
            menu=menu,
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
