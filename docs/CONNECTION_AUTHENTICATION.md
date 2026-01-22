# Connection & Authentication

This guide covers how to connect the Televoodoo App to your Python application, including connection types, QR codes, credentials, and troubleshooting.

## Connection Types

| Type | Latency | Requirements | Best For |
|------|---------|--------------|----------|
| **WiFi** (default) | ~16ms | Same network | General use, cross-platform |
| **USB** | ~5-10ms | USB cable + tethering | Lowest latency, force feedback |
| **BLE** | ~32ms effective | Platform-specific | When WiFi/USB unavailable |

### Selecting a Connection Type

**Via CLI:**

```bash
televoodoo --connection wifi   # WiFi (default)
televoodoo --connection usb    # USB tethering
televoodoo --connection ble    # Bluetooth
```

**Via Python:**

```python
start_televoodoo(callback=handler, connection="wifi")  # or "usb", "ble"
```

### Transport-Specific Documentation

For detailed setup and protocol information, see:

- **[WiFi API](WIFI_API.md)** — UDP protocol, mDNS discovery
- **[USB API](USB_API.md)** — USB tethering setup (platform-specific)
- **[BLE API](BLE_API.md)** — Bluetooth Low Energy service and characteristics

## Connection Flow

1. **Start your Python application** — A QR code is displayed in the terminal
2. **Scan QR code** with Televoodoo App — The app reads connection info
3. **App connects and authenticates** — Using the credentials in the QR code
4. **Pose streaming begins** — Your callback receives real-time pose events

## QR Code Format

The QR code contains minimal JSON data for connection:

```json
{
  "name": "myvoodoo",
  "code": "ABC123",
  "transport": "wifi"
}
```

| Field | Description |
|-------|-------------|
| `name` | Service name for mDNS discovery (WiFi/USB) or BLE peripheral name |
| `code` | 6-character authentication code |
| `transport` | Connection type: `"wifi"`, `"usb"`, or `"ble"` |

For WiFi and USB, the phone discovers the server via mDNS using the `name` field. No IP address is included in the QR code.

## Authentication Credentials

### Random Credentials (Default)

```bash
televoodoo
# Name: voodooX7 (random)
# Code: X3P7M2 (random)
```

New credentials are generated each launch. Good for quick testing.

### Static Credentials

Set fixed credentials for development or ongoing projects:

**Via CLI:**

```bash
televoodoo --name myvoodoo --code ABC123
```

**Via Python:**

```python
start_televoodoo(callback=handler, name="myvoodoo", code="ABC123")
```

**Via Config File:**

```json
{
  "authCredentials": {
    "name": "myvoodoo",
    "code": "ABC123"
  }
}
```

See [Configuration](CONFIGURATION.md) for details.

### Credential Requirements

| Field | Requirements |
|-------|--------------|
| `name` | 1-20 characters, letters/numbers/underscores/hyphens |
| `code` | Exactly 6 characters, uppercase letters (A-Z) and digits (0-9) |

## mDNS Discovery

For WiFi and USB connections, the phone discovers the server via mDNS (Bonjour/Zeroconf):

1. QR code provides the service `name`
2. Phone queries: `<name>._televoodoo._udp.local.`
3. mDNS returns IP address and port
4. Phone connects to the discovered endpoint

This works regardless of which network interface (WiFi LAN or USB tethering) the phone is using.

## Multi-Device Setup

### Running Multiple Peripherals

Each peripheral needs a unique name:

```python
# Device 1
start_televoodoo(callback=callback1, name="robot_left", code="LEFT01")

# Device 2
start_televoodoo(callback=callback2, name="robot_right", code="RIGHT1")
```

> **Note**: Running multiple BLE peripherals on the same machine may have platform limitations.

### Team Development

For team environments, use static credentials and share them:

```bash
televoodoo --name lab_robot_5 --code LAB005
```

## Security Considerations

### Access Code Limitations

- **Not encryption**: Data is not encrypted (WiFi uses plain UDP)
- **Physical access**: Anyone with the QR code can connect
- **Session-based**: Codes are only valid while your app is running

### Best Practices

- Use **random codes** in production or public demos
- Use **static codes** only in controlled development environments
- Don't share QR codes publicly (screenshots, demos)
- Consider adding **application-level authentication** for sensitive use cases

## Troubleshooting

### QR Code Not Scanning

- Ensure good lighting
- Increase terminal font size for a larger QR code
- Try a terminal with better Unicode support
- Manually enter credentials in the app (if supported)

### Device Not Found (WiFi)

- Ensure phone and computer are on the **same WiFi network**
- Check that your Python app is still running
- Verify no firewall is blocking UDP port 50000
- Try specifying a different port: `televoodoo --wifi-port 51000`

### Device Not Found (BLE)

- Verify Bluetooth is enabled on both devices
- Ensure devices are within BLE range (~10 meters, line of sight)
- Restart the BLE peripheral (restart your Python app)
- On Linux, verify BlueZ: `sudo systemctl status bluetooth`

### Device Not Found (USB)

- Verify correct setup — iOS and Android require **opposite** configurations!
  - **iOS**: Mac Internet Sharing = ON, iPhone Personal Hotspot = OFF
  - **Android**: Mac Internet Sharing = OFF, Android USB Tethering = ON
- See [USB API](USB_API.md) for detailed prerequisites

### Authentication Failed

- Verify the access code matches
- Ensure you scanned the correct/latest QR code
- Restart your Python app and scan the new QR code

### Connection Drops Frequently

- Reduce distance between devices
- Minimize obstacles between devices
- Check for interference (other WiFi networks, BLE devices)
- Use USB for maximum reliability

## Platform-Specific Notes

### macOS

- **WiFi**: Works out of box
- **USB**: See [USB API](USB_API.md) for Internet Sharing setup
- **BLE**: Bluetooth permissions may require approval on first run

### Ubuntu/Linux

- **WiFi**: Works out of box
- **USB (Android)**: Enable USB Tethering on phone
- **USB (iOS)**: Requires `sudo apt install libimobiledevice6 usbmuxd`
- **BLE**: Install `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev`

### Windows

- **WiFi**: Works out of box
- **USB**: Works with appropriate drivers (built-in for most phones)
- **BLE**: Not supported

## See Also

- **[WiFi API](WIFI_API.md)** — UDP protocol details
- **[USB API](USB_API.md)** — USB tethering setup guide
- **[BLE API](BLE_API.md)** — Bluetooth Low Energy protocol
- **[Configuration](CONFIGURATION.md)** — Config file credentials
