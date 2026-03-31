# Gesture Keys

Map hand gestures to keyboard shortcuts using your webcam and MediaPipe.

Runs as a background app on Windows with a system tray icon. Configure mappings via a web interface at `localhost:5123`.

## Gestures Available (MediaPipe pre-trained)

| Gesture | Description |
|---|---|
| `Thumb_Up` | Thumbs up |
| `Thumb_Down` | Thumbs down |
| `Closed_Fist` | Closed fist |
| `Open_Palm` | Open hand, palm facing camera |
| `Pointing_Up` | Index finger pointing up |
| `Victory` | V / peace sign |
| `ILoveYou` | "I love you" hand sign |

## Installation

**Requirements:** Python 3.11+, Windows, a webcam.

```bash
pip install -r requirements.txt
```

On first run, the MediaPipe gesture model (~10MB) is downloaded automatically.

## Usage

```bash
python -m src.gesture_keys
```

Or from the `src/` directory:

```bash
python -m gesture_keys
```

- A **system tray icon** appears (green = active, red = paused).
- Open the **config UI** from the tray menu or navigate to `http://localhost:5123`.

## Configuration

In the web UI you can:

- Assign a keyboard shortcut to each gesture (click a field and press your key combo)
- Enable/disable individual gesture mappings
- Adjust the **cooldown** (minimum ms between triggers -- prevents key spamming)
- Adjust the **confidence threshold** (how certain MediaPipe must be before triggering)

### Example Mappings

| Gesture | Keys |
|---|---|
| `Thumb_Up` | `Enter` |
| `Closed_Fist` | `Alt + F4` |
| `Victory` | `Ctrl + C` |
| `Open_Palm` | `Space` |

### Config File

Saved automatically to `config.json` in the project root.

```json
{
  "cooldown_ms": 800,
  "confidence_threshold": 0.7,
  "mappings": {
    "Thumb_Up":    { "keys": ["enter"],     "enabled": true },
    "Closed_Fist": { "keys": ["alt", "F4"], "enabled": true }
  }
}
```

## Architecture

```
Webcam (cv2)
    └─> GestureEngine (thread)   -- MediaPipe gesture recognition
            ├─> on_gesture()     -- triggers KeyExecutor (pynput)
            └─> on_frame()       -- MJPEG stream to web UI

Web UI (Flask @ localhost:5123)  -- configure mappings in browser
System Tray (pystray)            -- enable/disable/quit
Config (config.json)             -- persistent key mappings
```

## Tray Menu

| Action | Description |
|---|---|
| Enable / Disable | Toggle gesture recognition on/off |
| Open Config | Open `http://localhost:5123` in browser |
| Quit | Shut down the application |

## Running Tests

```bash
python -m pytest tests/ -v
```

> Note: `test_key_executor.py` tests are skipped in headless environments (no display). They run fully on Windows.

## Project Structure

```
src/gesture_keys/
├── __main__.py          # Entry point
├── app.py               # Bootstrap / wiring
├── constants.py         # Gesture names, URLs, defaults
├── config.py            # Config load/save/dataclass
├── model_manager.py     # Auto-download gesture model
├── gesture_engine.py    # Webcam + MediaPipe thread
├── key_executor.py      # pynput keyboard simulation + cooldown
├── tray.py              # System tray icon (pystray)
└── web_ui/
    ├── server.py         # Flask REST API + MJPEG feed
    ├── templates/
    │   └── index.html    # Config UI
    └── static/
        ├── style.css
        └── app.js
```
