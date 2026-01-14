# USB Connection API

## Overview

USB connection provides a wired alternative to WiFi and BLE for connecting the Televoodoo App to your Python application. A USB connection creates a virtual network interface between your phone and computer, offering:

- **Lower latency**: ~5-10ms (vs ~16ms WiFi)
- **Higher reliability**: Wired connection, no wireless interference
- **No network dependency**: Works without WiFi access

USB uses the same UDP protocol as WiFi internally, so all features (poses, commands, haptic feedback) work identically.

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

### macOS + iOS (Recommended Setup)

> ⚠️ **Important**: For iOS, use **macOS Internet Sharing** (Mac shares its network to iPhone), NOT iPhone Personal Hotspot/Tethering.

**Setup Steps:**

1. Connect iPhone to Mac via Lightning/USB-C cable
2. If prompted on iPhone, tap **Trust** to trust the computer
3. On Mac, go to **System Settings → General → Sharing**
4. Click **Internet Sharing** (don't enable yet)
5. Set **"Share your connection from"** to your internet source (e.g., "Wi-Fi")
6. Check **"iPhone USB"** under "To computers using"
7. Enable **Internet Sharing** (toggle it on)
8. Confirm when prompted

The Mac will create a network bridge (`192.168.2.x`) and the iPhone will receive an IP via DHCP.

### macOS + Android

**On Android phone:**
1. Connect phone to Mac via USB cable (must be data-capable, not charge-only)
2. Go to **Settings → Network & Internet → Hotspot & Tethering**
3. Enable **USB Tethering**
4. Wait for Mac to detect the network interface (~5 seconds)

### Ubuntu/Linux + Android

1. Connect Android phone via USB cable
2. Enable **USB Tethering** on phone (Settings → Hotspot & Tethering)
3. Some devices may need `usb-modeswitch`:
   ```bash
   sudo apt install usb-modeswitch
   ```

### Ubuntu/Linux + iOS

⚠️ Requires additional packages and may have limited support:
```bash
sudo apt install libimobiledevice6 usbmuxd
sudo systemctl start usbmuxd
```

### Windows + Android

1. Connect Android phone via USB cable
2. Enable **USB Tethering** on phone
3. May need USB drivers (OEM-specific or generic RNDIS)
4. Most modern phones work with Windows 10/11 built-in drivers

### Windows + iOS

⚠️ Requires iTunes or Apple Mobile Device Support installed. Setup similar to macOS Internet Sharing approach.

---

## CLI Usage

```bash
# USB connection with random credentials
televoodoo --connection usb

# USB connection with static credentials
televoodoo --connection usb --name myrobot --code ABC123

# USB with custom port
televoodoo --connection usb --wifi-port 51000
```

---

## Python API

```python
from televoodoo import start_televoodoo

def on_event(evt):
    if evt.get("type") == "pose":
        print(f"Pose: {evt['data']}")

# USB connection with random credentials
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

## USB Interface Detection

Televoodoo automatically detects USB network interfaces by looking for IP addresses in known ranges:

| Setup | Typical IP Range | Notes |
|-------|------------------|-------|
| macOS Internet Sharing (iOS) | `192.168.2.x` | Mac at `.1`, iPhone gets DHCP |
| Android USB Tethering | `192.168.42.x` | Phone at `.1` |
| Android (variant) | `192.168.44.x` | Phone at `.1` |
| iOS Personal Hotspot | `172.20.10.x` | May not work reliably on macOS |

### Checking USB Availability

```python
from televoodoo.usb import is_usb_available, get_usb_info

# Check if USB tethering is active
if is_usb_available():
    info = get_usb_info()
    print(f"USB connected via {info['interface']}")
    print(f"Local IP: {info['local_ip']}")
    print(f"Phone IP: {info['phone_ip']}")
    print(f"Platform: {info['platform']}")  # 'android' or 'ios'
else:
    print("No USB tethering detected")
```

---

## QR Code Format

The USB transport uses a QR code format similar to WiFi:

```json
{
  "name": "myrobot",
  "code": "ABC123",
  "transport": "usb",
  "ip": "192.168.42.129",
  "port": 50000,
  "phone_ip": "192.168.42.1"
}
```

The `phone_ip` field helps the app verify it's connected via the correct interface.

---

## Event Format

USB events use the same format as WiFi, with `usb_` prefix:

```python
# Connection established
{"type": "usb_connected", "client": "192.168.42.1:51234"}

# Pose data
{"type": "pose", "data": {"absolute_input": {...}}}

# Disconnection
{"type": "usb_disconnected", "reason": "timeout"}  # or "bye"
```

---

## Technical Details

### How USB Networking Works

**macOS Internet Sharing (recommended for iOS):**
1. Mac creates a bridge network interface (`bridge100`)
2. Mac acts as router/DHCP server at `192.168.2.1`
3. iPhone receives an IP via DHCP (e.g., `192.168.2.x`)
4. Standard TCP/UDP networking works over this interface

**Android USB Tethering:**
1. Phone creates a virtual network interface over USB
2. Computer sees a new network interface (e.g., `en5` on macOS, `usb0` on Linux)
3. Phone runs a DHCP server, assigning an IP to the computer
4. Standard TCP/UDP networking works over this interface

### Differences from WiFi

| Aspect | WiFi | USB |
|--------|------|-----|
| Discovery | mDNS on LAN | Direct IP (interface detection) |
| Latency | ~16ms | ~5-10ms |
| Reliability | Depends on WiFi | Very stable |
| Setup | Same network required | Cable + Internet Sharing/Tethering |
| mDNS | Enabled | Disabled (not needed) |

### Why No mDNS for USB?

USB creates a point-to-point network between phone and computer. The IP addresses are predictable based on the setup method, so mDNS discovery is unnecessary. This also simplifies the connection flow.

---

## Troubleshooting

### "No USB tethering interface detected"

1. **For iOS on macOS**: Verify **Internet Sharing** is enabled in System Settings → General → Sharing
2. **For Android**: Verify **USB Tethering** is enabled on the phone
3. **Check the cable** - use a data-capable USB cable (not charge-only)
4. **Wait a few seconds** after enabling for the interface to appear
5. **Check System Settings → Network** (macOS) or Network Manager (Linux) for new interfaces

### macOS + iOS: No network interface appears

1. Make sure **Internet Sharing** is configured correctly:
   - Share from: Wi-Fi (or your internet source)
   - To computers using: iPhone USB (must be checked)
2. Toggle Internet Sharing off and on again
3. Disconnect and reconnect the iPhone
4. Check that iPhone shows "Trust This Computer" and tap Trust

### Connection times out

1. **Verify the phone app** is connecting to the correct IP (shown in QR code)
2. **For iOS**: The QR code should show `192.168.2.1` (Mac's bridge IP)
3. **Check firewall** - ensure UDP port 50000 is not blocked
4. **Try a different port**: `--wifi-port 51000`

### iOS: "Trust This Computer" not appearing

1. Disconnect and reconnect the USB cable
2. Unlock the iPhone before connecting
3. On Mac, check System Information → USB to verify the phone is recognized

### Linux: USB interface not appearing for iOS

Install the required packages:
```bash
sudo apt install libimobiledevice6 usbmuxd
sudo systemctl enable usbmuxd
sudo systemctl start usbmuxd
```

Reconnect the iPhone after installing.

### Android: USB Tethering option grayed out

1. Enable **Developer Options** on your phone
2. Enable **USB Debugging** in Developer Options
3. Reconnect the USB cable
4. Select "USB Tethering" mode when connecting

---

## See Also

- **WIFI_API.md**: WiFi/UDP protocol details (shared with USB)
- **BLE_API.md**: Bluetooth Low Energy connection
- **CONNECTION_SETUP.md**: General connection guide
- **HAPTIC_FEEDBACK_API.md**: Haptic feedback works with USB
