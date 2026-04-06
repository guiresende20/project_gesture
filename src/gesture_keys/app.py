from __future__ import annotations

import logging
import sys
import threading
import time
import webbrowser

from gesture_keys.constants import (
    APP_DIR,
    CONFIG_PATH,
    MODELS_DIR,
    WEB_HOST,
    WEB_PORT,
    _is_frozen,
)
from gesture_keys.config import Config
from gesture_keys.model_manager import ensure_model
from gesture_keys.gesture_engine import GestureEngine
from gesture_keys.key_executor import KeyExecutor
from gesture_keys.web_ui.server import init_app, run_server

log = logging.getLogger("gesture_keys")


def _setup_logging() -> None:
    """Set up logging to file when running as frozen .exe."""
    handlers: list[logging.Handler] = []
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    if _is_frozen():
        fh = logging.FileHandler(APP_DIR / "gesture_keys.log", encoding="utf-8")
        fh.setFormatter(fmt)
        handlers.append(fh)
    else:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        handlers.append(sh)

    logging.basicConfig(level=logging.INFO, handlers=handlers)


def _show_error(title: str, message: str) -> None:
    """Show error dialog on Windows when running without console."""
    if _is_frozen():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # type: ignore[attr-defined]
        except Exception:
            pass
    print(f"ERROR: {title}: {message}")


def main() -> None:
    _setup_logging()
    log.info("Gesture Keys - Starting...")

    # Download model if needed
    try:
        model_path = ensure_model(MODELS_DIR)
        log.info("Model ready at %s", model_path)
    except RuntimeError as e:
        _show_error("Model Download Failed", str(e))
        sys.exit(1)

    # Load config
    config = Config.load(CONFIG_PATH)
    log.info("Config loaded from %s", CONFIG_PATH)

    # Key executor
    executor = KeyExecutor(cooldown_ms=config.cooldown_ms)

    def on_gesture(gesture_name: str, confidence: float) -> None:
        mapping = config.mappings.get(gesture_name)
        if mapping and mapping.enabled and mapping.keys:
            executed = executor.execute(gesture_name, mapping.keys)
            if executed:
                log.info("[Gesture] %s (%.0f%%) -> %s", gesture_name, confidence * 100, " + ".join(mapping.keys))

    # Gesture engine
    engine = GestureEngine(
        model_path=model_path,
        confidence_threshold=config.confidence_threshold,
        on_gesture=on_gesture,
    )

    def save_config() -> None:
        config.save(CONFIG_PATH)
        executor.cooldown_ms = config.cooldown_ms
        engine.confidence_threshold = config.confidence_threshold
        log.info("Config saved.")

    # Web UI
    init_app(config, engine, save_callback=save_config)
    web_thread = threading.Thread(
        target=run_server,
        args=(WEB_HOST, WEB_PORT),
        daemon=True,
    )
    web_thread.start()
    url = f"http://{WEB_HOST}:{WEB_PORT}"
    log.info("Web UI available at %s", url)

    # Start gesture engine
    engine.start()
    log.info("Gesture engine started. Watching for gestures...")

    # Auto-open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    # Try system tray, fall back to simple main-thread loop
    tray_ok = False
    try:
        from gesture_keys.tray import TrayIcon

        def on_toggle() -> bool:
            if engine.is_paused:
                engine.resume()
                log.info("Engine resumed.")
                return True
            else:
                engine.pause()
                log.info("Engine paused.")
                return False

        def on_quit() -> None:
            log.info("Shutting down...")
            engine.stop()

        tray = TrayIcon(on_toggle=on_toggle, on_quit=on_quit)
        tray_ok = True
        log.info("System tray icon active. Right-click for menu.")
        tray.run()
    except Exception as e:
        if not tray_ok:
            log.warning("System tray unavailable (%s), running without it.", e)
        log.info("Running in console mode. Open %s to configure.", url)
        log.info("Press Ctrl+C to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down...")
            engine.stop()
