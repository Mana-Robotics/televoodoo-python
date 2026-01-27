# Televoodoo Multi-Transport Pose Streaming Specification

**Version**: 1.0-draft  
**Status**: Draft  
**Last Updated**: 2026-01-26

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [Design Goals](#3-design-goals)
4. [Platform Support Matrix](#4-platform-support-matrix)
5. [Architecture](#5-architecture)
6. [Transport Layer](#6-transport-layer)
7. [Discovery Protocol](#7-discovery-protocol)
8. [Binary Protocol](#8-binary-protocol)
9. [Session Management](#9-session-management)
10. [Connection State Machine](#10-connection-state-machine)
11. [Version Negotiation](#11-version-negotiation)
12. [Error Handling](#12-error-handling)
13. [Performance Guidelines](#13-performance-guidelines)
14. [Security Considerations](#14-security-considerations)
15. [Implementation Checklist](#15-implementation-checklist)

---

## 1. Overview

Televoodoo streams 6-DoF pose data from a mobile device (iOS/Android) to a host computer (macOS/Windows/Linux) for robot teleoperation. This specification defines a transport-agnostic protocol that works identically across WiFi, USB, and BLE transports.

### Key Principles

- **Transport agnostic**: Same binary protocol regardless of physical transport
- **TCP for data**: Reliable, ordered delivery with low-latency tuning (WiFi/USB)
- **Newest pose wins**: Application-level semantics; no backpressure
- **Single client**: One mobile device per Televoodoo service instance
- **Auto-reconnect**: Sessions resume automatically after disconnections
- **Simple discovery**: UDP broadcast beacons (no mDNS dependency)

---

## 2. Problem Statement

The original approach had transport-specific issues:

| Constraint | Impact |
|------------|--------|
| iOS doesn't support UDP over USB to Linux | Required different protocol per platform |
| mDNS/multicast is fragile on Linux WiFi hotspots | Discovery fails silently |
| USB tethering network topology varies by platform | iOS and Android require opposite configurations |
| UDP packet loss handling adds complexity | Sequence tracking, timeout guessing |
| BLE has MTU constraints | Requires characteristic-based design |

### Solution: TCP for Data, UDP for Discovery

Using TCP for data transport solves the key issues:

| Benefit | Rationale |
|---------|-----------|
| Works everywhere | TCP works over usbmuxd (Linux + iOS), all network types |
| Connection state for free | No timeout guessing; TCP knows when connection drops |
| Ordered delivery | No sequence number tracking needed |
| Simple session model | TCP connection = session |
| Negligible latency overhead | <0.5ms on LAN with proper tuning |

UDP is only used for discovery beacons (stateless, simple).

---

## 3. Design Goals

### Must Have

| Goal | Rationale |
|------|-----------|
| Ultra-low latency | Force feedback loops require <20ms round-trip |
| Identical pose semantics across transports | Application code should not care about transport |
| Minimal dependencies | No mDNS libraries, no complex network stacks |
| Works on all platform combinations | Including Linux + iOS USB (usbmuxd) |
| Auto-reconnect without user intervention | Production deployments need resilience |

### Should Have

| Goal | Rationale |
|------|-----------|
| Clear separation of concerns | Future transports (QUIC, WebRTC) can be added |
| Graceful degradation | Fallback when preferred transport unavailable |
| Cross-platform consistency | Same experience on macOS, Windows, Linux |

### Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| WAN/NAT traversal | Local network only |
| Encryption (for now) | Adds latency, complexity; may revisit |
| Multi-client support | Single operator per robot |
| Windows BLE | Platform limitations, low priority |

---

## 4. Platform Support Matrix

### Transport Availability

| Host \ Mobile | iOS | Android |
|---------------|-----|---------|
| **macOS** | WiFi ✅, USB ✅, BLE ✅ | WiFi ✅, USB ✅, BLE ✅ |
| **Linux** | WiFi ✅, USB ✅, BLE ✅ | WiFi ✅, USB ✅, BLE ✅ |
| **Windows** | WiFi ✅, USB ✅ | WiFi ✅, USB ✅ |

### USB Transport Mechanism

| Platform Pair | Mechanism | Notes |
|---------------|-----------|-------|
| macOS + iOS | MobileDevice framework | TCP tunnel, built into macOS |
| macOS + Android | USB Tethering | Creates network interface, standard TCP |
| Linux + iOS | usbmuxd | TCP tunnel via `libimobiledevice` |
| Linux + Android | USB Tethering | Creates `usb0` interface, standard TCP |
| Windows + iOS | Apple Mobile Device Service | TCP tunnel via iTunes drivers |
| Windows + Android | USB Tethering | RNDIS driver, standard TCP |

**Key insight:** iOS always uses TCP tunneling (no network interface). Android always uses USB Tethering (creates network interface). The protocol is TCP in both cases.

### USB Configuration Requirements

| Host | Mobile | Host Setup | Mobile Setup |
|------|--------|------------|--------------|
| **macOS** | iOS | None (built-in) | Just connect cable, tap "Trust" |
| **macOS** | Android | None | USB Tethering ON |
| **Linux** | iOS | `sudo apt install libimobiledevice6 usbmuxd` | Just connect cable, tap "Trust" |
| **Linux** | Android | None | USB Tethering ON |
| **Windows** | iOS | iTunes installed (provides drivers) | Just connect cable, tap "Trust" |
| **Windows** | Android | None | USB Tethering ON |

**iOS uses TCP tunneling** via the MobileDevice framework (macOS built-in) or `usbmuxd` (Linux/Windows). No network interface configuration needed—just plug in the cable.

**Android uses USB Tethering** which creates a standard network interface. The host connects via normal TCP over this interface.

### BLE Availability

BLE is an **optional fallback** transport, manually activated when WiFi/USB are unavailable:

| Host | BLE Support | Notes |
|------|-------------|-------|
| macOS | ✅ Full | CoreBluetooth, works reliably |
| Linux | ✅ Requires setup | BlueZ + D-Bus, `sudo apt install libdbus-1-dev libglib2.0-dev` |
| Windows | ❌ Not supported | Non-goal for this version |

---

## 5. Architecture

### Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  - Pose callbacks                                           │
│  - Command handling                                         │
│  - Config management                                        │
├─────────────────────────────────────────────────────────────┤
│  Session Layer                                              │
│  - Authentication (HELLO/ACK exchange)                      │
│  - Connection lifecycle                                     │
│  - Reconnection logic                                       │
├─────────────────────────────────────────────────────────────┤
│  Protocol Layer                                             │
│  - Binary message encoding/decoding                         │
│  - TCP framing (length prefix)                              │
│  - Message routing                                          │
├─────────────────────────────────────────────────────────────┤
│  Transport Layer                                            │
│  - WiFi / USB: TCP (with low-latency tuning)                │
│  - BLE: GATT characteristics                                │
├─────────────────────────────────────────────────────────────┤
│  Discovery Layer (separate)                                 │
│  - UDP broadcast beacons                                    │
│  - BLE advertising                                          │
└─────────────────────────────────────────────────────────────┘
```

### Transport Abstraction

All transports implement a common interface:

```python
class Transport(Protocol):
    def send(self, data: bytes) -> None: ...
    def recv(self) -> bytes | None: ...
    def is_connected(self) -> bool: ...
    def close(self) -> None: ...
    
    # Transport-specific
    def get_remote_address(self) -> str: ...
```

The application layer never directly accesses transport-specific APIs.

---

## 6. Transport Layer

### 6.1 TCP Transport (WiFi / USB)

**Characteristics:**
- Low latency with proper tuning (~16ms WiFi, ~5-10ms USB)
- Connection-oriented (connection = session)
- Reliable, ordered delivery
- Works everywhere including usbmuxd tunnels

**Architecture:**
- Host listens on TCP port (default 50000)
- Mobile connects to discovered host IP:port
- Single connection per session

**Host Socket Setup:**
```python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 50000))
server.listen(1)  # Single client

# Accept connection
conn, addr = server.accept()

# Low-latency tuning (critical!)
conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
conn.setblocking(False)
```

**Mobile Socket Setup:**
```swift
// iOS example
let connection = NWConnection(host: host, port: port, using: .tcp)
connection.parameters.requiredInterfaceType = .wiredEthernet  // Prefer USB if available
// Enable TCP_NODELAY via NWProtocolTCP.Options
```

**TCP_NODELAY is Critical:**
Without `TCP_NODELAY`, Nagle's algorithm buffers small packets (our 46-byte POSE) waiting for more data. This adds up to 200ms latency. Always disable Nagle.

### 6.2 TCP Framing

Since TCP is a stream (not datagrams), messages need framing.

**Frame Format:**

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | `length` | `uint16` | Payload length (little-endian) |
| 2 | `payload` | `bytes` | Binary message (HELLO, POSE, etc.) |

**Example: POSE packet on wire**
```
[0x2E 0x00] [TELE header + pose data...]
 └─ length=46 (little-endian)
```

**Reading Messages (Host):**
```python
def read_message(conn: socket.socket) -> bytes | None:
    # Read 2-byte length prefix
    length_bytes = recv_exact(conn, 2)
    if not length_bytes:
        return None
    length = struct.unpack("<H", length_bytes)[0]
    
    # Read payload
    return recv_exact(conn, length)

def recv_exact(conn: socket.socket, n: int) -> bytes | None:
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None  # Connection closed
        data += chunk
    return data
```

**Writing Messages (Mobile):**
```python
def send_message(conn: socket.socket, payload: bytes) -> None:
    length = struct.pack("<H", len(payload))
    conn.sendall(length + payload)
```

### 6.3 USB via TCP Tunneling (iOS)

iOS devices use TCP tunneling over USB on all platforms. The tunnel is provided by:

| Platform | Tunnel Provider | Setup |
|----------|----------------|-------|
| macOS | MobileDevice.framework | Built-in, no setup needed |
| Linux | usbmuxd | `sudo apt install libimobiledevice6 usbmuxd` |
| Windows | Apple Mobile Device Service | Installed with iTunes |

**How it works:**
1. Host opens a tunnel to the iOS device on a specific port
2. Mobile app listens on that port
3. Host connects via the tunnel as if it were a local TCP socket

**Linux example with iproxy:**
```bash
# Start usbmuxd (if not running)
sudo systemctl start usbmuxd

# Forward local port 50000 to iOS device port 50000
iproxy 50000 50000 &

# Now connect to localhost:50000
```

**macOS:** Uses the MobileDevice framework directly (same APIs Xcode uses). No `iproxy` needed—the framework handles tunneling internally.

From the protocol's perspective, this is just TCP—no special handling needed in the application layer.

### 6.4 BLE Transport

**Characteristics:**
- Higher latency (~32ms effective)
- Lower bandwidth (~30 Hz pose updates)
- Works without network infrastructure
- **Optional fallback only**, manually activated

**Architecture:**
- Host runs as BLE **peripheral** (GATT server)
- Mobile connects as **central** (GATT client)
- Data flows via characteristic writes/notifications
- No TCP framing (each characteristic write is a complete message)

**Service Definition:**

| UUID Suffix | Name | Properties | Direction |
|-------------|------|------------|-----------|
| `...AEF61` | Service | - | - |
| `...AEF63` | Auth | Write | Mobile → Host |
| `...AEF64` | Pose | Write, WriteWithoutResponse | Mobile → Host |
| `...AEF65` | Heartbeat | Read, Notify | Host → Mobile |
| `...AEF66` | Command | Write, WriteWithoutResponse | Mobile → Host |
| `...AEF67` | Haptic | Read, Notify | Host → Mobile |
| `...AEF68` | Config | Read, Notify | Host → Mobile |

Full UUIDs use base `1C8FD138-FC18-4846-954D-E509366AEF6x`.

**MTU Requirement:**
- POSE packet is 46 bytes
- Minimum MTU must be negotiated to ≥64 bytes
- Most modern devices support 185+ bytes

---

## 7. Discovery Protocol

### 7.1 Design Rationale

**Why not mDNS:**
- Fragile on Linux WiFi hotspots (multicast routing issues)
- Requires `zeroconf` library dependency
- Windows requires Bonjour service installation
- Hard to debug when it fails silently

**UDP Broadcast for Discovery:**
- Zero dependencies (standard sockets)
- Works on point-to-point networks (USB tethering)
- Easy to debug with packet capture
- Only used for discovery, not data

### 7.2 Beacon Protocol (WiFi/USB)

The host broadcasts discovery beacons; the mobile listens and filters by service name.

**Beacon Packet (no TCP framing, just raw UDP):**

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | `magic` | `char[4]` | `"TELE"` |
| 4 | `msg_type` | `uint8` | `8` (BEACON) |
| 5 | `version` | `uint8` | Protocol version |
| 6 | `port` | `uint16` | TCP data port (e.g., 50000) |
| 8 | `name_len` | `uint8` | Length of service name |
| 9 | `reserved` | `uint8` | Must be 0 |
| 10 | `name` | `char[n]` | Service name (UTF-8) |

**Total size:** 10 + name_len bytes

**Beacon Transmission:**
```python
# Host broadcasts every 500ms
beacon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
beacon_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

while running:
    beacon = pack_beacon(name="myvoodoo", port=50000)
    beacon_sock.sendto(beacon, ("255.255.255.255", 50001))
    time.sleep(0.5)
```

**Mobile Discovery Flow:**
1. Listen for UDP beacons on port 50001
2. Filter beacons where `name` matches QR code
3. Extract host IP from UDP source address
4. Connect via TCP to `host_ip:<port>` from beacon

**Fallback Priority:**
1. Try last-known IP directly (fast reconnect)
2. Listen for beacons (3 second timeout)
3. Manual IP entry in app settings (ultimate fallback)

### 7.3 BLE Discovery

BLE uses native Bluetooth scanning:

1. Host advertises peripheral with local name = service name
2. Mobile scans for peripherals
3. Mobile filters by name matching QR code
4. Mobile connects to matching peripheral

No custom discovery protocol needed.

---

## 8. Binary Protocol

### 8.1 Design Principles

- **Little-endian** byte order (native to ARM/x86)
- **Fixed-size messages** where possible (O(1) parsing)
- **Magic header** for validation
- **Version field** for compatibility
- **TCP framing**: All messages wrapped with 2-byte length prefix

### 8.2 Common Header (6 bytes)

All messages start with this header:

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | `magic` | `char[4]` | `"TELE"` (0x54 0x45 0x4C 0x45) |
| 4 | `msg_type` | `uint8` | Message type ID |
| 5 | `version` | `uint8` | Protocol version (currently `1`) |

### 8.3 Message Types

| ID | Name | Direction | Transport | Size |
|----|------|-----------|-----------|------|
| 1 | HELLO | Mobile → Host | TCP | 18 |
| 2 | ACK | Host → Mobile | TCP | 12 |
| 3 | POSE | Mobile → Host | All | 46 |
| 4 | BYE | Mobile → Host | TCP | 10 |
| 5 | CMD | Mobile → Host | All | 8 |
| 6 | HEARTBEAT | Host → Mobile | BLE only | 14 |
| 7 | HAPTIC | Host → Mobile | All | 12 |
| 8 | BEACON | Host → Broadcast | UDP only | 10+n |
| 9 | CONFIG | Host → Mobile | All | 8+n |

### 8.4 Message Formats

#### HELLO (Mobile → Host)

Sent immediately after TCP connection is established.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | session_id | `uint32` | 4 | Random ID for this session |
| 10 | code | `char[6]` | 6 | Authentication code |
| 16 | reserved | `uint16` | 2 | Must be 0 |
| **Total** | | | **18** | |

**Note:** Unlike UDP, HELLO is only sent once at connection start. TCP connection state handles liveness.

#### ACK (Host → Mobile)

Response to HELLO.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | status | `uint8` | 1 | Status code |
| 7 | reserved | `uint8` | 1 | Must be 0 |
| 8 | min_version | `uint8` | 1 | Minimum supported version |
| 9 | max_version | `uint8` | 1 | Maximum supported version |
| 10 | reserved2 | `uint16` | 2 | Must be 0 |
| **Total** | | | **12** | |

**Status Codes:**

| Code | Name | Description |
|------|------|-------------|
| 0 | OK | Session established |
| 1 | BAD_CODE | Authentication failed |
| 2 | BUSY | Another client is connected |
| 3 | VERSION_MISMATCH | Protocol version not supported |

After `ACK(OK)`, host sends `CONFIG` message with initial configuration.

#### POSE (Mobile → Host)

Core pose data. Streamed at up to 60 Hz.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | seq | `uint16` | 2 | Sequence number (wraps at 65535) |
| 8 | timestamp_us | `uint64` | 8 | Microseconds since session start |
| 16 | flags | `uint8` | 1 | Bitfield (see below) |
| 17 | reserved | `uint8` | 1 | Must be 0 |
| 18 | x | `float32` | 4 | Position X (meters) |
| 22 | y | `float32` | 4 | Position Y (meters) |
| 26 | z | `float32` | 4 | Position Z (meters) |
| 30 | qx | `float32` | 4 | Quaternion X |
| 34 | qy | `float32` | 4 | Quaternion Y |
| 38 | qz | `float32` | 4 | Quaternion Z |
| 42 | qw | `float32` | 4 | Quaternion W |
| **Total** | | | **46** | |

**Flags Bitfield:**

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `movement_start` | New movement origin (reset deltas) |
| 1-7 | reserved | Must be 0 |

**Python Struct:** `"<4sBBHQBB7f"`

**Sequence Number:** Used for diagnostics (detecting if poses are being dropped in application layer). TCP guarantees delivery, but the application might not process fast enough.

#### BYE (Mobile → Host)

Graceful session close (optional; TCP close also ends session).

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | session_id | `uint32` | 4 | Session ID from HELLO |
| **Total** | | | **10** | |

#### CMD (Mobile → Host)

Command signals.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | cmd_type | `uint8` | 1 | Command type |
| 7 | value | `uint8` | 1 | Command value |
| **Total** | | | **8** | |

**Command Types:**

| ID | Name | Values |
|----|------|--------|
| 1 | RECORDING | 1=start, 0=stop |
| 2 | KEEP_RECORDING | 1=keep, 0=discard |

#### HEARTBEAT (Host → Mobile, BLE only)

Liveness signal for BLE connections.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | counter | `uint32` | 4 | Increments each heartbeat |
| 10 | uptime_ms | `uint32` | 4 | Milliseconds since host started |
| **Total** | | | **14** | |

Sent at **2 Hz** (every 500ms). Not needed for TCP (connection state is implicit).

#### HAPTIC (Host → Mobile)

Haptic feedback signal.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | intensity | `float32` | 4 | 0.0 (off) to 1.0 (max) |
| 10 | channel | `uint8` | 1 | Reserved (always 0) |
| 11 | reserved | `uint8` | 1 | Must be 0 |
| **Total** | | | **12** | |

**Python Struct:** `"<4sBBfBB"`

#### BEACON (Host → Broadcast, UDP only)

Discovery beacon. See [Section 7.2](#72-beacon-protocol-wifiusb).

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | port | `uint16` | 2 | TCP data port |
| 8 | name_len | `uint8` | 1 | Service name length |
| 9 | reserved | `uint8` | 1 | Must be 0 |
| 10 | name | `char[n]` | n | Service name (UTF-8) |
| **Total** | | | **10+n** | |

**Note:** BEACON is sent via UDP broadcast, not TCP. No length prefix framing.

#### CONFIG (Host → Mobile)

Runtime configuration update.

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | header | - | 6 | Common header |
| 6 | config_len | `uint16` | 2 | JSON payload length |
| 8 | config | `char[n]` | n | JSON payload (UTF-8) |
| **Total** | | | **8+n** | |

**Config Payload Example:**

```json
{
  "ui": {
    "show_gripper": true,
    "gripper_range": [0.0, 1.0]
  }
}
```

CONFIG is sent:
- Once after successful `ACK(OK)` (initial config)
- When configuration changes at runtime

---

## 9. Session Management

### 9.1 Session Lifecycle (TCP)

With TCP, session management is dramatically simplified:

```
┌─────────────────────────────────────────────────────────────────┐
│                         DISCONNECTED                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │ Mobile discovers host
                                │ (beacon or last-known IP)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TCP CONNECTING                             │
│  - Mobile opens TCP connection to host:port                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ TCP connected
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATING                            │
│  - Mobile sends HELLO with auth code                            │
│  - Host validates code, sends ACK                               │
└───────────────────────────────┬─────────────────────────────────┘
                                │ ACK(status=OK)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          CONNECTED                              │
│  - Host sends CONFIG                                            │
│  - Mobile begins streaming POSE (up to 60 Hz)                   │
│  - Host sends HAPTIC as needed                                  │
│  - Mobile sends CMD as needed                                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ TCP close, error, or BYE
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DISCONNECTED                            │
│  - Mobile attempts auto-reconnect                               │
└─────────────────────────────────────────────────────────────────┘
```

**Key Simplification:** No HELLO keepalives needed. TCP handles liveness detection automatically via:
- TCP keepalive probes (OS-level)
- Immediate notification on connection close/reset

### 9.2 Single-Client Exclusivity

Only one TCP connection is accepted at a time.

| Scenario | Host Behavior |
|----------|---------------|
| New TCP connection while session active | Accept connection, send `ACK(BUSY)`, close |
| New connection after previous closed | Accept, normal auth flow |
| Same client reconnects (previous connection closed) | Accept, normal auth flow |

### 9.3 Liveness Detection

| Transport | Mechanism | Detection Time |
|-----------|-----------|----------------|
| TCP | TCP keepalive + connection state | Configurable (typically 10-30s for keepalive, immediate for RST) |
| BLE | HEARTBEAT notifications | 3 seconds |

**TCP Keepalive Tuning (optional, for faster detection):**
```python
# Linux: detect dead connection faster
conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)   # Start probes after 5s idle
conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)  # Probe every 1s
conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)    # 3 failed probes = dead
```

### 9.4 Auto-Reconnection

When TCP connection is lost, mobile attempts automatic reconnection:

1. **Immediate retry** (0-500ms): Network glitch, likely to succeed
2. **Fast retry** (500ms-5s): Retry every 500ms
3. **Slow retry** (5s+): Retry every 2s, indefinitely

**Reconnection uses:**
- Same credentials (name, code) from last session
- Last-known host IP (try first, before beacon discovery)
- Same transport (try first, then fallback order)

**Transport Fallback Order:**
1. Last-used transport
2. USB
3. WiFi
4. BLE (if enabled)

---

## 10. Connection State Machine

### 10.1 Mobile State Machine

```
                              ┌──────────────┐
                              │   INITIAL    │
                              └──────┬───────┘
                                     │ QR scanned or
                                     │ auto-reconnect
                                     ▼
              ┌─────────────────────────────────────────┐
              │              DISCOVERING                │
              │  - Try last-known IP (TCP connect)      │
              │  - Listen for UDP beacons               │
              └──────────────────┬──────────────────────┘
                                 │ TCP connection established
                                 ▼
              ┌─────────────────────────────────────────┐
              │              AUTHENTICATING             │
              │  - Send HELLO                           │
              │  - Wait for ACK                         │
              └─────┬───────────────────────────┬───────┘
                    │ ACK(OK)                   │ ACK(error) or timeout
                    ▼                           ▼
┌───────────────────────────────┐    ┌──────────────────────────────┐
│           CONNECTED           │    │           ERROR              │
│  - Receive CONFIG             │    │  - Display error to user     │
│  - Start streaming POSE       │    │  - May retry or abort        │
│  - Process HAPTIC             │    └──────────────────────────────┘
│  - Send CMD as needed         │
└───────────────┬───────────────┘
                │ TCP closed or error
                ▼
┌───────────────────────────────┐
│         RECONNECTING          │
│  - Retry with backoff         │
│  - Try last-known IP first    │
└───────────────────────────────┘
```

### 10.2 Host State Machine

```
              ┌─────────────────────────────────────────┐
              │              LISTENING                  │
              │  - TCP server listening on port         │
              │  - Broadcasting UDP beacons             │
              └──────────────────┬──────────────────────┘
                                 │ TCP connection accepted
                                 ▼
              ┌─────────────────────────────────────────┐
              │          AWAITING_HELLO                 │
              │  - Wait for HELLO (timeout: 5s)         │
              └─────┬───────────────────────────┬───────┘
                    │ Valid HELLO               │ Timeout or invalid
                    ▼                           ▼
              ┌─────────────────────────────────────────┐
              │              CONNECTED                  │
              │  - Send ACK(OK)                         │
              │  - Send CONFIG                          │
              │  - Process POSE/CMD                     │
              │  - Send HAPTIC as needed                │
              └─────┬───────────────────────────────────┘
                    │ TCP close or BYE
                    ▼
              ┌─────────────────────────────────────────┐
              │              LISTENING                  │
              │  - Ready for new connection             │
              └─────────────────────────────────────────┘
```

---

## 11. Version Negotiation

### 11.1 Protocol Versioning

The protocol version is carried in every message header (byte 5).

**Current version:** `1`

### 11.2 Compatibility Check

Version is checked in the HELLO message:

1. Mobile sends HELLO with its protocol version
2. Host checks if version is supported
3. If not supported: `ACK(VERSION_MISMATCH)` with supported range
4. Mobile displays: "Server supports protocol v1-2, you have v3. Please update."

### 11.3 ACK Version Fields

```
ACK {
  status: VERSION_MISMATCH,
  min_version: 1,
  max_version: 2,
}
```

### 11.4 Version Bump Policy

| Change Type | Version Impact |
|-------------|----------------|
| New optional message type | No bump (backward compatible) |
| New optional field in existing message | No bump (use reserved bytes) |
| Change to existing field semantics | Major bump |
| Remove message type | Major bump |

---

## 12. Error Handling

### 12.1 Connection Errors

| Condition | Host Behavior | Mobile Behavior |
|-----------|---------------|-----------------|
| TCP connection refused | N/A | Try next discovery method |
| TCP connection reset | Close session, emit event | Attempt reconnection |
| TCP timeout (no data) | Rely on TCP keepalive | Rely on TCP keepalive |
| BLE disconnect | Close session, emit event | Attempt reconnection |

### 12.2 Protocol Errors

| Condition | Host Behavior | Mobile Behavior |
|-----------|---------------|-----------------|
| Wrong magic (`!= "TELE"`) | Close connection | Close connection |
| Unknown message type | Log warning, ignore message | Log warning, ignore message |
| Invalid length prefix | Close connection | Close connection |
| Wrong version | `ACK(VERSION_MISMATCH)`, close | Show error to user |
| Wrong auth code | `ACK(BAD_CODE)`, close | Show error to user |
| Busy (other client) | `ACK(BUSY)`, close | Show error, retry later |

### 12.3 Logging Levels

| Level | When to Use |
|-------|-------------|
| ERROR | Connection failures, auth failures |
| WARN | Protocol errors, unexpected messages |
| INFO | Connect/disconnect events |
| DEBUG | Individual messages (rate-limited) |

---

## 13. Performance Guidelines

### 13.1 Latency Targets

| Transport | Target E2E Latency | Typical Frequency |
|-----------|-------------------|-------------------|
| WiFi (TCP) | <20ms | 60 Hz |
| USB (TCP) | <10ms | 60 Hz |
| BLE | <50ms | 30 Hz |

E2E latency = time from ARKit pose update to robot command sent.

### 13.2 Critical TCP Tuning

**Disable Nagle's Algorithm (MANDATORY):**
```python
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
```
Without this, small packets are buffered for up to 200ms.

**Optional: TCP_QUICKACK (Linux):**
```python
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
```
Disables delayed ACKs for even lower latency.

**Socket Buffer Sizing:**
```python
# Smaller buffers = lower latency (less buffering delay)
# But too small = dropped data under burst
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32768)
```

### 13.3 Receive Loop

```python
def receive_loop(conn: socket.socket):
    while True:
        msg = read_message(conn)
        if msg is None:
            break  # Connection closed
        
        msg_type = msg[4]  # Byte 4 is msg_type
        if msg_type == MSG_POSE:
            # Process immediately, don't queue
            process_pose(msg)
        elif msg_type == MSG_CMD:
            process_command(msg)
        # ... etc
```

**Key principles:**
- Process messages immediately in receive thread
- No queuing (avoids latency)
- Caller handles thread safety if needed

### 13.4 Benchmarking

Use the `measure_frequency.py` example to validate:
- Actual receive frequency (should be ~60 Hz)
- Inter-packet jitter
- Sequence number gaps (application not keeping up)

---

## 14. Security Considerations

### 14.1 Current Model

| Aspect | Current State | Risk |
|--------|---------------|------|
| Authentication | 6-char code | Brute-forceable (36^6 = 2B combinations) |
| Encryption | None | Data visible on network |
| Integrity | Magic header only | No cryptographic integrity |

### 14.2 Mitigations

| Risk | Mitigation |
|------|------------|
| Code guessing | Close connection after 3 failed attempts |
| Eavesdropping | Use USB (point-to-point) for sensitive deployments |
| Replay attacks | Session ID prevents cross-session replay |

### 14.3 Future Considerations

For production deployments requiring security:
- TLS for TCP connections (adds ~2-5ms handshake, negligible per-message)
- BLE encryption (handled by stack)
- Certificate-based auth (eliminates codes)

---

## 15. Implementation Checklist

### 15.1 Host (Python) Implementation

- [ ] **Transport Layer**
  - [ ] TCP server (listen, accept, low-latency tuning)
  - [ ] TCP framing (length prefix read/write)
  - [ ] BLE peripheral (macOS CoreBluetooth, Linux BlueZ)
  - [ ] Transport abstraction interface

- [ ] **Discovery**
  - [ ] UDP beacon broadcast (500ms interval)
  - [ ] BLE advertising with service name

- [ ] **Protocol**
  - [ ] Binary message parsing (all types)
  - [ ] Binary message packing (ACK, HAPTIC, CONFIG, BEACON)
  - [ ] Version validation

- [ ] **Session**
  - [ ] HELLO/ACK handshake
  - [ ] Authentication validation
  - [ ] Single-client enforcement
  - [ ] Graceful close handling

- [ ] **Application**
  - [ ] Pose callback emission
  - [ ] Command callback emission
  - [ ] Connection event emission
  - [ ] Haptic feedback API
  - [ ] Config update API

### 15.2 Mobile (iOS/Android) Implementation

- [ ] **Transport Layer**
  - [ ] TCP client (connect, low-latency tuning)
  - [ ] TCP framing (length prefix read/write)
  - [ ] BLE central (CoreBluetooth / Android BLE)
  - [ ] Transport abstraction interface

- [ ] **Discovery**
  - [ ] UDP beacon listener
  - [ ] Last-known IP storage and direct connect
  - [ ] BLE scanning with name filter

- [ ] **Protocol**
  - [ ] Binary message packing (HELLO, POSE, CMD, BYE)
  - [ ] Binary message parsing (ACK, HAPTIC, CONFIG)
  - [ ] Version validation and error display

- [ ] **Session**
  - [ ] HELLO sending on connect
  - [ ] ACK processing and error handling
  - [ ] Auto-reconnection with backoff
  - [ ] Credential storage for auto-reconnect

- [ ] **Application**
  - [ ] QR code scanning
  - [ ] ARKit pose streaming (60 Hz)
  - [ ] Haptic feedback triggering
  - [ ] Dynamic UI from CONFIG
  - [ ] Recording command sending

### 15.3 Testing Matrix

| Test | WiFi | USB | BLE |
|------|------|-----|-----|
| Discovery (beacon/scan) | ○ | ○ | ○ |
| TCP connect + auth | ○ | ○ | N/A |
| Authentication failure | ○ | ○ | ○ |
| Pose streaming 60 Hz | ○ | ○ | ○ |
| Latency measurement | ○ | ○ | ○ |
| Connection drop detection | ○ | ○ | ○ |
| Auto-reconnection | ○ | ○ | ○ |
| Haptic feedback | ○ | ○ | ○ |
| Config updates | ○ | ○ | ○ |
| Version mismatch | ○ | ○ | ○ |
| Linux + iOS (usbmuxd) | N/A | ○ | N/A |

---

## Appendix A: QR Code Format

```json
{
  "name": "myvoodoo",
  "code": "ABC123",
  "transport": "wifi"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Service name (1-20 chars, alphanumeric + underscore/hyphen) |
| `code` | string | Auth code (exactly 6 chars, uppercase A-Z and 0-9) |
| `transport` | string | `"wifi"`, `"usb"`, or `"ble"` |

**Note:** No IP address is included. Discovery handles finding the host.

---

## Appendix B: Port Assignments

| Port | Protocol | Purpose |
|------|----------|---------|
| 50000 | TCP | Data (HELLO, ACK, POSE, CMD, HAPTIC, CONFIG) |
| 50001 | UDP | Discovery (BEACON broadcast) |

Both ports are configurable via CLI/API.

---

## Appendix C: Byte Order Reference

All multi-byte fields use **little-endian** byte order.

| Type | Size | Python struct |
|------|------|---------------|
| `uint8` | 1 | `B` |
| `uint16` | 2 | `<H` |
| `uint32` | 4 | `<I` |
| `uint64` | 8 | `<Q` |
| `float32` | 4 | `<f` |
| `char[n]` | n | `{n}s` |

---

## Appendix D: Message Size Summary

| Message | Payload Size | On Wire (TCP) |
|---------|-------------|---------------|
| HELLO | 18 bytes | 20 bytes |
| ACK | 12 bytes | 14 bytes |
| POSE | 46 bytes | 48 bytes |
| BYE | 10 bytes | 12 bytes |
| CMD | 8 bytes | 10 bytes |
| HEARTBEAT | 14 bytes | N/A (BLE only) |
| HAPTIC | 12 bytes | 14 bytes |
| BEACON | 10+n bytes | N/A (UDP, no framing) |
| CONFIG | 8+n bytes | 10+n bytes |

"On Wire (TCP)" = payload + 2-byte length prefix.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0-draft | 2026-01-26 | Initial specification with TCP transport |
