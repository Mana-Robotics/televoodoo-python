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

## Pose Data Payload

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

## Connection Flow

1. **Your Python app starts**: Televoodoo Python creates a BLE peripheral
2. **QR code displayed**: Shows connection info (peripheral name + access code)
3. **User scans QR code**: Using the Televoodoo App on their smartphone
4. **App connects**: Automatically discovers and connects to your peripheral
5. **Authentication**: App sends the access code
6. **Pose streaming begins**: Your callback receives real-time pose data
7. **Your app processes**: Use the pose data for your application logic



