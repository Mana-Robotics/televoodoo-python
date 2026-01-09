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

⚠️ This can move a real robot. Keep the workspace clear, use reduced mode / low speeds while tuning, and keep an E-stop accessible.

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

### Real mode (moves the robot)

```bash
python examples/teleop_xarm/teleop_xarm.py \
  --config examples/teleop_xarm/xarm_config.json \
  --ip 192.168.1.100 \
  --enable-motion \
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

