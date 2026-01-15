# Data Format

This document describes the pose data format, coordinate systems, and binary protocol used by Televoodoo.

## Coordinate System

### Reference Frame

- All pose values are expressed relative to a **reference coordinate system**
- The reference frame is established by an **[ArUco marker](../assets/televoodoo-aruco-marker.pdf)** scanned by the Televoodoo App
- The phone's pose is tracked in 6 degrees of freedom (6DoF) relative to this marker
- The relationship between the marker frame and your target frame (robot base, world frame) is defined in a [config file](CONFIGURATION.md)

### Coordinate Convention

- **X-axis**: Typically horizontal (right is positive)
- **Y-axis**: Typically depth (forward is positive)
- **Z-axis**: Typically vertical (up is positive)
- **Units**: Meters for position
- **Quaternions**: Normalized (magnitude = 1.0)

> **Note**: The specific orientation depends on how the ArUco marker is positioned. Use [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer) to visually verify and configure your coordinate system.

## Pose Fields

### Movement Control

| Field | Type | Description |
|-------|------|-------------|
| `movement_start` | bool | `True` = new origin for delta calculation |

When `movement_start` is `True`, this pose becomes the new origin for calculating deltas. This allows the user to reposition the phone while not actively controlling, then start a new movement — the robot only applies relative deltas from the new origin.

### Position (Translation)

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `x` | float | meters | Position along X-axis |
| `y` | float | meters | Position along Y-axis |
| `z` | float | meters | Position along Z-axis |

### Rotation (Quaternion)

| Field | Type | Description |
|-------|------|-------------|
| `qx` | float | Quaternion X component |
| `qy` | float | Quaternion Y component |
| `qz` | float | Quaternion Z component |
| `qw` | float | Quaternion W component |

> Quaternions are the preferred representation for 3D rotations — they avoid gimbal lock and interpolate smoothly.

### Rotation (Euler Angles)

When enabled in config, Euler angles are computed from the quaternion:

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `rx`, `ry`, `rz` | float | radians | Rotation vector (axis-angle) |
| `rx_deg`, `ry_deg`, `rz_deg` | float | degrees | Euler angles in degrees |

## Callback Event Format

Your callback receives events with this structure:

```python
{
    "type": "pose",
    "data": {
        "absolute_input": {
            "movement_start": True,
            "x": 0.15,
            "y": 0.20,
            "z": -0.10,
            "qx": 0.01234,
            "qy": -0.56789,
            "qz": 0.12345,
            "qw": 0.81234
        }
    }
}
```

The `data` dictionary contains one or more output formats depending on your [config](CONFIGURATION.md). See [Output Formats](OUTPUT_FORMATS.md) for details.

### Other Event Types

```python
# Command events
{"type": "command", "name": "recording", "value": True}

# Connection events (WiFi)
{"type": "wifi_connected", "client": "192.168.1.50:51234"}
{"type": "wifi_disconnected", "reason": "timeout"}

# Connection events (BLE)
{"type": "ble_connected"}
{"type": "ble_authenticated"}
{"type": "ble_disconnected"}
```

## Binary Protocol

The Televoodoo App sends pose data using a binary protocol over UDP (WiFi/USB) or BLE characteristics.

### Common Header (6 bytes)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | `magic` | `char[4]` | `"TELE"` |
| 4 | `msg_type` | `uint8` | Message type ID |
| 5 | `version` | `uint8` | Protocol version (`1`) |

**Byte order**: Little-endian

### POSE Packet (46 bytes)

| Offset | Field | Type | Bytes |
|--------|-------|------|-------|
| 0 | header | - | 6 |
| 6 | seq | `uint16` | 2 |
| 8 | timestamp_us | `uint64` | 8 |
| 16 | flags | `uint8` | 1 |
| 17 | reserved | `uint8` | 1 |
| 18 | x | `float32` | 4 |
| 22 | y | `float32` | 4 |
| 26 | z | `float32` | 4 |
| 30 | qx | `float32` | 4 |
| 34 | qy | `float32` | 4 |
| 38 | qz | `float32` | 4 |
| 42 | qw | `float32` | 4 |

**Flags Bitfield:**

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `movement_start` | New movement origin (reset deltas) |
| 1-7 | reserved | Must be 0 |

**Python Struct:**

```python
POSE_FORMAT = "<4sBBHQBB7f"  # little-endian, 46 bytes
```

## Data Rate and Timing

### Update Frequency

- The Televoodoo App streams at up to **60 Hz** (limited by ARKit)
- Actual rate depends on phone performance and connection type
- Your callback is invoked for each received pose update

| Connection | Typical Rate |
|------------|--------------|
| WiFi | ~60 Hz |
| USB | ~60 Hz |
| BLE | ~30 Hz (batched) |

### Upsampling

For applications requiring higher frequencies, see [Upsampling & Rate Limiting](UPSAMPLING_RATE_LIMITING.md).

## Validation

### Checking Quaternion Normalization

```python
def validate_quaternion(qx, qy, qz, qw):
    magnitude = (qx**2 + qy**2 + qz**2 + qw**2) ** 0.5
    return abs(magnitude - 1.0) < 0.01
```

## See Also

- **[Output Formats](OUTPUT_FORMATS.md)** — Available output format options
- **[Configuration](CONFIGURATION.md)** — Config file options
- **[WiFi API](WIFI_API.md)** — UDP protocol details
- **[BLE API](BLE_API.md)** — BLE protocol details
