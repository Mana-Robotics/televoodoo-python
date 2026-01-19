# Configuration

Config files define how poses are transformed from the ArUco marker frame to your target coordinate system (robot base, world frame, etc.), what output formats to include, and connection credentials.

## File Format & Location

- **Format**: JSON (`.json` extension recommended)
- **Default search paths** (in order):
  1. Current working directory
  2. Directory of your Python script
  3. Televoodoo module directory

## Complete Config File Example

```json
{
  "authCredentials": {
    "name": "myrobot",
    "code": "ABC123"
  },
  "vel_limit": 0.3,
  "acc_limit": 10.0,
  "includeFormats": {
    "absolute_input": true,
    "delta_input": false,
    "absolute_transformed": true,
    "delta_transformed": true
  },
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": false,
    "euler_degree": true
  },
  "scale": 1.0,
  "outputAxes": {
    "x": 1,
    "y": 1,
    "z": -1
  },
  "targetFrameDegrees": {
    "x": 0.0,
    "y": 0.0,
    "z": 0.5,
    "x_rot_deg": 0,
    "y_rot_deg": 0,
    "z_rot_deg": 90
  }
}
```

## Config Sections

### Authentication Credentials

```json
{
  "authCredentials": {
    "name": "myrobot",
    "code": "ABC123"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Peripheral/server name for connection |
| `code` | string | 6-character authentication code (A-Z, 0-9) |

When set, these credentials are used instead of random ones. The phone only needs to scan the QR code once.

### Resampling Options

```json
{
  "upsample_to_frequency_hz": 200.0,
  "rate_limit_frequency_hz": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `upsample_to_frequency_hz` | float or null | Upsample poses to target frequency using linear extrapolation |
| `rate_limit_frequency_hz` | float or null | Cap output at maximum frequency, drops excess poses |

See [Upsampling & Rate Limiting](UPSAMPLING_RATE_LIMITING.md) for details.

### Motion Limiting Options

```json
{
  "vel_limit": 0.3,
  "acc_limit": 10.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `vel_limit` | float or null | Maximum velocity in m/s. Poses exceeding this are clamped. |
| `acc_limit` | float or null | Maximum acceleration in m/s². Symmetric (applies to deceleration too). |

Motion limiting is a safety feature for robot teleoperation. When consecutive poses would result in motion exceeding the configured limits, the output position is clamped to respect the maximum allowed velocity and acceleration. Orientation is passed through unchanged.

When limiting is applied, the pose data includes `"limited": true` and a warning is logged:

```json
{"type": "motion_limit_warning", "message": "Motion limited: vel=1.50m/s > 0.50m/s", "reasons": ["vel=1.50m/s > 0.50m/s"]}
```

CLI flags: `--vel-limit` and `--acc-limit`

### Output Formats

```json
{
  "includeFormats": {
    "absolute_input": true,
    "delta_input": false,
    "absolute_transformed": true,
    "delta_transformed": true
  }
}
```

| Format | Description |
|--------|-------------|
| `absolute_input` | Raw pose from phone (in marker frame) |
| `delta_input` | Change since first pose (in marker frame) |
| `absolute_transformed` | Pose transformed to target frame |
| `delta_transformed` | Delta transformed to target frame — **best for robot control** |

See [Output Formats](OUTPUT_FORMATS.md) for details.

### Orientation Formats

```json
{
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": false,
    "euler_degree": true
  }
}
```

| Format | Description |
|--------|-------------|
| `quaternion` | Quaternion (qx, qy, qz, qw) — recommended for 3D math |
| `euler_radian` | Euler angles in radians (rx, ry, rz) |
| `euler_degree` | Euler angles in degrees (rx_deg, ry_deg, rz_deg) |

### Scale and Axis Configuration

```json
{
  "scale": 1.0,
  "outputAxes": {
    "x": 1,
    "y": 1,
    "z": -1
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `scale` | float | Scale factor applied to positions (default: 1.0) |
| `outputAxes.x/y/z` | int | Axis multipliers: use `1` or `-1` to flip an axis |

### Target Frame Transform

```json
{
  "targetFrameDegrees": {
    "x": 0.0,
    "y": 0.0,
    "z": 0.5,
    "x_rot_deg": 0,
    "y_rot_deg": 0,
    "z_rot_deg": 90
  }
}
```

Defines the 6DoF transform from the ArUco marker frame to your target frame (e.g., robot base).

| Field | Type | Description |
|-------|------|-------------|
| `x`, `y`, `z` | float | Position offset in meters |
| `x_rot_deg`, `y_rot_deg`, `z_rot_deg` | float | Rotation offset in degrees |

## Loading Config Files

### Basic Loading

```python
from televoodoo import load_config, PoseProvider, start_televoodoo

# Load config from file
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    delta = pose_provider.get_delta(evt)
    if delta:
        # Process pose...
        pass

# Use credentials from config (if specified), or fall back to random
start_televoodoo(
    callback=on_teleop_event,
    name=config.auth_name,  # None = random
    code=config.auth_code   # None = random
)
```

### Passing Config to start_televoodoo

```python
config = load_config("my_robot_config.json")

# Config is used for resampling options
start_televoodoo(callback=handler, config=config)
```

### Default Config

If no config file is specified, `load_config()` returns a default configuration:

```python
config = load_config()  # Uses defaults
```

## Creating Config Files

### Option 1: Manual Creation

Create a JSON file following the format above.

### Option 2: Televoodoo Viewer

Use [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer) to:
- Visually configure coordinate transforms
- Test your configuration in real-time 3D
- Export the config file

### Minimal Config Example

Only include the settings you need to change from defaults:

```json
{
  "authCredentials": {
    "name": "myrobot",
    "code": "ABC123"
  },
  "targetFrameDegrees": {
    "z_rot_deg": 90
  }
}
```

## See Also

- **[Output Formats](OUTPUT_FORMATS.md)** — Detailed explanation of output format options
- **[Upsampling & Rate Limiting](UPSAMPLING_RATE_LIMITING.md)** — Frequency control options
- **[Data Format](DATA_FORMAT.md)** — Pose data fields and coordinate systems
