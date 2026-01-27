# Televoodoo Mobile Protocol Specification

**Version**: 1.0  
**For**: iOS/Android App Developers

---

## Overview

The mobile app streams 6-DoF pose data to a host computer using either **TCP** (WiFi/USB) or **BLE**. Both transports use the same binary message format.

| Transport | Discovery | Data Transport | Typical Latency |
|-----------|-----------|----------------|-----------------|
| WiFi | UDP beacon | TCP | ~16ms |
| USB | UDP beacon | TCP | ~5-10ms |
| BLE | BLE scan | GATT characteristics | ~32ms |

---

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 50000 | TCP | Data (HELLO, ACK, POSE, CMD, etc.) |
| 50001 | UDP | Discovery (listen for BEACON) |

---

## Discovery

### WiFi/USB: UDP Beacon

The host broadcasts UDP beacons on port **50001**. The mobile app:

1. Listens on UDP port 50001
2. Receives BEACON packets
3. Filters by `name` matching QR code
4. Extracts host IP from UDP source address
5. Connects via TCP to `host_ip:<port>` from beacon

**BEACON packet format** (no length prefix, raw UDP):

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | magic | char[4] | `"TELE"` |
| 4 | msg_type | uint8 | `8` |
| 5 | version | uint8 | `1` |
| 6 | port | uint16 | TCP data port (little-endian) |
| 8 | name_len | uint8 | Service name length |
| 9 | reserved | uint8 | `0` |
| 10 | name | char[n] | Service name (UTF-8) |

### BLE: Scan for Peripheral

Scan for peripherals advertising the Televoodoo service UUID. Filter by local name matching the QR code `name`.

---

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
| name | Service name (1-20 chars) |
| code | Auth code (6 chars, A-Z 0-9) |
| transport | `"wifi"`, `"usb"`, or `"ble"` |

---

## TCP Framing

All TCP messages use a **2-byte little-endian length prefix**:

```
[length: uint16 LE] [payload: bytes]
```

Example: 46-byte POSE → `[0x2E 0x00] [payload...]`

**BLE does not use framing** — each characteristic write is a complete message.

---

## Message Header (6 bytes)

All messages start with:

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | magic | char[4] | `"TELE"` |
| 4 | msg_type | uint8 | Message type ID |
| 5 | version | uint8 | `1` |

---

## Messages: Mobile → Host

### HELLO (18 bytes)

Send immediately after TCP connect (or BLE Auth characteristic write).

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | session_id | uint32 | Random session ID |
| 10 | code | char[6] | Auth code from QR |
| 16 | reserved | uint16 | `0` |

### POSE (46 bytes)

Stream at up to 60 Hz.

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | seq | uint16 | Sequence number (wraps) |
| 8 | timestamp_us | uint64 | Microseconds since session start |
| 16 | flags | uint8 | Bit 0: movement_start |
| 17 | reserved | uint8 | `0` |
| 18 | x, y, z | float32 × 3 | Position (meters) |
| 30 | qx, qy, qz, qw | float32 × 4 | Quaternion (scalar-last) |

**Flags**: Set bit 0 (`0x01`) when user starts a new movement (reset deltas).

### CMD (8 bytes)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | cmd_type | uint8 | Command type |
| 7 | value | uint8 | Command value |

**Command types**:
- `1` = RECORDING: value `1`=start, `0`=stop
- `2` = KEEP_RECORDING: value `1`=keep, `0`=discard

### BYE (10 bytes)

Graceful disconnect (optional).

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | session_id | uint32 | Session ID from HELLO |

---

## Messages: Host → Mobile

### ACK (12 bytes)

Response to HELLO.

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | status | uint8 | Status code |
| 7 | reserved | uint8 | `0` |
| 8 | min_version | uint8 | Host min supported version |
| 9 | max_version | uint8 | Host max supported version |
| 10 | reserved2 | uint16 | `0` |

**Status codes**:
- `0` = OK (success)
- `1` = BAD_CODE (wrong auth code)
- `2` = BUSY (another client connected)
- `3` = VERSION_MISMATCH (update app)

### HAPTIC (12 bytes)

Trigger haptic feedback.

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | intensity | float32 | 0.0 to 1.0 |
| 10 | channel | uint8 | `0` (reserved) |
| 11 | reserved | uint8 | `0` |

### CONFIG (8+n bytes)

Runtime configuration.

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | config_len | uint16 | JSON length |
| 8 | config | char[n] | JSON payload (UTF-8) |

Example config:
```json
{"ui":{"show_gripper":true,"gripper_range":[0.0,1.0]}}
```

### HEARTBEAT (14 bytes, BLE only)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | header | - | 6 bytes |
| 6 | counter | uint32 | Increments each beat |
| 10 | uptime_ms | uint32 | Host uptime |

Sent every 500ms. If not received for 3s, connection is dead.

---

## TCP Session Flow

```
Mobile                              Host
  │                                   │
  │──── TCP Connect ─────────────────▶│
  │                                   │
  │──── HELLO (framed) ─────────────▶│
  │                                   │
  │◀─── ACK (framed) ────────────────│
  │                                   │
  │◀─── CONFIG (framed) ─────────────│ (initial config)
  │                                   │
  │──── POSE (framed, 60 Hz) ───────▶│
  │──── POSE ───────────────────────▶│
  │◀─── HAPTIC (framed) ─────────────│ (as needed)
  │──── CMD (framed) ───────────────▶│ (as needed)
  │     ...                           │
  │                                   │
  │──── BYE (framed) ───────────────▶│ (optional)
  │──── TCP Close ──────────────────▶│
```

---

## BLE Service

**Service UUID**: `1C8FD138-FC18-4846-954D-E509366AEF61`

| UUID Suffix | Name | Properties | Direction |
|-------------|------|------------|-----------|
| `...AEF63` | Auth | Write | Mobile → Host |
| `...AEF64` | Pose | Write, WriteWithoutResponse | Mobile → Host |
| `...AEF65` | Heartbeat | Read, Notify | Host → Mobile |
| `...AEF66` | Command | Write, WriteWithoutResponse | Mobile → Host |
| `...AEF67` | Haptic | Read, Notify | Host → Mobile |
| `...AEF68` | Config | Read, Notify | Host → Mobile |

**BLE Auth Flow**: Write auth code (6 bytes UTF-8) to Auth characteristic. Host validates and starts sending Heartbeat/Config.

---

## TCP Low-Latency Settings (iOS)

```swift
let params = NWParameters.tcp
let tcpOptions = NWProtocolTCP.Options()
tcpOptions.noDelay = true  // Critical: disable Nagle
params.defaultProtocolStack.transportProtocol = tcpOptions

let connection = NWConnection(host: host, port: port, using: params)
```

---

## Auto-Reconnect

On disconnect:
1. Retry immediately (0-500ms)
2. Fast retry: every 500ms for 5s
3. Slow retry: every 2s indefinitely

Use cached credentials and try last-known host IP before beacon discovery.

---

## Byte Order

All multi-byte fields are **little-endian**.

| Type | Size | Swift | Kotlin |
|------|------|-------|--------|
| uint8 | 1 | UInt8 | UByte |
| uint16 | 2 | UInt16 (LE) | UShort (LE) |
| uint32 | 4 | UInt32 (LE) | UInt (LE) |
| uint64 | 8 | UInt64 (LE) | ULong (LE) |
| float32 | 4 | Float (LE) | Float (LE) |
