# Haptic Feedback

Send haptic feedback to the Televoodoo App based on robot sensor values (e.g., force feedback). The phone generates haptic vibrations proportional to the signal intensity.

## Overview

**Direction**: PC → Phone (reverse of pose data flow)

The `send_haptic` function normalizes your sensor values to 0.0–1.0 intensity and transmits them to the phone.

## Basic Usage

```python
from televoodoo import start_televoodoo, send_haptic, PoseProvider, load_config
import threading
import time

# --- Force Monitoring Thread ---
def force_monitor_loop():
    """Monitor robot force and send haptic feedback."""
    while True:
        force = robot.get_force()  # e.g., 0–50 Newtons
        # Normalize to 0.0–1.0 and send to phone
        send_haptic(force, min_value=0.0, max_value=50.0)
        time.sleep(0.05)  # 20 Hz update rate

# Start force monitoring in background thread
monitor_thread = threading.Thread(target=force_monitor_loop, daemon=True)
monitor_thread.start()

# --- Teleoperation Callback ---
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    robot.move_relative(delta['dx'], delta['dy'], delta['dz'])

# Start televoodoo (blocks until disconnected)
start_televoodoo(callback=on_teleop_event, quiet=True)
```

## send_haptic() Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | float | The sensor value to send (e.g., force in Newtons) |
| `min_value` | float | Minimum expected value (maps to intensity 0.0) |
| `max_value` | float | Maximum expected value (maps to intensity 1.0) |

The function:
- Normalizes `value` to 0.0–1.0 based on min/max
- Clamps to valid range (values outside min/max are clamped)
- Is thread-safe — can be called from any thread while `start_televoodoo` is running

## Use Cases

### Force Feedback

```python
def force_monitor():
    while True:
        force = robot.get_force()
        send_haptic(force, min_value=0, max_value=50)  # 50N max
        time.sleep(0.05)
```

### Proximity Warning

```python
def proximity_monitor():
    while True:
        distance = robot.get_obstacle_distance()
        # Invert: closer = stronger haptic
        intensity = max(0, 1 - distance / 0.5)  # 0.5m range
        send_haptic(intensity, min_value=0, max_value=1)
        time.sleep(0.1)
```

### Collision Detection

```python
def collision_monitor():
    while True:
        if robot.collision_detected():
            send_haptic(1.0, min_value=0, max_value=1)  # Max intensity
        else:
            send_haptic(0.0, min_value=0, max_value=1)  # Off
        time.sleep(0.02)
```

## Intensity Mapping

| Intensity | Haptic Effect |
|-----------|---------------|
| 0.0 | No haptic (off) |
| 0.1–0.3 | Light vibration |
| 0.4–0.6 | Medium vibration |
| 0.7–0.9 | Strong vibration |
| 1.0 | Maximum haptic strength |

## Update Rate

- Recommended: **10–20 Hz** (every 50–100ms)
- Higher rates are supported but may not improve user experience
- Latest value wins if updates arrive faster than the haptic engine can process

## Binary Protocol

For implementers, the HAPTIC message format (12 bytes):

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | magic | `char[4]` | `"TELE"` |
| 4 | msg_type | `uint8` | `7` (HAPTIC) |
| 5 | version | `uint8` | `1` |
| 6 | intensity | `float32` | 0.0–1.0 |
| 10 | channel | `uint8` | Reserved (always 0) |
| 11 | reserved | `uint8` | Reserved (always 0) |

**Byte order**: Little-endian

## Notes

- `channel` is reserved for future multi-motor support
- Messages may arrive out of order (UDP) — the phone uses the latest value
- Haptic feedback requires an active session

## See Also

- **[Usage](USAGE.md)** — General usage patterns
- **[WiFi API](WIFI_API.md)** — Protocol details including HAPTIC message
- **[BLE API](BLE_API.md)** — BLE haptic characteristic
- **[examples/haptic_feedback/](../examples/haptic_feedback/)** — Complete example
