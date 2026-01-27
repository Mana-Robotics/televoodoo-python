# WiFi Connection

WiFi is the **default and recommended** connection type. It offers low latency (~16ms) with simple setup.

> For protocol details, see [Protocol Docs](MOBILE_PROTOCOL.md).

## Requirements

- Phone and computer on the **same WiFi network**
- No firewall blocking TCP port 50000 or UDP port 50001

## How It Works

1. Python app starts TCP server on port 50000
2. Python app broadcasts UDP beacons on port 50001
3. Phone app listens for beacons matching the QR code `name`
4. Phone connects via TCP to the beacon's source IP

No IP address is included in the QR code—the phone discovers the server automatically via UDP beacons.

## CLI Usage

```bash
# Default (WiFi is auto-selected)
televoodoo

# Explicit WiFi
televoodoo --connection wifi

# Custom ports
televoodoo --tcp-port 51000 --beacon-port 51001
```

## Python Usage

```python
from televoodoo import start_televoodoo

def on_event(evt):
    if evt.get("type") == "pose":
        print(evt["data"]["absolute_input"])

start_televoodoo(callback=on_event, connection="wifi")
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Phone can't find server | Ensure same WiFi network, check firewall |
| Connection drops | Reduce distance, check for WiFi interference |
| High latency | Switch to USB for lowest latency (~5-10ms) |

## See Also

- **[Protocol Docs](MOBILE_PROTOCOL.md)** — Full protocol specification
- **[Connection & Authentication](CONNECTION_AUTHENTICATION.md)** — QR codes, credentials, troubleshooting
- **[USB API](USB_API.md)** — Lower latency alternative
- **[BLE API](BLE_API.md)** — Bluetooth fallback
