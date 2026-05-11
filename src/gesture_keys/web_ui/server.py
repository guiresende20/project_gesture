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
    client would call cv2.imencode independently on the same frame.

    Reads the engine via a getter so the app can hot-swap engines (e.g. when
    the user changes the camera index) without restarting the streamer."""

    def __init__(
        self,
        engine_getter: Callable[[], "GestureEngine | None"],
        fps: int = MJPEG_FPS,
        jpeg_quality: int = MJPEG_JPEG_QUALITY,
    ) -> None:
        self._engine_getter = engine_getter
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
            engine = self._engine_getter()
            frame = engine.latest_frame if engine is not None else None
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
    engine: "GestureEngine"  # swapped when camera_index changes
    save_callback: Callable[[], None]
    config_lock: threading.Lock
    streamer: JpegStreamer
    restart_engine: Callable[[], None] | None = None


def _ctx() -> AppContext | None:
    return current_app.config.get(_CTX_KEY)


def init_app(
    config: "Config",
    engine: "GestureEngine",
    save_callback: Callable[[], None],
    restart_engine: Callable[[], None] | None = None,
) -> "AppContext":
    ctx_holder: dict = {}

    def get_engine():
        c = ctx_holder.get("ctx")
        return c.engine if c is not None else None

    streamer = JpegStreamer(get_engine)
    streamer.start()
    ctx = AppContext(
        config=config,
        engine=engine,
        save_callback=save_callback,
        config_lock=threading.Lock(),
        streamer=streamer,
        restart_engine=restart_engine,
    )
    ctx_holder["ctx"] = ctx
    app.config[_CTX_KEY] = ctx
    return ctx


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
            "camera_index": ctx.config.camera_index,
            "default_enabled": ctx.config.default_enabled,
            "mappings": {
                name: {"keys": m.keys, "enabled": m.enabled}
                for name, m in ctx.config.mappings.items()
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
                for p in ctx.config.profiles
            ],
        })


@app.route("/api/config", methods=["POST"])
def update_config():
    ctx = _ctx()
    if ctx is None:
        return jsonify({"error": "Not initialized"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    camera_index_changed = False
    with ctx.config_lock:
        try:
            if "cooldown_ms" in data:
                val = int(data["cooldown_ms"])
                ctx.config.cooldown_ms = max(COOLDOWN_MIN_MS, min(val, COOLDOWN_MAX_MS))
            if "confidence_threshold" in data:
                val = float(data["confidence_threshold"])
                ctx.config.confidence_threshold = max(CONFIDENCE_MIN, min(val, CONFIDENCE_MAX))
            if "camera_index" in data:
                val = int(data["camera_index"])
                if val < 0:
                    return jsonify({"error": "camera_index must be >= 0"}), 400
                if val != ctx.config.camera_index:
                    ctx.config.camera_index = val
                    camera_index_changed = True
            if "default_enabled" in data:
                ctx.config.default_enabled = bool(data["default_enabled"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid numeric value"}), 400

        from gesture_keys.config import GestureMapping, Profile
        from gesture_keys.constants import GESTURE_NAMES

        if "mappings" in data:
            for name, mapping_data in data["mappings"].items():
                if name in ctx.config.mappings and name in GESTURE_NAMES:
                    keys = mapping_data.get("keys", [])
                    if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
                        ctx.config.mappings[name] = GestureMapping(
                            keys=keys,
                            enabled=bool(mapping_data.get("enabled", False)),
                        )

        if "profiles" in data:
            profiles_data = data["profiles"]
            if isinstance(profiles_data, list):
                new_profiles: list[Profile] = []
                for item in profiles_data:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name", "")
                    if not isinstance(name, str):
                        name = ""
                    raw_patterns = item.get("app_patterns", [])
                    patterns: list[str] = []
                    if isinstance(raw_patterns, list):
                        patterns = [
                            p.strip() for p in raw_patterns
                            if isinstance(p, str) and p.strip()
                        ]
                    mappings_map: dict[str, GestureMapping] = {}
                    raw_mappings = item.get("mappings", {})
                    if isinstance(raw_mappings, dict):
                        for gname, mdata in raw_mappings.items():
                            if gname not in GESTURE_NAMES or not isinstance(mdata, dict):
                                continue
                            keys = mdata.get("keys", [])
                            if not isinstance(keys, list) or not all(
                                isinstance(k, str) for k in keys
                            ):
                                continue
                            mappings_map[gname] = GestureMapping(
                                keys=keys,
                                enabled=bool(mdata.get("enabled", False)),
                            )
                    new_profiles.append(Profile(
                        name=name,
                        app_patterns=patterns,
                        mappings=mappings_map,
                    ))
                ctx.config.profiles = new_profiles

    if ctx.save_callback:
        ctx.save_callback()

    if camera_index_changed and ctx.restart_engine is not None:
        try:
            ctx.restart_engine()
        except Exception:
            log.exception("Engine restart after camera change failed")
            return jsonify({"status": "ok", "warning": "engine restart failed"}), 200

    return jsonify({"status": "ok"})


@app.route("/api/cameras", methods=["GET"])
def list_cameras_endpoint():
    ctx = _ctx()
    if ctx is None:
        return jsonify({"error": "Not initialized"}), 503
    from gesture_keys.camera import list_cameras
    with ctx.config_lock:
        current_index = ctx.config.camera_index
    cams = list_cameras(current_index)
    return jsonify({
        "cameras": [
            {"index": c.index, "available": c.available, "current": c.current}
            for c in cams
        ],
    })


@app.route("/api/status", methods=["GET"])
def get_status():
    ctx = _ctx()
    engine = ctx.engine if ctx else None
    gesture = engine.current_gesture if engine else None
    confidence = engine.current_confidence if engine else 0.0
    paused = engine.is_paused if engine else True

    from gesture_keys.active_window import get_active_app
    from gesture_keys.config import find_active_profile

    active_app = get_active_app()
    active_profile_name = None
    if ctx is not None:
        profile = find_active_profile(ctx.config.profiles, active_app)
        if profile is not None:
            active_profile_name = profile.name or None

    return jsonify({
        "gesture": gesture,
        "confidence": round(confidence, 3),
        "running": not paused,
        "active_app": active_app,
        "active_profile": active_profile_name,
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
