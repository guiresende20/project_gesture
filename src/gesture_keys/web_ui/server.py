from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import cv2
from flask import Flask, current_app, jsonify, render_template, request, Response

if TYPE_CHECKING:
    from gesture_keys.config import Config
    from gesture_keys.gesture_engine import GestureEngine

from gesture_keys.constants import (
    BUNDLE_DIR,
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    COOLDOWN_MAX_MS,
    COOLDOWN_MIN_MS,
    MJPEG_FPS,
    MJPEG_JPEG_QUALITY,
    _is_frozen,
)

log = logging.getLogger("gesture_keys")

if _is_frozen():
    _web_ui_dir = BUNDLE_DIR / "gesture_keys" / "web_ui"
else:
    _web_ui_dir = Path(__file__).parent

app = Flask(
    __name__,
    template_folder=str(_web_ui_dir / "templates"),
    static_folder=str(_web_ui_dir / "static"),
)

_CTX_KEY = "GK_CTX"


class JpegStreamer:
    """Encodes the engine's latest frame to JPEG once per tick and serves the
    cached bytes to any number of MJPEG clients. Without this, every connected
    client would call cv2.imencode independently on the same frame."""

    def __init__(
        self,
        engine: "GestureEngine",
        fps: int = MJPEG_FPS,
        jpeg_quality: int = MJPEG_JPEG_QUALITY,
    ) -> None:
        self._engine = engine
        self._interval = 1.0 / fps
        self._quality = jpeg_quality
        self._cond = threading.Condition()
        self._latest_jpeg: bytes | None = None
        self._frame_seq = 0
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="JpegStreamer")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()

    def _run(self) -> None:
        last_frame_id: int | None = None
        while not self._stop_event.is_set():
            frame = self._engine.latest_frame
            if frame is None:
                time.sleep(self._interval)
                continue
            fid = id(frame)
            if fid == last_frame_id:
                time.sleep(self._interval)
                continue
            try:
                ok, jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality]
                )
            except Exception:
                log.exception("MJPEG encode failed")
                time.sleep(self._interval)
                continue
            if not ok:
                time.sleep(self._interval)
                continue
            last_frame_id = fid
            with self._cond:
                self._latest_jpeg = jpeg.tobytes()
                self._frame_seq += 1
                self._cond.notify_all()
            time.sleep(self._interval)

    def stream(self):
        last_seq = -1
        while not self._stop_event.is_set():
            with self._cond:
                self._cond.wait_for(
                    lambda: self._stop_event.is_set() or self._frame_seq != last_seq,
                    timeout=2.0,
                )
                if self._stop_event.is_set():
                    return
                if self._frame_seq == last_seq or self._latest_jpeg is None:
                    continue
                jpeg = self._latest_jpeg
                last_seq = self._frame_seq
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )


@dataclass
class AppContext:
    config: "Config"
    engine: "GestureEngine"
    save_callback: Callable[[], None]
    config_lock: threading.Lock
    streamer: JpegStreamer


def _ctx() -> AppContext | None:
    return current_app.config.get(_CTX_KEY)


def init_app(
    config: "Config",
    engine: "GestureEngine",
    save_callback: Callable[[], None],
) -> Flask:
    streamer = JpegStreamer(engine)
    streamer.start()
    app.config[_CTX_KEY] = AppContext(
        config=config,
        engine=engine,
        save_callback=save_callback,
        config_lock=threading.Lock(),
        streamer=streamer,
    )
    return app


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    ctx = _ctx()
    if ctx is None:
        return jsonify({"error": "Not initialized"}), 503
    with ctx.config_lock:
        return jsonify({
            "cooldown_ms": ctx.config.cooldown_ms,
            "confidence_threshold": ctx.config.confidence_threshold,
            "mappings": {
                name: {"keys": m.keys, "enabled": m.enabled}
                for name, m in ctx.config.mappings.items()
            },
        })


@app.route("/api/config", methods=["POST"])
def update_config():
    ctx = _ctx()
    if ctx is None:
        return jsonify({"error": "Not initialized"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    with ctx.config_lock:
        try:
            if "cooldown_ms" in data:
                val = int(data["cooldown_ms"])
                ctx.config.cooldown_ms = max(COOLDOWN_MIN_MS, min(val, COOLDOWN_MAX_MS))
            if "confidence_threshold" in data:
                val = float(data["confidence_threshold"])
                ctx.config.confidence_threshold = max(CONFIDENCE_MIN, min(val, CONFIDENCE_MAX))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid numeric value"}), 400

        if "mappings" in data:
            from gesture_keys.config import GestureMapping
            from gesture_keys.constants import GESTURE_NAMES
            for name, mapping_data in data["mappings"].items():
                if name in ctx.config.mappings and name in GESTURE_NAMES:
                    keys = mapping_data.get("keys", [])
                    if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
                        ctx.config.mappings[name] = GestureMapping(
                            keys=keys,
                            enabled=bool(mapping_data.get("enabled", False)),
                        )

    if ctx.save_callback:
        ctx.save_callback()

    return jsonify({"status": "ok"})


@app.route("/api/status", methods=["GET"])
def get_status():
    ctx = _ctx()
    engine = ctx.engine if ctx else None
    gesture = engine.current_gesture if engine else None
    confidence = engine.current_confidence if engine else 0.0
    paused = engine.is_paused if engine else True
    return jsonify({
        "gesture": gesture,
        "confidence": round(confidence, 3),
        "running": not paused,
    })


@app.route("/api/toggle", methods=["POST"])
def toggle_engine():
    ctx = _ctx()
    engine = ctx.engine if ctx else None
    if engine:
        if engine.is_paused:
            engine.resume()
        else:
            engine.pause()
    paused = engine.is_paused if engine else True
    return jsonify({"running": not paused})


@app.route("/api/feed")
def video_feed():
    ctx = _ctx()
    if ctx is None:
        return jsonify({"error": "Not initialized"}), 503
    return Response(
        ctx.streamer.stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def run_server(host: str, port: int) -> None:
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
