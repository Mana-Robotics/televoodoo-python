# Teleop an xArm 5/6/7 or Lite 6 Robot Arm

Teleoperate a UFACTORY xArm end-effector pose using a smartphone as a 6DoF controller.

## Control Modes

You **must** specify a control mode via `--mode`. Available modes:

| Mode | Description | xArm API |
|------|-------------|----------|
| `delta-pose` | Position control via deltas from movement origin | `set_servo_cartesian_aa` |
| `velocity` | Velocity control (vx, vy, vz, wx, wy, wz) | `vc_set_cartesian_velocity` |

This example:
- Receives phone pose samples (position + quaternion orientation)
- Applies Televoodoo's `OutputConfig` transforms (axes / target frame)
- Streams commands to the robot based on the selected mode

## Requirements

- **xArm SDK**: `pip install xarm-python-sdk`
- **Robot**: UFACTORY xArm / Lite6 reachable via IP on your LAN

## Safety

⚠️ This can move a real robot. Configure speed and acceleration limits, keep the workspace clear and keep an E-stop accessible.

## Configuration

Copy `xarm_config.json` and adapt it for your setup:

```json
{
  "authCredentials": {
    "name": "myXarm",
    "code": "CDE456"
  },
  "targetFrameDegrees": {
    "x": 0,
    "y": 0,
    "z": 0,
    "x_rot_deg": 0,
    "y_rot_deg": 180,
    "z_rot_deg": 0
  },
  "vel_limit": 0.5,
  "acc_limit": 50.0,
  "scale": 1000
}
```

### Target Frame

Use `targetFrameDegrees` to align the ArUco reference marker (to be scanned with Televooodoo App) with your robot. For example, a ceiling-mounted robot might need `"y_rot_deg": 180`.

### TCP Velocity Limit

For UFACTORY Lite 6 the max TCP speed limit is 500 mm/s (see Lite 6 user manual). If exceeded, the robot controller will raise an error and stop.


> 👉 Recommended: start with limit of **0.3** (m/s). 


### TCP Acceleration Limit

For UFACTORY Lite 6 the TCP acceleration limit is 50,000 mm/s² (see Lite 6 user manual).

> 👉 Recommended: start with limit to **10.0** (m/s²). 

### Scale Factor for Unit Conversion

- Televoodoo outputs positions in **meters**
- xArm expects positions in **millimeters**
- Set `"scale": 1000` to convert m → mm


## Run

### Dry-run with delta-pose mode

```bash
python examples/teleop_xarm/teleop_xarm.py \
  --mode delta-pose \
  --dry-run
```

### Dry-run with config file (mode from config)

If `mode` is set in the config file, you don't need `--mode`:

```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --dry-run
```

### Real mode with delta-pose

Use delta-pose mode for maximum precission, reactivity and "direct-control" feeling. 


```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --mode delta-pose \
  --ip 10.23.4.21 \
  --enable-motion
```

> ⚠️ For smooth motion, the phone must provide pose tracking at ~60 Hz or higher. This is supported by most recent iPhones, but only by a limited number of Android devices. Please check the “Tracking frequency” field in the Android app GUI to verify support.

### Velocity mode

Use velocity mode for smoother control. This mode computes linear and angular velocities from consecutive pose samples.

```bash
# Real mode with velocity control and safety limits
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --mode velocity \
  --ip 10.23.4.21 \
  --enable-motion
```

> ⚠️ Recommended for phones supoorting less than ~60 Hz pose tracking frequency.

Note: `--vel-limit` is in m/s (scaled automatically based on config, e.g., 0.1 m/s → 100 mm/s with scale=1000). `--ang-limit` is in rad/s.

## Output (dry-run)

### delta-pose / absolute-pose modes

Prints pose targets [x, y, z, rx, ry, rz] which in Real Mode are sent to the robot:

```
Using config: examples/teleop_xarm/xarm_config.json
Control mode: delta-pose
xArm mode: 1 (servo position control)
delta-pose target: [300.5, 120.3, 450.2, 0.01, -0.02, 0.15]
delta-pose target: [301.2, 121.0, 449.8, 0.02, -0.01, 0.16]
...
```

### velocity mode

Prints velocity commands [vx, vy, vz, wx, wy, wz] in mm/s and rad/s:

```
Using config: examples/teleop_xarm/xarm_config.json
Control mode: velocity
xArm mode: 5 (Cartesian velocity control)
velocity: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] (movement_start)
velocity: [15.2, -8.3, 22.1, 0.02, -0.01, 0.03] (dt=0.0333s)
velocity: [18.5, -10.1, 25.8, 0.03, -0.02, 0.04] (dt=0.0321s)
...
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to Televoodoo config JSON |
| `--mode MODE` | **Required.** Control mode: `delta-pose` or `velocity`. ⚠️ DO NOT USE `absolute-pose` for robot teleoperation! |
| `--ip ADDRESS` | xArm IP address (required with `--enable-motion`) |
| `--enable-motion` | Enable robot motion (dangerous) |
| `--dry-run` | Print poses only, don't connect to robot (default) |
| `--vel-limit FLOAT` | Maximum velocity in m/s |
| `--acc-limit FLOAT` | Maximum acceleration in m/s² (symmetric for acceleration / deceleration) |
| `--ang-limit FLOAT` | Maximum angular velocity in rad/s (velocity mode only) |

### Motion Limiting

**Position Modes (delta-pose, absolute-pose):**
- `--vel-limit`: Clamps position changes to not exceed the specified speed (m/s)
- `--acc-limit`: Limits how quickly speed can change (m/s², symmetric)

When limits are applied, a warning is logged and the pose data includes `"limited": true`.

**Velocity Mode:**
- `--vel-limit`: Clamps linear velocity components (m/s, scaled automatically)
- `--ang-limit`: Clamps angular velocity components (rad/s)

If no limits are specified, velocities are sent to the robot without clamping.

**Recommended starting values:**
- `--vel-limit 0.3` (0.3 m/s) - for UFACTORY Lite 6 the max TCP speed limit is 500 mm/s (see Lite 6 user manual). If exceeded, the robot controller will raise an error and stop.
- `--acc-limit 10.0` (10 m/s²) - for UFACTORY Lite 6 the TCP acceleration limit is 50,000 mm/s² (see Lite 6 user manual).
- `--ang-limit 1.0` (1.0 rad/s) - reasonable starting point for angular velocity.

### Mode Comparison

| Feature | delta-pose | velocity |
|---------|------------|----------|
| Control method | Deltas from origin | Velocities |
| xArm mode | Mode 1 (servo) | Mode 5 (Cartesian velocity) |
| Best for | Precission teleoperation | Smooth continuous motion |

**When to use `delta-pose`:**
- Robot follows your hand movements precisely, very direct-control feeling
- Good for intuitive "move relative to current position" control
- Most common for teleoperation

**When to use `velocity`:**
- Smoother, more natural motions
- Direct control over speed rather than position
- Better for continuous, flowing movements

