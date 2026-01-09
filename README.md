# Televoodoo Python

**Televoodoo Python** enables your Python project to receive real-time **6DoF** pose data from any smartphone running the Televoodoo App — perfect for **Robot Teleoperation**, **3D object manipulation**, **VR motion control**, and more.

### The Televoodoo Ecosystem

- **[Televoodoo Python](https://github.com/Mana-Robotics/televoodoo-python)** (this project) — Create BLE peripherals for the Televoodoo App to connect to, with pose handling, coordinate transforms, and more
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

```python
from televoodoo.ble import start_peripheral

def my_pose_handler(pose_data):
    if pose_data.get('movement_start'):
        print("New movement started — origin reset")
    print(f"Position: ({pose_data['x']:.3f}, {pose_data['y']:.3f}, {pose_data['z']:.3f})")
    # Control your robot, 3D object, etc.

start_peripheral(callback=my_pose_handler)
```

### 3. Connect with Televoodoo app (iOS, Android)

1. A QR code appears in your terminal
2. Use **Televoodoo App** to scan the QR code and the [ArUco marker](#coordinate-system-setup) (reference frame), then follow further on-screen instructions
5. Callback receives real-time 6DoF poses




## How It Works

### Coordinate System Setup

1. **Print the [ArUco marker](assets/televoodoo-aruco-marker.pdf)** (100% scale, no fit-to-page)
2. **Attach it** to your setup (e.g., somewhere statically linked to world/robot base) — this defines your reference frame
3. **Configure the transform** between marker and your world/robot frame with a config file. e.g. using [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)

> **For robot control**: Absolute position doesn't matter — only the **axis orientation** (rot_x, rot_y, rot_z) of the reference frame relative to the robot's base is crucial to ensure phone movements correctly map to robot movements.

### Pose Data Format

Your callback receives a dictionary with:

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


## Usage Examples

Complete examples are in `examples/`:

| Example | Description |
|---------|-------------|
| `pose_logger/` | Simple pose logging to console |
| `pose_recording/` | Record and replay pose streams |
| `pose_frequency/` | Analyze pose update rates |
| `output_poller/` | Poll output from config file |

### Basic Pose Logging

```python
from televoodoo.ble import start_peripheral

def handle_pose(pose_data):
    if pose_data.get('movement_start'):
        print("🎯 New movement origin set")
    print(f"📍 x={pose_data['x']:.3f} y={pose_data['y']:.3f} z={pose_data['z']:.3f}")

start_peripheral(callback=handle_pose)
```

Static credentials let you reconnect without re-scanning the QR code.

### Robot Control Example

```python
from televoodoo.ble import start_peripheral

class RobotController:
    def __init__(self):
        self.origin = None
    
    def handle_pose(self, pose_data):
        # movement_start=True: user started a new movement, reset origin
        if pose_data.get('movement_start'):
            self.origin = pose_data
            print("🎯 New movement origin — robot stays in place")
            return
        
        if self.origin is None:
            return  # Wait for first movement_start
        
        # Calculate delta from origin (robot only moves by relative amount)
        dx = pose_data['x'] - self.origin['x']
        dy = pose_data['y'] - self.origin['y']
        dz = pose_data['z'] - self.origin['z']
        
        # Send delta to robot
        self.move_robot_relative(dx, dy, dz)

controller = RobotController()
start_peripheral(callback=controller.handle_pose)
```

### Using the Pose Class

```python
from televoodoo.pose import Pose
from televoodoo.ble import start_peripheral

def handle_pose(pose_data):
    pose = Pose.from_dict(pose_data)
    
    if not pose.is_active:
        return
    
    position = pose.position          # numpy array [x, y, z]
    quaternion = pose.quaternion      # [qx, qy, qz, qw]
    matrix = pose.to_matrix()         # 4x4 homogeneous transform

start_peripheral(callback=handle_pose)
```


## Authentication Credentials

The BLE peripheral provides 2 options for the BLE Authentication credentials:

**Random** (default): New credentials each launch — good for quick testing  
**Static**: Same credentials every time — good for ongoing projects, development, RL demonstration


### Random Credentials

| Flag | Description | Default |
|------|-------------|---------|
| `--name` | BLE peripheral name | Random `voodooXX` |
| `--code` | 6-character auth code | Random alphanumeric |


### Static Credentials

Option 1: Set via CLI flag
```bash
televoodoo --name myrobot --code ABC123
```

Option 2: Set in code
```python
start_peripheral(callback=handle_pose, name="myrobot", code="ABC123")
```

Option 3: Set within [config file](#config-files)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **QR code not scanning** | Increase terminal font size, ensure good lighting |
| **Device not found** | Check Bluetooth is on, devices within ~10m range |
| **Connection drops** | Reduce distance, check for BLE interference |
| **No pose data** | Ensure phone scanned ArUco marker at least once and you started tracking in the phone app (keep finger pressed down), check BLE connection |
| **Linux: Bluetooth issues** | Run `sudo systemctl status bluetooth`, check BlueZ logs |



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
- See example configs in `examples/output_poller/`

### Loading Config Files

```python
from televoodoo import load_config, PoseProvider, start_televoodoo

# Load config from file
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    # Get pose delta directly from event
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    # Access delta data for robot control
    print(f"Delta: dx={delta['dx']:.3f} dy={delta['dy']:.3f} dz={delta['dz']:.3f}")
    print(f"Rotation: rx={delta['rx']:.3f} ry={delta['ry']:.3f} rz={delta['rz']:.3f}")

# Use credentials from config (if specified), or fall back to random
start_televoodoo(
    callback=on_teleop_event,
    name=config.auth_name,  # None = random
    code=config.auth_code   # None = random
)
```

### Command Line Usage

```bash
# With config file
python examples/pose_logger/pose_logger.py --config my_config.json

python examples/output_poller/output_poller.py --config voodoo_settings.json --hz 10
```

### Output Formats Explained

| Format | Description |
|--------|-------------|
| `absolute_input` | Raw pose from phone (in marker frame) |
| `delta_input` | Change since first pose (in marker frame) |
| `absolute_transformed` | Pose transformed to target frame |
| `delta_transformed` | Delta transformed to target frame — **best for robot control** |


## Advanced Topics

### Rate Limiting

The Televoodoo App streams poses (~60 Hz limited by iOS ARKit). Throttle if needed:

```python
import time

class ThrottledHandler:
    def __init__(self, max_hz=30):
        self.min_interval = 1.0 / max_hz
        self.last_time = 0
    
    def handle_pose(self, pose_data):
        now = time.time()
        if now - self.last_time < self.min_interval:
            return
        self.last_time = now
        # Process pose...
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
