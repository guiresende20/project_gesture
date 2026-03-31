from __future__ import annotations

import sys
import threading

from gesture_keys.constants import (
    CONFIG_PATH,
    MODELS_DIR,
    WEB_HOST,
    WEB_PORT,
)
from gesture_keys.config import Config
from gesture_keys.model_manager import ensure_model
from gesture_keys.gesture_engine import GestureEngine
from gesture_keys.key_executor import KeyExecutor
from gesture_keys.tray import TrayIcon
from gesture_keys.web_ui.server import init_app, run_server


def main() -> None:
    print("Gesture Keys - Starting...")

    # Download model if needed
    model_path = ensure_model(MODELS_DIR)

    # Load config
    config = Config.load(CONFIG_PATH)
    print(f"Config loaded from {CONFIG_PATH}")

    # Key executor
    executor = KeyExecutor(cooldown_ms=config.cooldown_ms)

    def on_gesture(gesture_name: str, confidence: float) -> None:
        mapping = config.mappings.get(gesture_name)
        if mapping and mapping.enabled and mapping.keys:
            executed = executor.execute(gesture_name, mapping.keys)
            if executed:
                print(f"[Gesture] {gesture_name} ({confidence:.0%}) -> {' + '.join(mapping.keys)}")

    # Gesture engine
    engine = GestureEngine(
        model_path=model_path,
        confidence_threshold=config.confidence_threshold,
        on_gesture=on_gesture,
    )

    def save_config() -> None:
        config.save(CONFIG_PATH)
        executor.cooldown_ms = config.cooldown_ms
        engine._confidence_threshold = config.confidence_threshold
        print("Config saved.")

    # Web UI
    init_app(config, engine, save_callback=save_config)
    web_thread = threading.Thread(
        target=run_server,
        args=(WEB_HOST, WEB_PORT),
        daemon=True,
    )
    web_thread.start()
    print(f"Web UI available at http://{WEB_HOST}:{WEB_PORT}")

    # Start gesture engine
    engine.start()
    print("Gesture engine started. Watching for gestures...")

    # Tray icon callbacks
    def on_toggle() -> bool:
        if engine.is_paused:
            engine.resume()
            print("Engine resumed.")
            return True
        else:
            engine.pause()
            print("Engine paused.")
            return False

    def on_quit() -> None:
        print("Shutting down...")
        engine.stop()
        sys.exit(0)

    # System tray (blocks main thread)
    tray = TrayIcon(on_toggle=on_toggle, on_quit=on_quit)
    try:
        tray.run()
    except KeyboardInterrupt:
        on_quit()
