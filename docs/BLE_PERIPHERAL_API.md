# Televoodoo Python - BLE Peripheral API

## Overview

Televoodoo Python creates a Bluetooth Low Energy (BLE) peripheral that the Televoodoo App (iOS/Android) connects to. This document describes the BLE service structure that Televoodoo Python exposes, which you can use in your applications to receive real-time 6DoF pose data from smartphones.

## BLE Service Configuration

### Service UUID
```
1C8FD138-FC18-4846-954D-E509366AEF61
```

### Characteristics

Televoodoo Python creates the following BLE characteristics:

#### 1. Authentication Characteristic
- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF63`
- **Properties**: Write, WriteWithoutResponse
- **Purpose**: Receives authentication codes from connecting devices
- **Data Format**: UTF-8 string (6-character access code)
- **Authentication Flow**:
  1. The Televoodoo App connects to your peripheral
  2. The app writes the access code to this characteristic
  3. Televoodoo Python validates the code
  4. If correct, the connection is authenticated for data exchange

#### 2. Pose Data Characteristic
- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF64`
- **Properties**: Write, WriteWithoutResponse
- **Purpose**: Receives 6DoF pose tracking data from the Televoodoo App
- **Data Format**: UTF-8 JSON string
- **Your Code**: Process incoming pose data in your callback function

#### 3. Heartbeat Characteristic
- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF65`
- **Properties**: Read
- **Purpose**: Provides connection health monitoring
- **Data Format**: 4-byte little-endian UInt32 counter
- **Behavior**: Auto-increments to help clients detect stale connections

#### 4. Command Data Characteristic
- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF66`
- **Properties**: Write, WriteWithoutResponse
- **Purpose**: Receives command data from the Televoodoo App
- **Data Format**: UTF-8 JSON string with command name and value

##### Command JSON Format
```json
{
  "command_name": value
}
```

##### Supported Commands
| Command Name | Value Type | Description |
|-------------|------------|-------------|
| `recording` | boolean | Indicates recording start (`true`) or stop (`false`) |
| `keep_recording` | boolean | Indicates whether to keep (`true`) or discard (`false`) the recording |

##### Example Command Payloads

**Recording Started**
```json
{"recording":true}
```

**Recording Stopped**
```json
{"recording":false}
```

**Keep Recording**
```json
{"keep_recording":true}
```

**Discard Recording**
```json
{"keep_recording":false}
```

## Pose Data Format

### JSON Structure Received

Your callback function receives pose data in the following format:

```json
{
  "movement_start": true|false,
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

### Field Descriptions
- **movement_start** (boolean): When `true`, sets this pose as the new origin for delta calculations
- **x, y, z** (double): Position in meters relative to the reference coordinate system
- **x_rot, y_rot, z_rot** (double): Euler angles in degrees
- **qx, qy, qz, qw** (double): Quaternion components (normalized)

### Example: New Movement Start
```json
{
  "movement_start": true,
  "x": 0.1,
  "y": 0.2,
  "z": 0.05,
  "x_rot": 45.0,
  "y_rot": -30.5,
  "z_rot": 15.25,
  "qx": 0.01234,
  "qy": -0.56789,
  "qz": 0.12345,
  "qw": 0.81234
}
```

### Example: Continuous Movement
```json
{
  "movement_start": false,
  "x": 0.12,
  "y": 0.22,
  "z": 0.07,
  "x_rot": 46.0,
  "y_rot": -29.5,
  "z_rot": 16.0,
  "qx": 0.01334,
  "qy": -0.56689,
  "qz": 0.12445,
  "qw": 0.81134
}
```

## Using Televoodoo Python in Your Project

### Basic Usage

```python
from televoodoo.ble import start_peripheral

def my_pose_handler(pose_data):
    """Called whenever new pose data arrives from the Televoodoo App"""
    if pose_data.get('movement_start'):
        print("🎯 New movement started — origin reset")
    
    print(f"Position: ({pose_data['x']:.3f}, {pose_data['y']:.3f}, {pose_data['z']:.3f})")
    print(f"Rotation: ({pose_data['x_rot']:.1f}°, {pose_data['y_rot']:.1f}°, {pose_data['z_rot']:.1f}°)")
    # Use the pose data in your application
    # e.g., control a robot, manipulate 3D objects, etc.

# Start the BLE peripheral
start_peripheral(callback=my_pose_handler)
```

### With Static Credentials

```python
from televoodoo.ble import start_peripheral

def my_pose_handler(pose_data):
    # Your pose handling logic here
    pass

# Use static credentials for easier reconnection during development
start_peripheral(
    callback=my_pose_handler,
    name="myvoodoo",
    code="ABC123"
)
```

### Connection Flow

1. **Your Python app starts**: Televoodoo Python creates a BLE peripheral
2. **QR code displayed**: Shows connection info (peripheral name + access code)
3. **User scans QR code**: Using the Televoodoo App on their smartphone
4. **App connects**: Automatically discovers and connects to your peripheral
5. **Authentication**: App sends the access code
6. **Pose streaming begins**: Your callback receives real-time pose data
7. **Your app processes**: Use the pose data for your application logic

## Platform-Specific Implementation

### macOS
- Uses PyObjC and Core Bluetooth
- Requires `pyobjc-core`, `pyobjc-framework-Cocoa`, `pyobjc-framework-CoreBluetooth`
- Native performance and reliability

### Ubuntu/Linux
- Uses BlueZ via `bluezero` and D-Bus
- Requires system packages: `libdbus-1-dev`, `libglib2.0-dev`, `python3-dev`
- Ensure BlueZ service is running: `sudo systemctl status bluetooth`

## Security Considerations

### Access Codes
- **Random by default**: Generated securely on each launch
- **Static option available**: Use `--code` flag or parameter for development
- **Short-lived**: Only valid during the peripheral's lifetime
- **Simple authentication**: Prevents accidental connections

### Best Practices
- Use random codes in production for better security
- Static codes are useful during development for frequent reconnections
- The access code is displayed in the QR code and terminal output
- No encryption is applied to the BLE data itself (use at your own risk in sensitive environments)

## Troubleshooting

### Common Issues

**Peripheral not discoverable**
- Ensure Bluetooth is enabled on your system
- Check that no other app is using the same service UUID
- On Linux, verify BlueZ service is running

**Connection drops immediately**
- Verify the access code matches
- Ensure the Televoodoo App has Bluetooth permissions
- Check system Bluetooth stability

**No pose data received**
- Verify your callback function is properly defined
- Verify pose data is being received (check `movement_start` field)
- Ensure the Televoodoo App has camera/tracking permissions

### Debug Mode

Run with verbose output to see connection events:

```bash
televoodoo --name mydevice --code ABC123
```

Monitor the terminal output for:
- `🔐 Central [UUID] is now authenticated` - Successful authentication
- Connection and disconnection events
- Pose data reception confirmation

## Advanced Usage

### Coordinate Transforms

Televoodoo Python includes utilities for coordinate system transformations:

```python
from televoodoo.transform import apply_transform
from televoodoo.pose import Pose

def my_pose_handler(pose_data):
    # Create a Pose object
    pose = Pose.from_dict(pose_data)
    
    # Apply transforms if needed (e.g., for your robot's coordinate system)
    transformed = apply_transform(pose, your_transform_config)
    
    # Use the transformed pose
    control_robot(transformed)
```

See the `examples/` directory for complete implementations.

## Support

For issues or questions:
- Check the examples in `python/televoodoo/examples/`
- Review the main README for installation troubleshooting
- Ensure your Televoodoo App version is compatible
- File issues on the [GitHub repository](https://github.com/Mana-Robotics/televoodoo-python)

## Version Information

- **API Version**: 1.0
- **Last Updated**: January 2026
- **Compatible with**: Televoodoo App (iOS/Android)

