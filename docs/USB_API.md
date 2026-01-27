# USB Connection

USB provides the **lowest latency** (~5-10ms) by eliminating WiFi overhead. It uses the same TCP protocol as WiFi but over a USB network interface.

> For protocol details, see [Protocol Docs](MOBILE_PROTOCOL.md).

## How It Works

USB creates a network interface between phone and computer:

- **iOS**: Uses Mac's Internet Sharing (bridge interface)
- **Android**: Uses USB Tethering (phone shares its network)

The Python server binds to all interfaces (`0.0.0.0`) and broadcasts UDP beacons. The phone discovers the server via beacons, just like WiFi—no special USB handling needed.

## iOS Setup (Mac Only)

### Prerequisites

1. **iPhone** connected via USB cable
2. **Mac** with Internet Sharing enabled

### Steps

1. Connect iPhone to Mac via USB
2. On Mac open **System Settings → General → Sharing**
3. Enable **Internet Sharing**:
   - Share from: **Wi-Fi** (or Ethernet)
   - To: **iPhone USB** (sometimes listed 2 times - select both!)
4. On iPhone: Disable Personal Hotspot (if enabled)
5. Run `televoodoo --connection usb`

### Verification

When connected, the Mac creates a `bridge100` interface:

```bash
ifconfig bridge100
# Should show an IP like 192.168.2.1
```

## Android Setup

### Prerequisites

1. **Android phone** with USB Tethering support
2. **USB cable** (data-capable, not charge-only)

### Steps

1. Connect Android to computer via USB
2. On Android: **Settings → Network → Hotspot → USB Tethering** → Enable
3. Run `televoodoo --connection usb`

### Platform-Specific Notes

| Platform | Interface Name |
|----------|---------------|
| macOS | Phone name (e.g., "Pixel 9a") |
| Linux | `usb0` or `enp*` |
| Windows | Network adapter appears automatically |

## CLI Usage

```bash
# Explicit USB mode
televoodoo --connection usb

# With custom ports
televoodoo --connection usb --tcp-port 51000
```

## Python Usage

```python
from televoodoo import start_televoodoo

def on_event(evt):
    if evt.get("type") == "pose":
        print(evt["data"]["absolute_input"])

start_televoodoo(callback=on_event, connection="usb")
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Phone not detected | Check cable (must be data-capable), try different USB port |
| iOS: No bridge interface | Enable Internet Sharing, disable iPhone Personal Hotspot |
| Android: No USB Tethering option | Enable Developer Options, or check carrier restrictions |
| Server not found | Verify network interface is active with `ifconfig` or `ip addr` |

## Latency Comparison

| Connection | Typical Latency |
|------------|-----------------|
| USB | ~5-10ms |
| WiFi | ~16ms |
| BLE | ~32ms |

USB is recommended for force-feedback applications where latency is critical.

## See Also

- **[Protocol Docs](MOBILE_PROTOCOL.md)** — Full protocol specification
- **[Connection & Authentication](CONNECTION_AUTHENTICATION.md)** — QR codes, credentials
- **[WiFi API](WIFI_API.md)** — Simpler setup alternative
- **[Haptic Feedback](HAPTIC_FEEDBACK.md)** — Force feedback over USB
