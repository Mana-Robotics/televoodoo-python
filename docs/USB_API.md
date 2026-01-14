# USB Connection API

## Overview

USB connection provides a wired alternative to WiFi and BLE for connecting the Televoodoo App to your Python application. USB creates a virtual network interface between your phone and computer, offering:

- **Lower latency**: ~5-10ms (vs ~16ms WiFi)
- **Higher reliability**: Wired connection, no wireless interference
- **No WiFi network required**: Works without WiFi access

## How It Works

USB and WiFi use the **same server implementation**:

1. **Server binds to `0.0.0.0:50000`** — listens on ALL network interfaces
2. **mDNS advertises on ALL interfaces** — phone discovers via `<name>._televoodoo._udp.local.`
3. **Phone discovers via mDNS** — regardless of connection type (WiFi or USB)

The QR code only contains:
- `name`: Service name for mDNS discovery
- `code`: Authentication code  
- `transport`: Connection type (`"usb"`)

No IP address is needed — mDNS handles discovery automatically.

## When to Use USB

| Scenario | Recommended Transport |
|----------|----------------------|
| Low latency critical (force feedback loops) | **USB** |
| No WiFi network available | **USB** |
| Wireless interference issues | **USB** |
| Quick setup, any network | WiFi |
| No cable available | WiFi or BLE |

---

## Prerequisites

> ⚠️ **Important**: iOS and Android require **opposite** configurations!

### macOS + iOS

> **Use macOS Internet Sharing** (Mac shares its network to iPhone via USB).
> **Do NOT enable** Personal Hotspot/Tethering on iPhone!

| Setting | Required State |
|---------|----------------|
| Mac: Internet Sharing | ✅ **Enabled** |
| iPhone: Personal Hotspot | ❌ **Disabled** |

**Setup Steps:**

1. Connect iPhone to Mac via Lightning/USB-C cable
2. If prompted on iPhone, tap **Trust** to trust the computer
3. **Disable Personal Hotspot** on iPhone (Settings → Personal Hotspot → Off)
4. On Mac, go to **System Settings → General → Sharing**
5. Click **Internet Sharing** (don't enable yet)
6. Set **"Share your connection from"** to your internet source (e.g., "Wi-Fi")
7. Check **"iPhone USB"** under "To computers using"
8. Enable **Internet Sharing** (toggle it on)

### macOS + Android

> **Use Android USB Tethering** (Android shares its network to Mac via USB).
> **Do NOT enable** Internet Sharing on Mac!

| Setting | Required State |
|---------|----------------|
| Mac: Internet Sharing | ❌ **Disabled** |
| Android: USB Tethering | ✅ **Enabled** |

**Setup Steps:**

1. **Disable Internet Sharing** on Mac (System Settings → General → Sharing)
2. Connect phone to Mac via USB cable (data-capable, not charge-only)
3. Go to **Settings → Network & Internet → Hotspot & Tethering**
4. Enable **USB Tethering**

### Ubuntu/Linux + Android

1. Connect Android phone via USB cable
2. Enable **USB Tethering** on phone (Settings → Hotspot & Tethering)

### Ubuntu/Linux + iOS

⚠️ Requires additional packages:
```bash
sudo apt install libimobiledevice6 usbmuxd
sudo systemctl start usbmuxd
```

---

## CLI Usage

```bash
# USB connection
televoodoo --connection usb

# USB with static credentials
televoodoo --connection usb --name myrobot --code ABC123
```

---

## Python API

```python
from televoodoo import start_televoodoo

def on_event(evt):
    if evt.get("type") == "pose":
        print(f"Pose: {evt['data']}")

# USB connection
start_televoodoo(callback=on_event, connection="usb")

# USB with static credentials
start_televoodoo(
    callback=on_event,
    connection="usb",
    name="myrobot",
    code="ABC123",
)
```

---

## QR Code Format

The QR code uses a minimal format with mDNS discovery:

```json
{
  "name": "myrobot",
  "code": "ABC123",
  "transport": "usb"
}
```

The phone app uses the `name` to discover the service via mDNS:
- Service: `myrobot._televoodoo._udp.local.`

No IP address is included — mDNS handles discovery on whatever network interface the phone is connected to.

---

## Technical Details

### Unified Server Architecture

WiFi and USB use the same server:

```
┌─────────────────────────────────────────────┐
│  UDP Server (binds to 0.0.0.0:50000)        │
│  - Receives packets from any interface      │
│  - mDNS advertises on all interfaces        │
└─────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌──────────────┐
   │  WiFi    │        │  USB Network │
   │ Interface│        │  Interface   │
   └──────────┘        └──────────────┘
```

### mDNS Discovery

The server advertises via mDNS (Bonjour/Zeroconf):
- **Service type**: `_televoodoo._udp.local.`
- **Instance name**: `<name> @ <hostname>._televoodoo._udp.local.`
- **TXT records**: `v=1`, `port=50000`, `name=<name>`

The phone app discovers the service on whatever network it's connected to (WiFi LAN or USB tethering network).

### Why This Works

Both WiFi and USB tethering create network interfaces:
- WiFi: Phone and Mac on same LAN
- USB: Phone and Mac on same point-to-point network

In both cases, mDNS works because the devices are on the same network segment. The server doesn't need to know which interface to use — it listens on all of them.

---

## Detecting USB Interfaces

For diagnostics, you can check what USB interfaces are detected:

```python
from televoodoo.usb import detect_usb_interfaces, is_usb_available

# Check if USB is available
if is_usb_available():
    interfaces = detect_usb_interfaces()
    for iface in interfaces:
        print(f"Found: {iface.name} ({iface.device})")
else:
    print("No USB network interface detected")
```

On macOS, this detects interfaces by name (e.g., "Pixel 9a", "iPhone USB") rather than IP ranges.

---

## Troubleshooting

### Phone can't discover server

1. **Verify correct setup** (iOS and Android require **opposite** configurations!):
   - **iOS**: Mac Internet Sharing = ON, iPhone Personal Hotspot = OFF
   - **Android**: Mac Internet Sharing = OFF, Android USB Tethering = ON
2. **Check mDNS**: The server should show `mdns_registered` in its output
3. **Same network**: Ensure phone and Mac are on the same network segment

### Server starts but no connection

1. **Check firewall**: Ensure UDP port 50000 is not blocked
2. **Verify correct setup**: See above — iOS and Android need opposite settings!
3. **Trust the computer**: On iOS, ensure you've tapped "Trust" when prompted

### Connection drops

1. **Cable issue**: Use a data-capable USB cable (not charge-only)
2. **Settings changed**: Check that the correct tethering/sharing settings are still enabled

---

## See Also

- **WIFI_API.md**: WiFi/UDP protocol details (shared with USB)
- **BLE_API.md**: Bluetooth Low Energy connection
- **CONNECTION_SETUP.md**: General connection guide
