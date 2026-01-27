<p align="center">
  <img src="assets/Televoodoo-Python-Banner.png" alt="Televoodoo Viewer screenshot" />
</p>

**Televoodoo Python** enables your Python project to receive real-time **6DoF** pose data from your smartphone (iOS/Android) running the Televoodoo App — perfect for **Robot Teleoperation**, **3D object manipulation**, **VR motion control**, and more.

### The Televoodoo Ecosystem

- **[Televoodoo Python](https://github.com/Mana-Robotics/televoodoo-python)** (this project) — Receive 6DoF poses from the Televoodoo App via WiFi, USB, or BLE, with pose handling, coordinate transforms, and more
- **[Televoodoo App](mailto:hello@mana-robotics.com?subject=Televoodoo%20App%3A%20Request%20for%20Test%20Access)** (iOS, Android) — 6DoF tracking phone app that streams poses at low latency via WiFi, USB, or BLE
- **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** — Cross-platform desktop app for visual testing and config file creation 


## ⚠️ **Legal & Safety Disclaimer**
 

> Televoodoo is a software tool intended **for research and development purposes only**. It is **not production-ready** and **not safety-certified**. Errors in pose tracking, perception, planning, and robot control may occur and can lead to unexpected or unsafe behavior. 
>
> The software is provided **“as is”**, without warranty of any kind. The authors and contributors assume **no responsibility or liability** for any damages, including material damage, personal injury, or loss of life resulting from the use or misuse of this software. 
>
>Use of Televoodoo requires a **trained and responsible operator** with experience in robotics programming and system integration. The user is solely responsible for performing a proper **risk assessment** and ensuring a safe overall system design. 
>
>Televoodoo must **only be used with collaborative robots (cobots)** equipped with collision detection and safety features.  **DO NOT USE with industrial robot arms.**


## Why Televoodoo?

Traditional 6DoF controllers either limit the motions you can generate (e.g., a 3D mouse) or require expensive hardware (e.g., VR controllers). Meanwhile, we all carry a capable 6DoF controller in our pocket—our phone. Let's make use of that.

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
| **macOS** | ✅ Works out of box | ✅ Configure according to [USB API](docs/USB_API.md) | ✅ Dependencies are auto-installed |
| **Ubuntu** | ✅ Works out of box | ✅ Configure according to [USB API](docs/USB_API.md) | ✅ Install `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev` |
| **Windows** | ✅ Works out of box | ✅ Configure according to [USB API](docs/USB_API.md) | ❌ Not supported |

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
televoodoo --name myvoodoo --code ABC123
```

**Or as Python App**

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

# Load config with control mode (delta-pose, velocity, or absolute-pose)
config = load_config("my_config.json")
pose_provider = PoseProvider(config)

def my_pose_handler(evt):
    # For robot teleoperation, use get_delta() or get_velocity()
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
2. **Align the Coordinate frame** with your **physical setup** by scanning the [ArUco marker](assets/televoodoo-aruco-marker.pdf) (reference frame) attached to the setup.
3. Start teleoperating using the **Televoodoo App** and receive real-time **6DoF pose data**.


## Physical Setup

### Coordinate System Setup

1. **Print the [ArUco marker](assets/televoodoo-aruco-marker.pdf)** (100% scale, no fit-to-page)
2. **Attach it** to your setup (e.g., somewhere statically linked to world/robot base) — this defines your reference frame
3. **Configure the transform** between marker and your world/robot frame with a [config file](docs/CONFIGURATION.md), e.g. using [Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)

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


## Documentation

| Document | Description |
|----------|-------------|
| **[Usage](docs/USAGE.md)** | PoseProvider API methods, CLI options, quiet mode |
| **[Configuration](docs/CONFIGURATION.md)** | Config file format, loading, and all available options |
| **[Connection & Authentication](docs/CONNECTION_AUTHENTICATION.md)** | Connection setup, QR codes, credentials, troubleshooting |
| **[Data Format](docs/DATA_FORMAT.md)** | Coordinate systems, pose fields, binary protocol |
| **[Output Formats](docs/OUTPUT_FORMATS.md)** | Available output formats and how to enable them |
| **[Haptic Feedback](docs/HAPTIC_FEEDBACK.md)** | Sending haptic feedback to the phone app |
| **[Upsampling & Rate Limiting](docs/UPSAMPLING_RATE_LIMITING.md)** | ⚠️ experimental: High-frequency control and rate limiting |

### Transport-Specific Documentation

| Document | Description |
|----------|-------------|
| **[WiFi API](docs/WIFI_API.md)** | TCP protocol, UDP beacon discovery (default connection) |
| **[USB API](docs/USB_API.md)** | USB tethering setup, lowest latency option |
| **[BLE API](docs/BLE_API.md)** | Bluetooth Low Energy service and protocol |


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, BLE internals, and how to contribute.


## Maintainer

Developed with ❤️ for 🤖 by [Mana Robotics](https://www.mana-robotics.com).

## License

Apache 2.0 License — see [LICENSE](LICENSE) for details.
