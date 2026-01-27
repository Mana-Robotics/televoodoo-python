# BLE Connection

Bluetooth Low Energy provides wireless connectivity when WiFi is unavailable. It has higher latency (~32ms) than WiFi/USB but works without network configuration.

> For protocol details, see [Protocol Docs](MOBILE_PROTOCOL.md).

## Platform Support

| Platform | Support |
|----------|---------|
| macOS | Full support (CoreBluetooth) |
| Ubuntu Linux | Full support (BlueZ via bluezero) |
| Windows | Not supported |

## How It Works

1. Python creates a BLE peripheral with the Televoodoo GATT service
2. Phone scans for peripherals matching the QR code `name`
3. Phone connects and writes auth code to Auth characteristic
4. Pose data streams via Write operations to Pose characteristic
5. Heartbeat (2 Hz) and Haptic feedback via Notify characteristics

## BLE Service

**Service UUID**: `1C8FD138-FC18-4846-954D-E509366AEF61`

| Characteristic | UUID Suffix | Properties | Direction |
|----------------|-------------|------------|-----------|
| Auth | `...AEF63` | Write | Phone → Host |
| Pose | `...AEF64` | Write | Phone → Host |
| Heartbeat | `...AEF65` | Read, Notify | Host → Phone |
| Command | `...AEF66` | Write | Phone → Host |
| Haptic | `...AEF67` | Read, Notify | Host → Phone |
| Config | `...AEF68` | Read, Notify | Host → Phone |

See [Protocol Docs](MOBILE_PROTOCOL.md) for message formats.

## CLI Usage

```bash
televoodoo --connection ble
```

## Python Usage

```python
from televoodoo import start_televoodoo

def on_event(evt):
    if evt.get("type") == "pose":
        print(evt["data"]["absolute_input"])

start_televoodoo(callback=on_event, connection="ble")
```

## Platform Setup

### macOS

No setup required. Grant Bluetooth permission when prompted.

### Ubuntu Linux

Install BlueZ dependencies:

```bash
sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev bluetooth bluez
```

Ensure Bluetooth service is running:

```bash
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
bluetoothctl power on
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Peripheral not advertising | Check Bluetooth is enabled, restart app |
| Phone can't find peripheral | Ensure within 10m, clear line of sight |
| Authentication fails | Verify code matches QR, rescan |
| Heartbeat timeout | Python app may be suspended, restart |
| Linux: No adapter found | Run `bluetoothctl power on` |

## Latency Notes

BLE has higher latency than WiFi/USB:

| Connection | Latency |
|------------|---------|
| USB | ~5-10ms |
| WiFi | ~16ms |
| BLE | ~32ms effective |

BLE uses batched writes and connection intervals that add latency. For latency-sensitive applications, prefer WiFi or USB.

## See Also

- **[Protocol Docs](MOBILE_PROTOCOL.md)** — Full protocol specification
- **[Connection & Authentication](CONNECTION_AUTHENTICATION.md)** — QR codes, credentials
- **[WiFi API](WIFI_API.md)** — Lower latency alternative
- **[Haptic Feedback](HAPTIC_FEEDBACK.md)** — Force feedback via BLE
