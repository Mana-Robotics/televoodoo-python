# Usage

This guide explains how to consume Televoodoo pose events in your application, including delta vs absolute poses, CLI options, and quiet mode.

## Delta vs Absolute Poses

### Option A: Using Pose Deltas (Recommended for Robot Teleoperation)

> ✅ **Recommended!** Deltas always start at 0 when tracking begins. Pause tracking, reposition yourself, then resume — no jumps in robot motion.

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

## CLI Options

### Basic Usage

```bash
# Start with WiFi (default), random credentials
televoodoo

# Set connection type
televoodoo --connection wifi   # WiFi (default)
televoodoo --connection usb    # USB tethering (lowest latency)
televoodoo --connection ble    # Bluetooth

# Set static credentials (scan once, reuse)
televoodoo --name myrobot --code ABC123

# Combine options
televoodoo --connection usb --name myrobot --code ABC123 --quiet
```

### Available Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--connection` | Connection type: `wifi`, `usb`, `ble` | `wifi` |
| `--name` | Peripheral/server name | Random `voodooXX` |
| `--code` | 6-character auth code | Random alphanumeric |
| `--quiet` | Suppress high-frequency logging | `False` |
| `--upsample-hz` | Upsample to target frequency (Hz) | None |
| `--rate-limit-hz` | Cap output at maximum frequency (Hz) | None |

## Python API Options

```python
from televoodoo import start_televoodoo

start_televoodoo(
    callback=handle_pose,           # Required: your pose handler
    connection="wifi",              # "wifi" (default), "usb", or "ble"
    name="myrobot",                 # Custom name (None = random)
    code="ABC123",                  # Custom code (None = random)
    quiet=True,                     # Suppress logging
    upsample_to_hz=200.0,           # Upsample frequency
    rate_limit_hz=30.0,             # Rate limit frequency
    config=config                   # Config object from load_config()
)
```

## Quiet Mode

Suppress high-frequency logging (pose events, heartbeat) while still receiving callbacks. Useful for production and high-frequency applications.

**Via CLI:**

```bash
televoodoo --quiet
```

**Via Python:**

```python
start_televoodoo(callback=handle_pose, quiet=True)
```

When quiet mode is enabled:
- Connection/disconnection events are still logged
- Error messages are still shown
- Pose and heartbeat logs are suppressed

## Connection Types

| Type | Latency | Use Case |
|------|---------|----------|
| **WiFi** (default) | ~16ms | General use, cross-platform |
| **USB** | ~5-10ms | Lowest latency, force feedback loops |
| **BLE** | ~32ms effective | When WiFi/USB unavailable |

> ⚠️ **USB Connection** requires **opposite** setup for iOS vs Android. See [USB API](USB_API.md) for details.

## See Also

- **[Configuration](CONFIGURATION.md)** — Config file format and options
- **[Connection & Authentication](CONNECTION_AUTHENTICATION.md)** — Connection setup and troubleshooting
- **[Data Format](DATA_FORMAT.md)** — Pose field descriptions
- **[Output Formats](OUTPUT_FORMATS.md)** — Available output format options
