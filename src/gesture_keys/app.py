from __future__ import annotations

import sys
import threading
import time
import webbrowser

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
from gesture_keys.web_ui.server import init_app, run_server


def main() -> None:
    print("Gesture Keys - Starting...")

    # Download model if needed
    try:
        model_path = ensure_model(MODELS_DIR)
        print(f"Model ready at {model_path}")
    except RuntimeError as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)

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
        engine.confidence_threshold = config.confidence_threshold
        print("Config saved.")

    # Web UI
    init_app(config, engine, save_callback=save_config)
    web_thread = threading.Thread(
        target=run_server,
        args=(WEB_HOST, WEB_PORT),
        daemon=True,
    )
    web_thread.start()
    url = f"http://{WEB_HOST}:{WEB_PORT}"
    print(f"Web UI available at {url}")

    # Start gesture engine
    engine.start()
    print("Gesture engine started. Watching for gestures...")

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
                print("Engine resumed.")
                return True
            else:
                engine.pause()
                print("Engine paused.")
                return False

        def on_quit() -> None:
            print("Shutting down...")
            engine.stop()

        tray = TrayIcon(on_toggle=on_toggle, on_quit=on_quit)
        tray_ok = True
        print("System tray icon active. Right-click for menu.")
        tray.run()
    except Exception as e:
        if not tray_ok:
            print(f"System tray unavailable ({e}), running without it.")
        print(f"Running in console mode. Open {url} to configure.")
        print("Press Ctrl+C to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            engine.stop()
