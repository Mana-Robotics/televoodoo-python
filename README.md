<p align="center">
  <img src="assets/Televoodoo-Python-Banner.png" alt="Televoodoo Viewer screenshot" />
</p>

**Televoodoo Python** enables your Python project to receive real-time **6DoF** pose data from any smartphone running the Televoodoo App — perfect for **Robot Teleoperation**, **3D object manipulation**, **VR motion control**, and more.

### The Televoodoo Ecosystem

- **[Televoodoo Python](https://github.com/Mana-Robotics/televoodoo-python)** (this project) — Create BLE services for the Televoodoo App to connect to, with pose handling, coordinate transforms, and more
- **[Televoodoo App](mailto:hello@mana-robotics.com?subject=Televoodoo%20App%3A%20Request%20for%20Test%20Access)** (iOS, Android) — 6DoF tracking phone app that streams poses at low latency via BLE
- **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** — Cross-platform desktop app for visual testing and config file creation 



## Quick Start

### Platform Notes

| Platform | Requirements |
|----------|-------------|
| **macOS** | PyObjC frameworks (auto-installed via requirements.txt) |
| **Ubuntu** | BlueZ + system headers: `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev` |


### 1. Install

#### Option A: Python venv (tested)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .
```

#### Option B: Conda

```bash
conda create -n televoodoo python -y
conda activate televoodoo
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .
```

### 2. Run

**With CLI**

```bash
# Start with random credentials (QR code will be displayed)
televoodoo

# Start with static credentials
televoodoo --name myrobot --code ABC123
```

**Or as Python App**

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

# Load config (optional - uses defaults if None)
config = load_config()
pose_provider = PoseProvider(config)

def my_pose_handler(evt):
    # For robot teleoperation, use get_delta():
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return  # Not a pose event or no origin set yet
    
    if delta['movement_start']:
        print("New movement started — origin reset")
    print(f"Position delta: ({delta['dx']:.3f}, {delta['dy']:.3f}, {delta['dz']:.3f})")
    print(f"Rotation delta (rad): ({delta['rx']:.3f}, {delta['ry']:.3f}, {delta['rz']:.3f})")
    # Control your robot, 3D object, etc.

start_televoodoo(callback=my_pose_handler)
```

### 3. Connect with Televoodoo app (iOS, Android)

1. A QR code appears in your terminal
2. Use **Televoodoo App** to scan the QR code and the [ArUco marker](#coordinate-system-setup) (reference frame), then follow further on-screen instructions
5. Callback receives real-time 6DoF poses




## Physical Setup

### Coordinate System Setup

1. **Print the [ArUco marker](assets/televoodoo-aruco-marker.pdf)** (100% scale, no fit-to-page)
2. **Attach it** to your setup (e.g., somewhere statically linked to world/robot base) — this defines your reference frame
3. **Configure the transform** between marker and your world/robot frame with a config file. e.g. using [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)

> 💡 **Tip for robot teleoperation:** The position offset between marker and robot base doesn't matter — only the **axis orientation** of the reference frame relative to the robot base is crucial for correct motion mapping.

## Examples

Complete examples can be found in `examples/`:

| Example | Description |
|---------|-------------|
| `print_delta_poses/` | Print pose deltas — ideal for robot teleoperation |
| `print_poses/` | Print absolute poses |
| `poll_poses/` | Poll latest pose at a fixed rate |
| `measure_frequency/` | Measure pose input frequency |
| `record_poses/` | Record poses to a JSON file |



## Usage




### Option A: Using Delta Poses

> ✅ **Recommended for Robot Teleoperation!** Deltas always start at 0 when tracking begins. Pause tracking, reposition yourself, then resume — no jumps in robot motion.


Use `PoseProvider.get_delta()` to get transformed deltas directly from events:

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

# Load config (optional - uses defaults if None)
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def my_handler(evt):
    # Get delta directly from event
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return  # Not a pose event or no origin set yet
    
    # Access delta data for robot control
    print(f"Position delta: dx={delta['dx']:.3f} dy={delta['dy']:.3f} dz={delta['dz']:.3f}")
    print(f"Rotation delta (rad): rx={delta['rx']:.3f} ry={delta['ry']:.3f} rz={delta['rz']:.3f}")
    print(f"Rotation delta (quaternion): ({delta['dqx']:.3f}, {delta['dqy']:.3f}, {delta['dqz']:.3f}, {delta['dqw']:.3f})")
    
    # Send delta to robot
    # robot.move_relative(delta['dx'], delta['dy'], delta['dz'])

start_televoodoo(callback=my_handler)
```

The delta is calculated relative to the pose where `movement_start=True`, making it perfect for robot teleoperation where you want relative movements.

### Option B: Using Absolute Poses

> ⚠️ **Not recommended for robot teleoperation.** Absolute poses are non-zero from the start and will jump when tracking is paused and resumed.

Use `PoseProvider.get_absolute()` to get transformed absolute poses:

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

# Load config (optional - uses defaults if None)
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def my_handler(evt):
    # Get absolute pose from event
    pose = pose_provider.get_absolute(evt)
    if pose is None:
        return  # Not a pose event
    
    # Access pose data
    print(f"Position: x={pose['x']:.3f} y={pose['y']:.3f} z={pose['z']:.3f}")
    print(f"Quaternion: ({pose['qx']:.3f}, {pose['qy']:.3f}, {pose['qz']:.3f}, {pose['qw']:.3f})")

start_televoodoo(callback=my_handler)
```

### Pose Format

The `Pose` object contains:

```python
{
    "movement_start": True,  # New movement origin (for delta calculation)
    "x": 0.15,               # Position in meters
    "y": 0.20,
    "z": -0.10,
    "x_rot": 15.0,           # Euler angles in degrees
    "y_rot": -30.0,
    "z_rot": 5.0,
    "qx": 0.01234,           # Quaternion (preferred for 3D math)
    "qy": -0.56789,
    "qz": 0.12345,
    "qw": 0.81234
}
```

| Field | Type | Description |
|-------|------|-------------|
| `movement_start` | bool | `True` = new origin for delta calculation (see below) |
| `x`, `y`, `z` | float | Position relative to ArUco marker (meters) |
| `x_rot`, `y_rot`, `z_rot` | float | Euler angles (degrees) — convenience only |
| `qx`, `qy`, `qz`, `qw` | float | Quaternion — use this for robust 3D calculations |

> **Understanding `movement_start`**: When `true`, this pose becomes the new origin for calculating deltas. This allows you to reposition the phone/controller while not actively controlling, then start a new movement from a different physical position — the robot end effector stays in place and only applies relative deltas from the new origin.

### Authentication Credentials

Televoodoo provides 2 options for connection credentials:
- **Random** (default): New credentials each launch — good for quick testing  
- **Static**: Same credentials every time — good for ongoing projects, development, RL demonstration


**Random Credentials**

| Flag | Description | Default |
|------|-------------|---------|
| `--name` | Peripheral/server name | Random `voodooXX` |
| `--code` | 6-character auth code | Random alphanumeric |


**Static Credentials**

Option 1: Set via CLI flag
```bash
televoodoo --name myrobot --code ABC123
```

Option 2: Set in code
```python
from televoodoo import start_televoodoo

start_televoodoo(callback=handle_pose, name="myrobot", code="ABC123")
```

Option 3: Set within [config file](#config-files)

### Connection Types

You can specify the connection backend:

```python
start_televoodoo(
    callback=handle_pose,
    connection="auto"  # Options: "auto" (default), "ble"
)
```

- **`"auto"`** (default): Automatically detects the best available connection type (currently defaults to BLE)
- **`"ble"`**: Force Bluetooth Low Energy connection

## Config Files

Config files define how poses are transformed from the ArUco marker frame to your target coordinate system (robot base, world frame, etc.), what output formats to include, and optionally BLE credentials.

### File Format & Location

- **Format**: JSON (`.json` extension recommended)
- **Default search paths** (in order):
  1. Current working directory
  2. Directory of your Python script
  3. Televoodoo module directory

### Config File Format

```json
{
  "authCredentials": {
    "name": "myrobot",
    "code": "ABC123"
  },
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

| Section | Purpose |
|---------|---------|
| `authCredentials` | Connection credentials: `name` (peripheral name) and `code` (6-char auth code) |
| `includeFormats` | Which pose formats to output (raw input, deltas, transformed) |
| `includeOrientation` | Include quaternion, Euler radians, and/or Euler degrees |
| `scale` | Scale factor applied to positions |
| `outputAxes` | Axis multipliers (use `-1` to flip an axis) |
| `targetFrameDegrees` | 6DoF transform: marker → target frame (position in meters, rotation in degrees) |

### Creating Config Files

**Option 1: Use [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** (recommended)
- Visually configure transforms with real-time 3D preview
- Export as JSON config file

**Option 2: Create manually**
- Copy the template above and adjust values

### Loading Config Files

```python
from televoodoo import load_config, PoseProvider, Pose, start_televoodoo

# Load config from file
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    # For robot teleoperation: use get_delta()
    delta = pose_provider.get_delta(evt)
    if delta is not None:
        print(f"Delta: dx={delta['dx']:.3f} dy={delta['dy']:.3f} dz={delta['dz']:.3f}")
        print(f"Rotation: rx={delta['rx']:.3f} ry={delta['ry']:.3f} rz={delta['rz']:.3f}")
        return
    
    # For absolute poses: use get_absolute()
    pose = pose_provider.get_absolute(evt)
    if pose is not None:
        print(f"Position: x={pose['x']:.3f} y={pose['y']:.3f} z={pose['z']:.3f}")

# Use credentials from config (if specified), or fall back to random
start_televoodoo(
    callback=on_teleop_event,
    name=config.auth_name,  # None = random
    code=config.auth_code   # None = random
)
```


## Output Formats Explained

| Format | Description |
|--------|-------------|
| `absolute_input` | Raw pose from phone (in marker frame) |
| `delta_input` | Change since first pose (in marker frame) |
| `absolute_transformed` | Pose transformed to target frame |
| `delta_transformed` | Delta transformed to target frame — **best for robot control** |


## Advanced Topics

### Quiet Mode

Suppress high-frequency logging (pose events, heartbeat) while still receiving callbacks:

```python
start_televoodoo(callback=handle_pose, quiet=True)
```


## Documentation

For in-depth technical details, see `docs/`:

- **[Pose Data Format](docs/POSE_DATA_FORMAT.md)** — Coordinate systems, field descriptions, validation
- **[Connection Setup](docs/CONNECTION_SETUP.md)** — QR codes, credentials, multi-device setup
- **[BLE Peripheral API](docs/BLE_PERIPHERAL_API.md)** — Service UUIDs, characteristics, protocol details


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, BLE internals, and how to contribute.


## Maintainer

Developed with ❤️ for 🤖 by [Mana Robotics](https://www.mana-robotics.com).

## License

MIT License — see [LICENSE](LICENSE) for details.
