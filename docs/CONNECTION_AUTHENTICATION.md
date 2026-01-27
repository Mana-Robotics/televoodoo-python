# Connection & Authentication

This guide covers how to connect the Televoodoo App to your Python application.

## Connection Types

| Type | Latency | Requirements | Best For |
|------|---------|--------------|----------|
| **WiFi** (default) | ~16ms | Same network | General use, cross-platform |
| **USB** | ~5-10ms | USB cable + tethering | Lowest latency, force feedback |
| **BLE** | ~32ms | Bluetooth | When WiFi/USB unavailable |

### Selecting a Connection Type

**CLI:**

```bash
televoodoo --connection wifi   # WiFi (default)
televoodoo --connection usb    # USB tethering
televoodoo --connection ble    # Bluetooth
```

**Python:**

```python
start_televoodoo(callback=handler, connection="wifi")  # or "usb", "ble"
```

## Connection Flow

1. **Start Python application** — QR code displayed in terminal
2. **Scan QR code** with Televoodoo App
3. **App discovers server** via UDP beacons (WiFi/USB) or BLE scan
4. **App connects and authenticates**
5. **Pose streaming begins**

## QR Code Format

```json
{
  "name": "voodooXY",
  "code": "ABC123",
  "transport": "wifi"
}
```

| Field | Description |
|-------|-------------|
| `name` | Service name (1-20 chars) — used for beacon/BLE matching |
| `code` | Authentication code (6 chars, A-Z 0-9) |
| `transport` | `"wifi"`, `"usb"`, or `"ble"` |

**No IP address is included.** The phone discovers the server via:
- **WiFi/USB**: UDP beacons on port 50001
- **BLE**: Scanning for peripherals with matching name

## Authentication Credentials

### Random Credentials (Default)

```bash
televoodoo
# Name: voodooX7 (random)
# Code: X3P7M2 (random)
```

New credentials are generated each launch.

### Static Credentials

**CLI:**

```bash
televoodoo --name myvoodoo --code ABC123
```

**Python:**

```python
start_televoodoo(callback=handler, name="myvoodoo", code="ABC123")
```

**Config file:**

```json
{
  "authCredentials": {
    "name": "myvoodoo",
    "code": "ABC123"
  }
}
```

### Requirements

| Field | Requirements |
|-------|--------------|
| `name` | 1-20 characters, letters/numbers/underscores/hyphens |
| `code` | Exactly 6 characters, uppercase A-Z and 0-9 |

## Multi-Device Setup

Each device needs a unique name:

```python
# Device 1
start_televoodoo(callback=cb1, name="robot_left", code="LEFT01")

# Device 2
start_televoodoo(callback=cb2, name="robot_right", code="RIGHT1")
```

## Troubleshooting

### General

| Issue | Solution |
|-------|----------|
| QR code not scanning | Increase terminal font size, improve lighting |
| Authentication failed | Rescan QR code (credentials change each launch) |
| Connection drops | Reduce distance, check for interference |

### WiFi

| Issue | Solution |
|-------|----------|
| Server not found | Ensure same network, check firewall (ports 50000/50001) |

### USB

| Issue | Solution |
|-------|----------|
| iOS not working | Enable Mac Internet Sharing, disable iPhone Personal Hotspot |
| Android not working | Enable USB Tethering on phone |

### BLE

| Issue | Solution |
|-------|----------|
| Peripheral not found | Ensure Bluetooth enabled, within 10m range |
| Linux: No adapter | Run `bluetoothctl power on` |

## Security Notes

- **Codes are session-based** — only valid while app is running
- **Not encrypted** — data travels in plaintext
- **Random codes** recommended for public demos
- Don't share QR code screenshots publicly

## See Also

- **[Protocol Docs](MOBILE_PROTOCOL.md)** — Full protocol specification
- **[WiFi API](WIFI_API.md)** — WiFi setup details
- **[USB API](USB_API.md)** — USB tethering setup
- **[BLE API](BLE_API.md)** — Bluetooth setup
- **[Configuration](CONFIGURATION.md)** — Config file options
