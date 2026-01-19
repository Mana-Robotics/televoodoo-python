# Teleop an xArm 5/6/7 or Lite 6 Robot Arm

Teleoperate a UFACTORY xArm end-effector pose using a smartphone as a 6DoF controller.

This example:
- Receives phone pose samples (position + quaternion orientation)
- Applies Televoodoo's `OutputConfig` transforms (axes / target frame)
- Streams `set_servo_cartesian_aa` targets to the robot

## Requirements

- **xArm SDK**: `pip install xarm-python-sdk`
- **Robot**: UFACTORY xArm / Lite6 reachable via IP on your LAN

## Safety

⚠️ This can move a real robot. Configure speed and acceleration limits, keep the workspace clear and keep an E-stop accessible.

## Configuration

Copy `xarm_config.json` and adapt it for your setup:

```json
{
  "authCredentials": { "name": "myrobot", "code": "ABC123" },
  "scale": 1000,
  "outputAxes": { "x": 1, "y": 1, "z": 1 },
  "targetFrameDegrees": {
    "x": 0, "y": 0, "z": 0,
    "x_rot_deg": 0, "y_rot_deg": 0, "z_rot_deg": 0
  }
}
```

### Units

- Televoodoo outputs positions in **meters**
- xArm expects positions in **millimeters**
- Set `"scale": 1000` to convert meters → mm

### Target Frame

Use `targetFrameDegrees` to align the ArUco reference marker (to be scanned with Televooodoo App) with your robot. For example, a ceiling-mounted robot might need `"y_rot_deg": 180`.

## Run

### Dry-run (prints targets, does not move robot)

```bash
python examples/teleop_xarm/teleop_xarm.py --dry-run
```

### Dry-run with custom config (prints targets, does not move robot)

```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --dry-run
```


### Real mode with config file

Note: Velocity and speed limits are loaded from the config file. Make sure they are set correctly!


```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --ip 192.168.1.100 \
  --enable-motion \
```


### Real mode with custom motion limits -> WARNING ⚠️

```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --ip 192.168.1.100 \
  --enable-motion \
  --vel-limit 0.5 \
  --acc-limit 50.0
```

## Output (dry-run)

Prints pose deltas, which in Real Mode are used to control the robot's end effector.

```
Using config: examples/teleop_xarm/xarm_config.json
target: [300.5, 120.3, 450.2, 0.01, -0.02, 0.15]
target: [301.2, 121.0, 449.8, 0.02, -0.01, 0.16]
...
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to Televoodoo config JSON |
| `--ip ADDRESS` | xArm IP address (required with `--enable-motion`) |
| `--enable-motion` | Enable robot motion (dangerous) |
| `--dry-run` | Print poses only, don't connect to robot (default) |
| `--vel-limit FLOAT` | Maximum velocity in m/s (clamps fast movements) |
| `--acc-limit FLOAT` | Maximum acceleration in m/s² (symmetric, limits jerk) |

### Motion Limiting

The `--vel-limit` and `--acc-limit` flags provide safety limits for robot motion:

- **Velocity limit**: Clamps position changes to not exceed the specified speed
- **Acceleration limit**: Limits how quickly speed can change (applies to both acceleration and deceleration)

When limits are applied, a warning is logged and the pose data includes `"limited": true`.

**Recommended starting values:**
- `--vel-limit 0.3` (0.3 m/s) - for UFACTORY Lite 6 the max TCP speed limit is 500 mm/s (see Lite 6 user manual). If exceeded, the robot controller will raise an error and stop.
- `--acc-limit 10.0` (10 m/s²) - for UFACTORY Lite 6 the TCP acceleration limit is 50.000 mm/s (see Lite 6 user manual).

