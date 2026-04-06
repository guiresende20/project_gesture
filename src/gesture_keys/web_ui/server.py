from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import cv2
from flask import Flask, jsonify, render_template, request, Response

if TYPE_CHECKING:
    from gesture_keys.config import Config
    from gesture_keys.gesture_engine import GestureEngine

from gesture_keys.constants import BUNDLE_DIR, _is_frozen

if _is_frozen():
    _web_ui_dir = BUNDLE_DIR / "gesture_keys" / "web_ui"
else:
    _web_ui_dir = __import__("pathlib").Path(__file__).parent

app = Flask(
    __name__,
    template_folder=str(_web_ui_dir / "templates"),
    static_folder=str(_web_ui_dir / "static"),
)

_config: Config | None = None
_engine: GestureEngine | None = None
_save_callback = None
_config_lock = threading.Lock()


def init_app(config: Config, engine: GestureEngine, save_callback) -> Flask:
    global _config, _engine, _save_callback
    _config = config
    _engine = engine
    _save_callback = save_callback
    return app


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    if _config is None:
        return jsonify({"error": "Not initialized"}), 503
    with _config_lock:
        return jsonify({
            "cooldown_ms": _config.cooldown_ms,
            "confidence_threshold": _config.confidence_threshold,
            "mappings": {
                name: {"keys": m.keys, "enabled": m.enabled}
                for name, m in _config.mappings.items()
            },
        })


@app.route("/api/config", methods=["POST"])
def update_config():
    if _config is None:
        return jsonify({"error": "Not initialized"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    with _config_lock:
        try:
            if "cooldown_ms" in data:
                val = int(data["cooldown_ms"])
                _config.cooldown_ms = max(100, min(val, 5000))
            if "confidence_threshold" in data:
                val = float(data["confidence_threshold"])
                _config.confidence_threshold = max(0.1, min(val, 1.0))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid numeric value"}), 400

        if "mappings" in data:
            from gesture_keys.config import GestureMapping
            from gesture_keys.constants import GESTURE_NAMES
            for name, mapping_data in data["mappings"].items():
                if name in _config.mappings and name in GESTURE_NAMES:
                    keys = mapping_data.get("keys", [])
                    if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
                        _config.mappings[name] = GestureMapping(
                            keys=keys,
                            enabled=bool(mapping_data.get("enabled", False)),
                        )

    if _save_callback:
        _save_callback()

    return jsonify({"status": "ok"})


@app.route("/api/status", methods=["GET"])
def get_status():
    gesture = _engine.current_gesture if _engine else None
    confidence = _engine.current_confidence if _engine else 0.0
    paused = _engine.is_paused if _engine else True
    return jsonify({
        "gesture": gesture,
        "confidence": round(confidence, 3),
        "running": not paused,
    })


@app.route("/api/toggle", methods=["POST"])
def toggle_engine():
    if _engine:
        if _engine.is_paused:
            _engine.resume()
        else:
            _engine.pause()
    paused = _engine.is_paused if _engine else True
    return jsonify({"running": not paused})


def _generate_mjpeg():
    while True:
        if _engine is None:
            time.sleep(0.1)
            continue
        frame = _engine.latest_frame
        if frame is None:
            time.sleep(0.03)
            continue
        try:
            ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                time.sleep(0.03)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )
        except Exception:
            time.sleep(0.03)
            continue
        time.sleep(0.05)


@app.route("/api/feed")
def video_feed():
    return Response(
        _generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def run_server(host: str, port: int) -> None:
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
