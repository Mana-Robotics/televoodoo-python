# Televoodoo Python - Usage

This page explains how to consume Televoodoo pose events in your application (delta vs absolute), and how to set credentials and connection types.

## Option A: Using Pose Deltas

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

## Option B: Using Absolute Poses

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

## Pose Format

`PoseProvider.get_absolute()` returns a transformed pose:

```python
{
    "movement_start": True,  # New movement origin (for delta calculation)
    "x": 0.15,               # Position in meters (transformed)
    "y": 0.20,
    "z": -0.10,
    "qx": 0.01234,           # Quaternion (preferred for 3D math)
    "qy": -0.56789,
    "qz": 0.12345,
    "qw": 0.81234,
    "rx": 0.26,              # Rotation vector (radians) — always included
    "ry": -0.52,
    "rz": 0.09
}
```

| Field | Type | Description |
|-------|------|-------------|
| `movement_start` | bool | `True` = new origin for delta calculation (see below) |
| `x`, `y`, `z` | float | Position relative to ArUco marker (meters) |
| `qx`, `qy`, `qz`, `qw` | float | Quaternion — use this for robust 3D calculations |
| `rx`, `ry`, `rz` | float | Rotation vector (radians) — axis-angle representation |

> **Understanding `movement_start`**: When `true`, this pose becomes the new origin for calculating deltas. This allows you to reposition the phone/controller while not actively controlling, then start a new movement from a different physical position — the robot end effector stays in place and only applies relative deltas from the new origin.

## Authentication Credentials

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

Option 3: Set within a config file (see the main README’s “Config File” section):
- [Config File](../README.md#config-file)

## Connection Types

You can specify the connection backend:

```python
start_televoodoo(
    callback=handle_pose,
    connection="auto"  # Options: "auto" (default), "wifi", "usb", "ble"
)
```

- **`"auto"`** (default): Uses WiFi — recommended for best latency and cross-platform compatibility
- **`"wifi"`**: UDP-based connection over local network (~60Hz consistent frequency / ~16ms latency)
- **`"usb"`**: USB tethering connection (~60Hz / ~5-10ms latency) — lowest latency, requires USB cable
- **`"ble"`**: Bluetooth Low Energy connection (platform-specific, subject to connection interval batching (e.g. iOS), resulting in effectively only ~30 Hz of update frequency / 32ms latency)

Or via CLI:

```bash
televoodoo --connection wifi   # WiFi (default)
televoodoo --connection usb    # USB tethering (lowest latency)
televoodoo --connection ble    # Bluetooth
```

> ⚠️ **USB Connection** requires **opposite** setup for iOS vs Android:
> - **Android**: Enable USB Tethering on phone, **disable** Mac Internet Sharing
> - **iOS on macOS**: Enable **macOS Internet Sharing** (share WiFi to "iPhone USB"), **disable** iPhone Personal Hotspot
> 
> See [USB API docs](USB_API.md) for details.

## See also

- [Connection setup](CONNECTION_SETUP.md)
- [Pose data format](POSE_DATA_FORMAT.md)
