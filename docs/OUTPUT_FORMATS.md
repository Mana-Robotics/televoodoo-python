# CLI Log Output Data

When running `python -m televoodoo`, the CLI outputs JSON pose data to stdout. The `logData` configuration controls which data is included in this output.

> **Note**: This setting only affects CLI log output. When using the library programmatically, use `PoseProvider.get_delta()`, `PoseProvider.get_absolute()`, or `PoseProvider.get_velocity()` instead—these methods always return their respective data regardless of `logData`.

## Available Data

| Data | Description | Use Case |
|------|-------------|----------|
| `absolute_input` | Raw pose from phone (in marker frame) | Debugging, recording |
| `delta_input` | Change since first pose (in marker frame) | Understanding raw deltas |
| `absolute_transformed` | Pose transformed to target frame | Digital twins, visualization |
| `delta_transformed` | Delta transformed to target frame | Robot control |
| `velocity` | Linear and angular velocities | Velocity-based robot control |

## Configuring Log Output

Configure which data is included in CLI output via your [config file](CONFIGURATION.md):

```json
{
  "logData": {
    "absolute_input": true,
    "delta_input": false,
    "absolute_transformed": true,
    "delta_transformed": true,
    "velocity": false
  }
}
```

## Data Details

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

The pose transformed to your target frame, as defined by `targetFramePose`, `scale`, and `outputAxes` in your config.

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

### velocity

Linear and angular velocities computed from consecutive poses.

```python
{
    "movement_start": False,
    "vx": 0.15,
    "vy": -0.08,
    "vz": 0.02,
    "wx": 0.05,
    "wy": -0.02,
    "wz": 0.01,
    "dt": 0.016
}
```

**When to use**: Velocity-based robot control (e.g., xArm `set_cartesian_velo_continuous`).

## Programmatic Use (Recommended)

For programmatic use, the `PoseProvider` class provides direct access methods that are independent of `logData`:

### get_delta()

Returns the transformed delta (same data as `delta_transformed`):

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

Returns the transformed absolute pose (same data as `absolute_transformed`):

```python
def handler(evt):
    pose = pose_provider.get_absolute(evt)
    if pose:
        update_visualization(pose['x'], pose['y'], pose['z'])
```

### get_velocity()

Returns linear and angular velocities (same data as `velocity`):

```python
def handler(evt):
    vel = pose_provider.get_velocity(evt)
    if vel:
        robot.set_velocity(vel['vx'], vel['vy'], vel['vz'])
```

## Log Data Format (Orientation)

Controls which orientation formats are included in CLI log output. This only affects `python -m televoodoo` JSON output—`PoseProvider` methods always include all orientation formats.

```json
{
  "logDataFormat": {
    "quaternion": true,
    "rotation_vector": true,
    "euler_radian": false,
    "euler_degree": true
  }
}
```

| Format | Fields | Description |
|--------|--------|-------------|
| `quaternion` | `qx`, `qy`, `qz`, `qw` | Quaternion — best for 3D math |
| `rotation_vector` | `rx`, `ry`, `rz` | Rotation vector (axis-angle, radians) |
| `euler_radian` | `x_rot`, `y_rot`, `z_rot` | Euler angles in radians |
| `euler_degree` | `x_rot_deg`, `y_rot_deg`, `z_rot_deg` | Euler angles in degrees |

## Example: Minimal CLI Log Output

A config that only logs delta_transformed (useful when piping to another process):

```json
{
  "logData": {
    "absolute_input": false,
    "delta_input": false,
    "absolute_transformed": false,
    "delta_transformed": true,
    "velocity": false
  },
  "logDataFormat": {
    "quaternion": true,
    "rotation_vector": true,
    "euler_radian": true,
    "euler_degree": false
  },
  "targetFramePose": {
    "z_rot_deg": 90
  }
}
```

## Example: Full Recording Config

A config that logs all data for debugging or data recording:

```json
{
  "logData": {
    "absolute_input": true,
    "delta_input": true,
    "absolute_transformed": true,
    "delta_transformed": true,
    "velocity": true
  },
  "logDataFormat": {
    "quaternion": true,
    "rotation_vector": true,
    "euler_radian": true,
    "euler_degree": true
  }
}
```

## See Also

- **[Configuration](CONFIGURATION.md)** — Complete config file reference
- **[Data Format](DATA_FORMAT.md)** — Pose fields and coordinate systems
- **[Usage](USAGE.md)** — Delta vs absolute poses
