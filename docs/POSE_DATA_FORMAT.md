# Televoodoo Python - Pose Data Format

## Overview

Televoodoo Python receives 6DoF pose tracking data from the Televoodoo App via Bluetooth Low Energy (BLE). This document describes the pose data format your callback function will receive, coordinate systems, and how to work with the data in your applications.

## Coordinate System

### Reference Frame
- All pose values are expressed relative to a **reference coordinate system**
- The reference frame (coordinate system) is established by an **[ArUco marker](../assets/televoodoo-aruco-marker.pdf)** which is scanned by the Televoodoo App and used to transform the phones random coordinate system into the reference frame, which again is statically linked to e.g. your robot base
- The **[ArUco marker](../assets/televoodoo-aruco-marker.pdf)** has to be printed (print settings: 100% original size) and then attached to the real world (static).
- The phone's pose is tracked in 6 degrees of freedom (6DoF) relative to this marker
- The **6DoF relationship between the reference frame (marker) and your world frame / robot base frame / ...** (position offset in x,y,z, rotation offset rot_x, rot_y, rot_z) should be set in a config file. -> **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** is a cross-platform desktop app that allows easy definition and visual testing of config files
- **For robot control**: Only relative movements (deltas) in the world are typically relevant, not absolute positions. However, the **relative orientation of the coordinate axes** (rot_x, rot_y, rot_z) is crucial to ensure phone movements map correctly to robot movements. So please set the correct orientation config

### Coordinate Convention
- **X-axis**: Typically horizontal (right is positive)
- **Y-axis**: Typically depth (forward is positive)
- **Z-axis**: Typically vertical (up is positive)
- **Units**: Meters for position, degrees for Euler angles
- **Quaternions**: Normalized (magnitude = 1.0)

> **Note**: The specific orientation depends on how the ArUco marker is positioned. Use the Televoodoo Viewer app to visually verify and configure your coordinate system.

## JSON Payload Format

Your callback function receives pose data as a Python dictionary with the following structure:

```python
{
  "movement_start": True,  # or False
  "x": 0.0,
  "y": 0.0,
  "z": 0.0,
  "x_rot": 0.0,
  "y_rot": 0.0,
  "z_rot": 0.0,
  "qx": 0.0,
  "qy": 0.0,
  "qz": 0.0,
  "qw": 1.0
}
```

## Field Descriptions

### Movement Control
- **movement_start** (bool): Signals the start of a new movement — sets this pose as the new origin for delta calculations
  - `True`: New movement beginning — use this pose as the origin for calculating deltas
  - `False`: Continuous movement — calculate deltas from the previously set origin

> **Use case**: Allows the user to reposition the phone/controller while not actively controlling, then start a new movement from a different physical position. The robot end effector stays in place and only applies relative deltas from the new origin.

### Position (Translation)
- **x** (float): Position along X-axis in meters
- **y** (float): Position along Y-axis in meters
- **z** (float): Position along Z-axis in meters

### Rotation (Euler Angles)
- **x_rot** (float): Rotation around X-axis in degrees (pitch)
- **y_rot** (float): Rotation around Y-axis in degrees (yaw)
- **z_rot** (float): Rotation around Z-axis in degrees (roll)

> **Note**: Euler angles are provided for convenience but may suffer from gimbal lock. For robust 3D calculations, use the quaternion representation.

### Rotation (Quaternion)
- **qx** (float): Quaternion X component
- **qy** (float): Quaternion Y component
- **qz** (float): Quaternion Z component
- **qw** (float): Quaternion W component

> **Note**: Quaternions are the preferred representation for 3D rotations as they avoid gimbal lock and interpolate smoothly.

## Example Payloads

### New Movement Start (Origin Reset)

```python
{
  "movement_start": True,   # This pose becomes the new delta origin
  "x": 0.15,
  "y": 0.20,
  "z": -0.10,
  "x_rot": 15.0,
  "y_rot": -30.0,
  "z_rot": 5.0,
  "qx": 0.01234,
  "qy": -0.56789,
  "qz": 0.12345,
  "qw": 0.81234
}
```

### Continuous Movement

```python
{
  "movement_start": False,  # Calculate delta from previous origin
  "x": 0.18,                # Moved 3cm from origin
  "y": 0.22,
  "z": -0.08,
  "x_rot": 18.0,
  "y_rot": -28.0,
  "z_rot": 6.0,
  "qx": 0.02345,
  "qy": -0.55678,
  "qz": 0.13456,
  "qw": 0.80123
}
```

## Using Pose Data in Your Application

### Basic Example (Delta Poses for Robot Control)

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

def handle_pose(evt):
    """Process incoming pose data"""
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    # Check if this is a new movement start (origin reset)
    if delta['movement_start']:
        print("🎯 New movement started — origin reset")
    
    # Extract position delta
    dx, dy, dz = delta['dx'], delta['dy'], delta['dz']
    
    # Extract rotation delta (as rotation vector, radians)
    rx, ry, rz = delta['rx'], delta['ry'], delta['rz']
    
    print(f"📍 Position delta: ({dx:.3f}, {dy:.3f}, {dz:.3f}) m")
    print(f"🔄 Rotation delta: ({rx:.3f}, {ry:.3f}, {rz:.3f}) rad")

start_televoodoo(callback=handle_pose)
```

### Using Absolute Poses

For applications like digital twins where you need absolute position:

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

def handle_pose(evt):
    pose = pose_provider.get_absolute(evt)
    if pose is None:
        return
    
    # Access position (transformed per config)
    x, y, z = pose['x'], pose['y'], pose['z']
    
    # Access quaternion
    qx, qy, qz, qw = pose['qx'], pose['qy'], pose['qz'], pose['qw']
    
    print(f"Position: ({x:.3f}, {y:.3f}, {z:.3f})")
    print(f"Quaternion: ({qx:.3f}, {qy:.3f}, {qz:.3f}, {qw:.3f})")

start_televoodoo(callback=handle_pose)
```

### Coordinate Transforms

Transform poses from the reference frame to your application's coordinate system using a config file:

```python
from televoodoo import PoseProvider, load_config

# Load config with targetFrame to define marker → robot transform
config = load_config("robot_config.json")
pose_provider = PoseProvider(config)

def on_teleop_event(evt):
    # Get transformed delta directly
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    # Delta is already in robot frame (per targetFrame config)
    # Send to robot controller
    control_robot(
        position_delta=(delta["dx"], delta["dy"], delta["dz"]),
        rotation_delta=(delta["rx"], delta["ry"], delta["rz"])
    )
```

## Data Rate and Timing

### Update Frequency
- The Televoodoo App streams at up to **60 Hz** (limited by iOS ARKit)
- Actual rate depends on phone performance and BLE throughput
- Your callback is invoked for each received pose update

### Handling High-Frequency Data

```python
import time
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

class PoseProcessor:
    def __init__(self, min_interval=0.033):  # Max 30 Hz processing
        self.last_process_time = 0
        self.min_interval = min_interval
    
    def handle_pose(self, evt):
        current_time = time.time()
        
        # Throttle processing if needed
        if current_time - self.last_process_time < self.min_interval:
            return
        
        delta = pose_provider.get_delta(evt)
        if delta is None:
            return
        
        self.last_process_time = current_time
        self.process_pose(delta)
    
    def process_pose(self, delta):
        # Your application logic here
        print(f"Delta: ({delta['dx']:.3f}, {delta['dy']:.3f}, {delta['dz']:.3f})")

processor = PoseProcessor()
start_televoodoo(callback=processor.handle_pose)
```

## Validation and Error Handling

### Checking for Valid Data

```python
def validate_pose(pose_data):
    """Validate pose data completeness and sanity"""
    
    # Check required fields
    required_fields = ['movement_start', 'x', 'y', 'z', 'qx', 'qy', 'qz', 'qw']
    for field in required_fields:
        if field not in pose_data:
            print(f"❌ Missing field: {field}")
            return False
    
    # Check quaternion normalization
    qx, qy, qz, qw = pose_data['qx'], pose_data['qy'], pose_data['qz'], pose_data['qw']
    q_magnitude = (qx**2 + qy**2 + qz**2 + qw**2) ** 0.5
    
    if abs(q_magnitude - 1.0) > 0.01:
        print(f"⚠️  Quaternion not normalized: magnitude = {q_magnitude}")
        return False
    
    return True

def handle_pose(pose_data):
    if not validate_pose(pose_data):
        return
    
    # Process valid pose data
    pass
```

## Working with Recorded Data

See the `examples/record_poses/` example for how to:
- Record pose streams to disk
- Replay recorded sessions
- Analyze pose data offline

## Visualization

Use the **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** desktop app to:
- Visualize incoming poses in real-time 3D
- Configure coordinate transforms
- Export transform configurations for use in your Python code

## See Also

- **BLE_PERIPHERAL_API.md**: Details on the BLE service and characteristics
- **examples/print_poses**: Print absolute poses
- **examples/print_delta_poses**: Print pose deltas for robot teleoperation
- **examples/record_poses**: Record poses to JSON file
- **examples/measure_frequency**: Measure pose input frequency

## Support

For questions about pose data:
- Check the examples in `python/televoodoo/examples/`
- Use Televoodoo Viewer to visualize and debug coordinate systems
- File issues on the [GitHub repository](https://github.com/Mana-Robotics/televoodoo-python)

