# Televoodoo Python - Connection Setup Guide

## Overview

Televoodoo Python uses QR codes to streamline the connection process between your Python application and the Televoodoo App on smartphones. This guide explains how Televoodoo Python generates connection information and how users connect their devices.

## Connection Flow

### 1. Start Your Python Application

```bash
# With random credentials (default)
televoodoo

# With static credentials (recommended for development)
televoodoo --name myvoodoo --code ABC123
```

Or programmatically:

```python
from televoodoo.ble import start_peripheral

def my_callback(pose_data):
    print(pose_data)

# Random credentials
start_peripheral(callback=my_callback)

# Static credentials
start_peripheral(callback=my_callback, name="myvoodoo", code="ABC123")
```

### 2. QR Code Display

Televoodoo Python automatically generates and displays a QR code in the terminal containing:
- **Peripheral name**: The BLE device name (e.g., `voodooA3` or your custom name)
- **Access code**: A 6-character authentication code

**Example terminal output:**
```
┌─────────────────────────────────────┐
│ Televoodoo BLE Peripheral           │
│                                     │
│ Name: myvoodoo                      │
│ Code: ABC123                        │
│                                     │
│ [QR CODE DISPLAYED HERE]            │
│                                     │
│ Scan with Televoodoo App to connect │
└─────────────────────────────────────┘
```

### 3. User Scans QR Code

The user opens the Televoodoo App on their smartphone and:
1. Points the camera at the QR code
2. App reads the connection information
3. App automatically discovers and connects to your BLE peripheral
4. App authenticates using the access code
5. Pose streaming begins automatically

### 4. Pose Data Flows

Once connected, your callback function receives real-time pose data:

```python
def my_callback(pose_data):
    if pose_data.get('movement_start'):
        print(f"Position: {pose_data['x']:.3f}, {pose_data['y']:.3f}, {pose_data['z']:.3f}")
        # Use pose data in your application
```

## QR Code Format

### JSON Structure

The QR code contains a JSON string with connection credentials:

```json
{
  "name": "myvoodoo",
  "code": "ABC123"
}
```

### Field Descriptions

- **name** (string): BLE peripheral's advertised local name
  - Random mode: `voodoo` + 2-character random suffix (e.g., `voodooX7`)
  - Static mode: Your custom name (e.g., `myvoodoo`)
  
- **code** (string): 6-character authentication code
  - Random mode: Randomly generated alphanumeric code
  - Static mode: Your custom code
  - Format: Uppercase letters and digits (A-Z, 0-9)

### Example QR Code Contents

**Random credentials:**
```json
{
  "name": "voodooK9",
  "code": "X3P7M2"
}
```

**Static credentials:**
```json
{
  "name": "my_robot_arm",
  "code": "ROBOT1"
}
```

## Peripheral Naming

### Default (Random) Names

When you don't specify a name, Televoodoo Python generates one:

```python
start_peripheral(callback=my_callback)
# Peripheral name: voodooXY (e.g., voodooA3, voodooK9)
```

### Custom (Static) Names

For easier identification during development:

```python
start_peripheral(callback=my_callback, name="lab_robot_1")
# Peripheral name: lab_robot_1
```

### Name Requirements
- **Length**: 1-20 characters recommended
- **Characters**: Letters, numbers, underscores, hyphens
- **Avoid**: Special characters that may not work well with BLE
- **Case**: Preserved as provided

## Access Codes

### Security Model

Access codes provide simple authentication to prevent accidental connections:
- **Not cryptographically strong**: Don't rely on this for security-critical applications
- **Temporary by default**: Changes on each launch (random mode)
- **Visual transmission**: Shown via QR code (requires physical access)
- **Single session**: Valid only while your Python app is running

### Random Access Codes (Default)

```bash
televoodoo
# Access code: X3P7M2 (random, changes each launch)
```

**Use case**: Quick testing, demos, one-off sessions

### Static Access Codes

```bash
televoodoo --name mydevice --code ABC123
# Access code: ABC123 (same every time)
```

**Use case**: Development, frequent reconnections, team environments

### Code Requirements
- **Length**: Exactly 6 characters
- **Format**: Uppercase letters (A-Z) and digits (0-9)
- **Examples**: `ABC123`, `ROBOT1`, `TEST99`

## Connection Troubleshooting

### QR Code Not Scanning

**Problem**: Televoodoo App can't read the QR code

**Solutions**:
- Ensure good lighting
- Increase terminal font size for a larger QR code
- Try a terminal with better Unicode support
- Manually enter credentials in the app (if supported)

### Device Not Found

**Problem**: App says "Device not found" after scanning QR code

**Solutions**:
- Verify Bluetooth is enabled on both devices
- Ensure devices are within BLE range (~10 meters, line of sight)
- Check that your Python app is still running
- Restart the BLE peripheral (restart your Python app)
- On Linux, verify BlueZ service: `sudo systemctl status bluetooth`

### Authentication Failed

**Problem**: App connects but immediately disconnects

**Solutions**:
- Verify the access code in the QR code matches your app
- Ensure you scanned the correct/latest QR code
- Restart your Python app and scan the new QR code

### Connection Drops Frequently

**Problem**: Connection established but drops often

**Solutions**:
- Reduce distance between devices
- Minimize obstacles between devices
- Check for BLE interference (Wi-Fi, other devices)
- On Linux, check BlueZ logs: `journalctl -u bluetooth`

## Advanced Usage

### Programmatic QR Code Generation

```python
import json
from televoodoo.ble import generate_qr_code

# Generate connection info
connection_info = {
    "name": "mydevice",
    "code": "ABC123"
}

# Create QR code (for display or export)
qr_image = generate_qr_code(json.dumps(connection_info))
qr_image.save("connection_qr.png")
```

### Custom Connection Display

```python
from televoodoo.ble import start_peripheral

def my_callback(pose_data):
    pass

# Start peripheral without automatic QR display
peripheral = start_peripheral(
    callback=my_callback,
    name="mydevice",
    code="ABC123",
    show_qr=False  # Suppress automatic QR display
)

# Display connection info in your own UI
print(f"Connect using:")
print(f"  Name: {peripheral.name}")
print(f"  Code: {peripheral.code}")
```

### Web-Based QR Code Display

For remote or headless deployments, display the QR code in a web interface:

```python
from flask import Flask, render_template
from televoodoo.ble import start_peripheral, get_connection_info

app = Flask(__name__)

@app.route('/')
def connection_page():
    info = get_connection_info()
    return render_template('connection.html', 
                         name=info['name'], 
                         code=info['code'],
                         qr_data=info['qr_data'])

def pose_callback(pose_data):
    # Handle poses
    pass

if __name__ == '__main__':
    # Start BLE peripheral in background thread
    start_peripheral(callback=pose_callback, threaded=True)
    
    # Serve web UI
    app.run(host='0.0.0.0', port=5000)
```

## Multi-Device Setup

### Running Multiple Peripherals

Each peripheral needs a unique name:

```python
# Device 1
start_peripheral(callback=callback1, name="robot_left", code="LEFT01")

# Device 2  
start_peripheral(callback=callback2, name="robot_right", code="RIGHT1")
```

> **Note**: Running multiple BLE peripherals on the same machine may have platform limitations.

### Team Development

For team environments, use static credentials and share them:

```bash
# Shared in team documentation
televoodoo --name lab_robot_5 --code LAB005
```

Everyone on the team can connect their phones using the same credentials.

## Platform-Specific Notes

### macOS
- QR codes display well in Terminal.app
- Bluetooth permissions may require user approval on first run
- Works reliably with native Core Bluetooth

### Ubuntu/Linux
- Install QR code libraries: `pip install qrcode[pil]`
- Ensure terminal supports Unicode for QR display
- BlueZ must be running: `sudo systemctl start bluetooth`
- May need to run with `sudo` depending on BlueZ configuration

## Security Considerations

### Access Code Limitations
- **Not encryption**: Data is not encrypted over BLE
- **Physical access**: Anyone with the QR code can connect
- **Session-based**: Codes expire when your app stops

### Best Practices
- Use **random codes** in production or public demos
- Use **static codes** only in controlled development environments
- **Don't share** QR codes publicly (screenshots, demos)
- **Regenerate** credentials frequently if security is a concern
- Consider adding **application-level authentication** for sensitive use cases

## See Also

- **BLE_PERIPHERAL_API.md**: Technical details on the BLE service
- **POSE_DATA_FORMAT.md**: What data your callback receives
- **examples/**: Sample applications showing complete workflows

## Support

For connection issues:
- Verify Bluetooth is enabled on both devices
- Check the [Troubleshooting](#connection-troubleshooting) section above
- Review the examples in `python/televoodoo/examples/`
- File issues on the [GitHub repository](https://github.com/Mana-Robotics/televoodoo-python)

