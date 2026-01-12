# Televoodoo Python - Connection Setup Guide

## Overview

Televoodoo Python uses QR codes to streamline the connection process between your Python application and the Televoodoo App on smartphones. This guide explains how Televoodoo Python generates connection information and how users connect their devices.

## Connection Types

| Type | Default | Latency | Requirements |
|------|---------|---------|--------------|
| **WiFi** | ✅ Yes | ~16ms consistent | Same network |
| **BLE** | No | ~17ms average (batched) | Platform-specific |

WiFi is recommended for:
- Lower, more consistent latency
- Cross-platform compatibility (works on Windows, Linux, macOS)
- No platform-specific BLE dependencies

## Connection Flow

### 1. Start Your Python Application

```bash
# WiFi (default) with random credentials
televoodoo

# WiFi with static credentials
televoodoo --name myvoodoo --code ABC123

# BLE connection (if needed)
televoodoo --connection ble --name myvoodoo --code ABC123
```

Or programmatically:

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

def my_callback(evt):
    delta = pose_provider.get_delta(evt)
    if delta is not None:
        print(delta)

# WiFi (default) with random credentials
start_televoodoo(callback=my_callback)

# WiFi with static credentials
start_televoodoo(callback=my_callback, name="myvoodoo", code="ABC123")

# BLE connection (if needed)
start_televoodoo(callback=my_callback, name="myvoodoo", code="ABC123", connection="ble")
```

### 2. QR Code Display

Televoodoo Python automatically generates and displays a QR code in the terminal containing:
- **Transport type**: `wifi` or `ble`
- **Server/peripheral name**: e.g., `voodooA3` or your custom name
- **Access code**: A 6-character authentication code
- **IP address and port** (WiFi only)

**Example terminal output (WiFi):**
```
{"type": "session", "name": "myvoodoo", "code": "ABC123", "transport": "wifi", "ip": "192.168.1.100", "port": 50000}

[QR CODE DISPLAYED HERE]

```

### 3. User Scans QR Code

The user opens the Televoodoo App on their smartphone and:
1. Points the camera at the QR code
2. App reads the connection information (including transport type)
3. App automatically connects via WiFi or BLE based on QR code
4. App authenticates using the access code
5. Pose streaming begins automatically

### 4. Pose Data Flows

Once connected, your callback function receives real-time pose events:

```python
def my_callback(evt):
    delta = pose_provider.get_delta(evt)
    if delta is not None:
        print(f"Delta: {delta['dx']:.3f}, {delta['dy']:.3f}, {delta['dz']:.3f}")
        # Use pose data in your application
```

## QR Code Format

### JSON Structure

The QR code contains a JSON string with connection credentials and transport info:

**WiFi (default):**
```json
{
  "name": "myvoodoo",
  "code": "ABC123",
  "transport": "wifi",
  "ip": "192.168.1.100",
  "port": 50000
}
```

**BLE:**
```json
{
  "name": "myvoodoo",
  "code": "ABC123",
  "transport": "ble"
}
```

### Field Descriptions

- **name** (string): Server/peripheral name
  - Random mode: `voodoo` + 2-character random suffix (e.g., `voodooX7`)
  - Static mode: Your custom name (e.g., `myvoodoo`)

- **code** (string): 6-character authentication code
  - Random mode: Randomly generated alphanumeric code
  - Static mode: Your custom code
  - Format: Uppercase letters and digits (A-Z, 0-9)

- **transport** (string): Connection type (`"wifi"` or `"ble"`)

- **ip** (string, WiFi only): Server IP address on local network

- **port** (number, WiFi only): UDP port (default: 50000)

### Example QR Code Contents

**WiFi with random credentials:**
```json
{
  "name": "voodooK9",
  "code": "X3P7M2",
  "transport": "wifi",
  "ip": "192.168.1.50",
  "port": 50000
}
```

**BLE with static credentials:**
```json
{
  "name": "my_robot_arm",
  "code": "ROBOT1",
  "transport": "ble"
}
```

## Peripheral Naming

### Default (Random) Names

When you don't specify a name, Televoodoo Python generates one:

```python
start_televoodoo(callback=my_callback)
# Peripheral name: voodooXY (e.g., voodooA3, voodooK9)
```

### Custom (Static) Names

For easier identification during development:

```python
start_televoodoo(callback=my_callback, name="lab_robot_1")
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

**WiFi Solutions**:
- Ensure phone and computer are on the **same WiFi network**
- Check that your Python app is still running
- Verify no firewall is blocking UDP port 50000
- Try specifying a different port: `televoodoo --wifi-port 51000`

**BLE Solutions**:
- Verify Bluetooth is enabled on both devices
- Ensure devices are within BLE range (~10 meters, line of sight)
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
from televoodoo import start_televoodoo, generate_credentials, print_session_qr

# Generate and display credentials manually
name, code = generate_credentials()
print_session_qr(name, code)

def my_callback(evt):
    pass

# Start without automatic QR display (quiet mode)
start_televoodoo(
    callback=my_callback,
    name=name,
    code=code,
    quiet=True
)
```

## Multi-Device Setup

### Running Multiple Peripherals

Each peripheral needs a unique name:

```python
# Note: Running multiple BLE peripherals on the same machine may have platform limitations.
# Device 1
start_televoodoo(callback=callback1, name="robot_left", code="LEFT01")

# Device 2  
start_televoodoo(callback=callback2, name="robot_right", code="RIGHT1")
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

### All Platforms (WiFi - Default)
- QR codes display well in most terminals
- Ensure phone and computer are on the same WiFi network
- UDP port 50000 (or custom via `--wifi-port`) must not be blocked by firewall
- mDNS discovery requires `zeroconf` package (auto-installed)

### macOS (BLE)
- Bluetooth permissions may require user approval on first run
- Works reliably with native Core Bluetooth

### Ubuntu/Linux (BLE)
- BlueZ must be running: `sudo systemctl start bluetooth`
- May need to run with `sudo` depending on BlueZ configuration
- Install system headers: `sudo apt-get install libdbus-1-dev libglib2.0-dev`

### Windows
- WiFi works out of the box
- BLE is not supported

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

- **WIFI_API.md**: Technical details on the WiFi/UDP protocol (default)
- **BLE_API.md**: Technical details on the BLE service
- **POSE_DATA_FORMAT.md**: What data your callback receives
- **examples/**: Sample applications showing complete workflows

## Support

For connection issues:
- Verify Bluetooth is enabled on both devices
- Check the [Troubleshooting](#connection-troubleshooting) section above
- Review the examples in `python/televoodoo/examples/`
- File issues on the [GitHub repository](https://github.com/Mana-Robotics/televoodoo-python)

