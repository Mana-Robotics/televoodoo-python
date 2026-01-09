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
- **Y-axis**: Typically vertical (up is positive)
- **Z-axis**: Typically depth (forward is positive)
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

### Basic Example

```python
from televoodoo.ble import start_peripheral

def handle_pose(pose_data):
    """Process incoming pose data"""
    
    # Check if this is a new movement start (origin reset)
    if pose_data.get('movement_start', False):
        print("🎯 New movement started — origin reset")
    
    # Extract position
    x = pose_data['x']
    y = pose_data['y']
    z = pose_data['z']
    
    # Extract rotation (use quaternion for accuracy)
    qx = pose_data['qx']
    qy = pose_data['qy']
    qz = pose_data['qz']
    qw = pose_data['qw']
    
    # Use the pose data
    print(f"📍 Position: ({x:.3f}, {y:.3f}, {z:.3f}) m")
    print(f"🔄 Quaternion: ({qx:.3f}, {qy:.3f}, {qz:.3f}, {qw:.3f})")

start_peripheral(callback=handle_pose)
```

### Using the Pose Class

Televoodoo Python provides a `Pose` class for convenient pose manipulation:

```python
from televoodoo.pose import Pose
from televoodoo.ble import start_peripheral

def handle_pose(pose_data):
    # Create a Pose object
    pose = Pose.from_dict(pose_data)
    
    # Check tracking status
    if not pose.is_active:
        return
    
    # Access position as numpy array
    position = pose.position  # [x, y, z]
    
    # Access quaternion
    quaternion = pose.quaternion  # [qx, qy, qz, qw]
    
    # Get transformation matrix
    transform_matrix = pose.to_matrix()  # 4x4 homogeneous transform
    
    print(f"Position: {position}")
    print(f"Distance from origin: {pose.distance_from_origin():.3f} m")

start_peripheral(callback=handle_pose)
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

class PoseProcessor:
    def __init__(self, min_interval=0.033):  # Max 30 Hz processing
        self.last_process_time = 0
        self.min_interval = min_interval
    
    def handle_pose(self, pose_data):
        current_time = time.time()
        
        # Throttle processing if needed
        if current_time - self.last_process_time < self.min_interval:
            return
        
        self.last_process_time = current_time
        
        # Check for new movement start
        if pose_data.get('movement_start'):
            self.reset_origin(pose_data)
        
        self.process_pose(pose_data)
    
    def reset_origin(self, pose_data):
        # Reset delta origin
        pass
    
    def process_pose(self, pose_data):
        # Your application logic here
        pass

processor = PoseProcessor()
start_peripheral(callback=processor.handle_pose)
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

See the `examples/pose_recording/` example for how to:
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
- **examples/pose_logger**: Simple example of logging pose data
- **examples/pose_recording**: Record and replay pose streams
- **examples/pose_frequency**: Analyze pose data update rates

## Support

For questions about pose data:
- Check the examples in `python/televoodoo/examples/`
- Use Televoodoo Viewer to visualize and debug coordinate systems
- File issues on the [GitHub repository](https://github.com/Mana-Robotics/televoodoo-python)

