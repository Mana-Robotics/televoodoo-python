# Output Formats

Televoodoo events can include multiple pose representations (raw input, deltas, and transformed variants). This document explains the available formats and how to enable them.

## Available Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `absolute_input` | Raw pose from phone (in marker frame) | Debugging, recording |
| `delta_input` | Change since first pose (in marker frame) | Understanding raw deltas |
| `absolute_transformed` | Pose transformed to target frame | Digital twins, visualization |
| `delta_transformed` | Delta transformed to target frame | **Robot control** |

## Enabling Formats

Configure which formats are included in your [config file](CONFIGURATION.md):

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

## Format Details

### absolute_input

The raw pose exactly as received from the phone, in the ArUco marker's coordinate frame.

```python
{
    "movement_start": True,
    "x": 0.15,
    "y": 0.20,
    "z": -0.10,
    "qx": 0.01234,
    "qy": -0.56789,
    "qz": 0.12345,
    "qw": 0.81234
}
```

**When to use**: Debugging, recording raw data, custom transforms.

### delta_input

The change in pose since the first pose (or since `movement_start=True`), in the marker frame.

```python
{
    "movement_start": False,
    "dx": 0.03,
    "dy": 0.02,
    "dz": 0.02,
    "dqx": 0.01111,
    "dqy": 0.01111,
    "dqz": 0.01111,
    "dqw": 0.99999
}
```

**When to use**: Understanding raw deltas before transformation.

### absolute_transformed

The pose transformed to your target frame, as defined by `targetFrameDegrees`, `scale`, and `outputAxes` in your config.

```python
{
    "movement_start": True,
    "x": 0.20,
    "y": -0.15,
    "z": 0.40,
    "qx": 0.12345,
    "qy": 0.01234,
    "qz": -0.56789,
    "qw": 0.81234,
    "rx": 0.26,      # If euler_radian enabled
    "ry": -0.52,
    "rz": 0.09
}
```

**When to use**: Digital twins, visualization, when you need absolute position in your coordinate system.

### delta_transformed

The delta transformed to your target frame — **recommended for robot control**.

```python
{
    "movement_start": False,
    "dx": 0.02,
    "dy": -0.03,
    "dz": 0.02,
    "rx": 0.01,
    "ry": -0.02,
    "rz": 0.005,
    "dqx": 0.005,
    "dqy": -0.01,
    "dqz": 0.0025,
    "dqw": 0.99999
}
```

**When to use**: Robot teleoperation, any application needing relative movements.

## Using PoseProvider

The `PoseProvider` class simplifies accessing the most common formats:

### get_delta()

Returns the transformed delta (equivalent to `delta_transformed`):

```python
from televoodoo import PoseProvider, load_config

config = load_config("my_config.json")
pose_provider = PoseProvider(config)

def handler(evt):
    delta = pose_provider.get_delta(evt)
    if delta:
        robot.move_relative(delta['dx'], delta['dy'], delta['dz'])
```

### get_absolute()

Returns the transformed absolute pose (equivalent to `absolute_transformed`):

```python
def handler(evt):
    pose = pose_provider.get_absolute(evt)
    if pose:
        update_visualization(pose['x'], pose['y'], pose['z'])
```

## Orientation Formats

Control which orientation representations are included:

```json
{
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": false,
    "euler_degree": true
  }
}
```

| Format | Fields | Description |
|--------|--------|-------------|
| `quaternion` | `qx`, `qy`, `qz`, `qw` | Quaternion — best for 3D math |
| `euler_radian` | `rx`, `ry`, `rz` | Rotation vector in radians |
| `euler_degree` | `rx_deg`, `ry_deg`, `rz_deg` | Euler angles in degrees |

> **Recommendation**: Always include `quaternion` for robust 3D calculations. Add Euler angles only if your application specifically needs them.

## Example: Robot Control Config

A minimal config optimized for robot teleoperation:

```json
{
  "includeFormats": {
    "absolute_input": false,
    "delta_input": false,
    "absolute_transformed": false,
    "delta_transformed": true
  },
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": true,
    "euler_degree": false
  },
  "targetFrameDegrees": {
    "z_rot_deg": 90
  }
}
```

## Example: Recording Config

A config for recording raw data:

```json
{
  "includeFormats": {
    "absolute_input": true,
    "delta_input": true,
    "absolute_transformed": true,
    "delta_transformed": true
  },
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": true,
    "euler_degree": true
  }
}
```

## See Also

- **[Configuration](CONFIGURATION.md)** — Complete config file reference
- **[Data Format](DATA_FORMAT.md)** — Pose fields and coordinate systems
- **[Usage](USAGE.md)** — Delta vs absolute poses
