<p align="center">
  <img src="assets/Televoodoo-Python-Banner.png" alt="Televoodoo Viewer screenshot" />
</p>

**Televoodoo Python** enables your Python project to receive real-time **6DoF** pose data from your smartphone (iOS/Android) running the Televoodoo App — perfect for **Robot Teleoperation**, **3D object manipulation**, **VR motion control**, and more.

### The Televoodoo Ecosystem

- **[Televoodoo Python](https://github.com/Mana-Robotics/televoodoo-python)** (this project) — Receive 6DoF poses from the Televoodoo App via WiFi, USB, or BLE, with pose handling, coordinate transforms, and more
- **[Televoodoo App](mailto:hello@mana-robotics.com?subject=Televoodoo%20App%3A%20Request%20for%20Test%20Access)** (iOS, Android) — 6DoF tracking phone app that streams poses at low latency via WiFi, USB, or BLE
- **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** — Cross-platform desktop app for visual testing and config file creation 

## Why Televoodoo?

Traditional 6DoF controllers either limit the motions you can generate (e.g., a 3D mouse) or require expensive hardware (e.g., VR controllers). Meanwhile, we all carry a capable 6DoF controller in our pocket—our phone. Let’s make use of that.

**Televoodoo is optimized for 3 main goals:**

#### 🕹️ Teleoperator UX

- Automatic pairing (app ↔ PC) to current setup via QR code scan
- Fast, reproducible world-frame alignment with an ArUco marker
- Tap-and-hold for deliberate control; release to stop instantly
- Receive **haptic feedback** driven by configurable signals (e.g., force/torque sensors)
- Control recording of motion demonstrations (training data) directly from the phone app.

#### ⚡ Teleoperation quality

- Stable pose and motion tracking (quaternion-based for safety)
- Ultra-low-latency streaming for responsive real-time control
- Optional upsampling and rate limiting to any target frequency

#### 🔌 Effortless integration

- Open-source **Python** client library
- Flexible connectivity via WiFi, USB, or BLE
- Working examples to get you started


## Platform Notes

| Platform | WiFi | USB | BLE |
|----------|----------------|-----|-----|
| **macOS** | ✅ Works out of box | ✅ Configure according to [USB_API](docs/USB_API.md) | ✅ Dependencies are auto-installed |
| **Ubuntu** | ✅ Works out of box | ✅ Configure according to [USB_API](docs/USB_API.md) | ✅ Install `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev` |
| **Windows** | ✅ Works out of box | ☑️ Not yet tested | ❌ Not supported |

## Quick Start

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
# Basic start -> using Wifi, random credentials
televoodoo

# Set connection type (wifi / usb / ble)
televoodoo --connection wifi

# Set static credentials -> You only need to scan it with app once
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

### 3. Connect the Televoodoo App (iOS, Android)

1. **Connect the Televoodoo App** to your **televoodoo-python** instance by scanning the QR code displayed in the terminal.
2. **Align the Coordinate frame** with your **physical setup** by scanning the [ArUco marker](#coordinate-system-setup) (reference frame) attached to the setup ([see details](#coordinate-system-setup)).
3. Start teleoperating using the **Televoodoo App** and receive real-time **6DoF pose data**.





## Physical Setup

### Coordinate System Setup

1. **Print the [ArUco marker](assets/televoodoo-aruco-marker.pdf)** (100% scale, no fit-to-page)
2. **Attach it** to your setup (e.g., somewhere statically linked to world/robot base) — this defines your reference frame
3. **Configure the transform** between marker and your world/robot frame with a [config file](#config-file). e.g. using [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)

> 💡 **Tip for robot teleoperation:** The position offset between marker and robot base doesn't matter — only the **axis orientation** of the reference frame relative to the robot base is crucial for correct motion mapping.

## Examples

Complete examples can be found in `examples/`:

| Example | Description | README |
|---------|-------------|--------|
| [`print_delta_poses/`](examples/print_delta_poses/) | Print pose deltas — ideal for robot teleoperation | [README](examples/print_delta_poses/README.md) |
| [`print_poses/`](examples/print_poses/) | Print absolute poses | [README](examples/print_poses/README.md) |
| [`poll_poses/`](examples/poll_poses/) | Poll latest pose at a fixed rate | [README](examples/poll_poses/README.md) |
| [`measure_frequency/`](examples/measure_frequency/) | Measure pose input frequency | [README](examples/measure_frequency/README.md) |
| [`record_poses/`](examples/record_poses/) | Record poses to a JSON file | [README](examples/record_poses/README.md) |
| [`haptic_feedback/`](examples/haptic_feedback/) | Send haptic feedback with simulated sensor values | [README](examples/haptic_feedback/README.md) |
| [`data_upsampling/`](examples/data_upsampling/) | High-frequency robot control with upsampled poses (200 Hz) | [README](examples/data_upsampling/README.md) |
| [`data_rate_limiting/`](examples/data_rate_limiting/) | Rate-limited pose output (cap frequency) | [README](examples/data_rate_limiting/README.md) |
| [`teleop_xarm/`](examples/teleop_xarm/) | Teleoperate a UFACTORY xArm (end-effector pose control) | [README](examples/teleop_xarm/README.md) |



## Usage
Moved to docs: **[Usage](docs/USAGE.md)**.

## Config File

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
  "upsample_to_frequency_hz": 200.0,
  "rate_limit_frequency_hz": null,
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
| `upsample_to_frequency_hz` | Upsample poses to target frequency (Hz) using linear extrapolation |
| `rate_limit_frequency_hz` | Limit output to maximum frequency (Hz), drops excess poses |

### Creating Config Files

You can create config files manually according to the examples or by configuring, testing and exporting them with Televoodoo Viewer.



### Loading Config Files

```python
from televoodoo import load_config, PoseProvider, Pose, start_televoodoo

# Load config from file
config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    # project specific callback code 
    # ...

# Use credentials from config (if specified), or fall back to random
start_televoodoo(
    callback=on_teleop_event,
    name=config.auth_name,  # None = random
    code=config.auth_code   # None = random
)
```


## Output Formats Explained

Moved to docs: **[Pose Data Format → Output formats](docs/POSE_DATA_FORMAT.md#output-formats-explained)**.


## Advanced Topics

### Upsampling & Rate Limiting

Robot arm controllers often require higher frequency input (100-200 Hz) than the phone can provide (30-60 Hz via WiFi, ~30 Hz via BLE). Televoodoo can upsample pose data using linear extrapolation.

**Via CLI:**
```bash
televoodoo --upsample-hz 200          # Upsample to 200 Hz
televoodoo --rate-limit-hz 30         # Cap output at 30 Hz (no upsampling)
```

**Via Python:**
```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def robot_handler(evt):
    """Called at ~200 Hz with real or extrapolated poses."""
    delta = pose_provider.get_delta(evt)
    if delta:
        robot.send_delta(delta['dx'], delta['dy'], delta['dz'])

# Just pass upsample_to_hz - resampling is handled internally
start_televoodoo(callback=robot_handler, upsample_to_hz=200.0, quiet=True)
```

**Via Config File:**
```json
{
  "upsample_to_frequency_hz": 200.0,
  "rate_limit_frequency_hz": 30.0
}
```

Then load and pass the config:
```python
config = load_config("my_robot_config.json")
start_televoodoo(callback=handler, config=config)
```

| Config Key | CLI Flag | Description |
|------------|----------|-------------|
| `upsample_to_frequency_hz` | `--upsample-hz` | Upsample to target frequency (Hz) using linear extrapolation |
| `rate_limit_frequency_hz` | `--rate-limit-hz` | Cap output at maximum frequency (Hz) |

**Key behaviors:**
- Real poses forwarded immediately (zero added latency)
- Extrapolated poses fill gaps using velocity-based prediction
- **Safety**: Extrapolation stops if no new pose arrives within expected interval (prevents runaway motion if phone disconnects)

> 💡 **Note:** Upsampling uses **regulated mode by default** for consistent timing at the target frequency. This outputs at fixed intervals with ~5ms max latency — ideal for robot controllers. Use `--no-regulated` if you prefer zero latency with irregular timing.

See `examples/data_upsampling/` for a complete example.

### Haptic Feedback

Send haptic feedback to the iOS app based on robot sensor values (e.g., force feedback).
The `send_haptic` function normalizes your sensor values to 0.0–1.0 intensity and transmits
them to the phone, which generates haptic vibrations accordingly.

```python
import threading
import time
from televoodoo import start_televoodoo, send_haptic, PoseProvider, load_config

# --- Force Monitoring Thread ---
# Runs independently to read robot force values and send haptic feedback

def force_monitor_loop():
    """Monitor robot force and send haptic feedback to the iOS app."""
    while True:
        force = robot.get_force()  # e.g., 0–50 Newtons
        # Normalize to 0.0–1.0 and send to iPhone
        send_haptic(force, min_value=0.0, max_value=50.0)
        time.sleep(0.05)  # 20 Hz update rate

# Start force monitoring in background thread
monitor_thread = threading.Thread(target=force_monitor_loop, daemon=True)
monitor_thread.start()

# --- Teleoperation Callback ---
# Receives poses from the iOS app

config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    # Send delta to robot...
    robot.move_relative(delta['dx'], delta['dy'], delta['dz'])

# Start televoodoo (blocks until disconnected)
start_televoodoo(callback=on_teleop_event, quiet=True)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | float | The sensor value to send (e.g., force in Newtons) |
| `min_value` | float | Minimum expected value (maps to intensity 0.0) |
| `max_value` | float | Maximum expected value (maps to intensity 1.0) |

The function is thread-safe and can be called from any thread while `start_televoodoo` is running.

### Quiet Mode

Suppress high-frequency logging (pose events, heartbeat) while still receiving callbacks:

```python
start_televoodoo(callback=handle_pose, quiet=True)
```


## Documentation

For in-depth technical details, see `docs/`:

- **[Usage](docs/USAGE.md)** — Deltas vs absolute, credentials, connection types
- **[Pose Data Format](docs/POSE_DATA_FORMAT.md)** — Coordinate systems, field descriptions, validation
- **[Connection Setup](docs/CONNECTION_SETUP.md)** — QR codes, credentials, multi-device setup
- **[WiFi API](docs/WIFI_API.md)** — UDP protocol, mDNS discovery (default connection)
- **[USB API](docs/USB_API.md)** — USB tethering setup, prerequisites, lowest latency option
- **[BLE Peripheral API](docs/BLE_API.md)** — Service UUIDs, characteristics, protocol details


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, BLE internals, and how to contribute.


## Maintainer

Developed with ❤️ for 🤖 by [Mana Robotics](https://www.mana-robotics.com).

## License

MIT License — see [LICENSE](LICENSE) for details.
