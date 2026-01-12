# Televoodoo BLE Peripheral API v2

## Overview

Televoodoo Python creates a BLE peripheral that the Televoodoo App connects to. This v2 spec uses **binary data format** for pose and command data, matching the WIFI protocol for code reuse.

## Changes from v1

| Change | v1 | v2 |
|--------|----|----|
| Pose data format | JSON string | Binary (same as WIFI POSE) |
| Command data format | JSON string | Binary (same as WIFI CMD) |
| Heartbeat | UInt32 counter | Binary with timestamp |

**Benefit**: Same parsing code works for both BLE and WIFI transports.

---

## BLE Service Configuration

### Service UUID
```
1C8FD138-FC18-4846-954D-E509366AEF61
```

### Characteristics Summary

| # | Name | UUID Suffix | Properties | Format |
|---|------|-------------|------------|--------|
| 1 | Authentication | `...AEF63` | Write | 6-char string |
| 2 | Pose Data | `...AEF64` | Write, WriteWithoutResponse | Binary |
| 3 | Heartbeat | `...AEF65` | Read, Notify | Binary |
| 4 | Command Data | `...AEF66` | Write, WriteWithoutResponse | Binary |

---

## Binary Protocol (Shared with WIFI)

All binary messages use **little-endian** byte order.

### Common Header (6 bytes)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | `magic` | `char[4]` | `"TELE"` |
| 4 | `msg_type` | `uint8` | Message type ID |
| 5 | `version` | `uint8` | Protocol version (`1`) |

### Message Types (BLE subset)

| ID | Name | Direction | Characteristic |
|----|------|-----------|----------------|
| 3 | POSE | iPhone → PC | Pose Data |
| 5 | CMD | iPhone → PC | Command Data |
| 6 | HEARTBEAT | PC → iPhone | Heartbeat |

Note: HELLO/ACK/BYE (types 1, 2, 4) are not used in BLE—connection state is managed by the BLE stack.

---

## Characteristics Detail

### 1. Authentication Characteristic

- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF63`
- **Properties**: Write, WriteWithoutResponse
- **Format**: UTF-8 string (6-character code)

Unchanged from v1. Simple string auth is sufficient for BLE since connection is already established.

**Flow:**
1. App connects to peripheral
2. App writes 6-char code to this characteristic
3. Python validates code
4. If valid, pose data is accepted

### 2. Pose Data Characteristic

- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF64`
- **Properties**: Write, WriteWithoutResponse
- **Format**: Binary POSE packet (46 bytes)

#### POSE Packet (iPhone → PC)

| Offset | Field | Type | Bytes |
|--------|-------|------|-------|
| 0 | header | - | 6 |
| 6 | seq | `uint16` | 2 |
| 8 | timestamp_us | `uint64` | 8 |
| 16 | flags | `uint8` | 1 |
| 17 | reserved | `uint8` | 1 |
| 18 | x | `float32` | 4 |
| 22 | y | `float32` | 4 |
| 26 | z | `float32` | 4 |
| 30 | qx | `float32` | 4 |
| 34 | qy | `float32` | 4 |
| 38 | qz | `float32` | 4 |
| 42 | qw | `float32` | 4 |
| **Total** | | | **46** |

#### Flags Bitfield

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `movement_start` | New movement origin (reset deltas) |
| 1-7 | reserved | Must be 0 |

#### Python Struct

```python
POSE_FORMAT = "<4sBBHQBB7f"  # little-endian, 46 bytes
```

**Note**: This is identical to WIFI POSE format. Same parsing code works for both.

### 3. Heartbeat Characteristic

- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF65`
- **Properties**: Read, Notify
- **Format**: Binary HEARTBEAT packet (14 bytes)

#### HEARTBEAT Packet (PC → iPhone)

| Offset | Field | Type | Bytes |
|--------|-------|------|-------|
| 0 | header | - | 6 |
| 6 | counter | `uint32` | 4 |
| 10 | uptime_ms | `uint32` | 4 |
| **Total** | | | **14** |

- `counter`: Increments with each heartbeat (rollover OK)
- `uptime_ms`: Milliseconds since peripheral started

**Liveness Detection:**
- PC updates heartbeat at **2 Hz** (every 500ms)
- iPhone subscribes to notifications
- If no heartbeat update for **3 seconds** → PC disconnected (or app backgrounded)

### 4. Command Data Characteristic

- **UUID**: `1C8FD138-FC18-4846-954D-E509366AEF66`
- **Properties**: Write, WriteWithoutResponse
- **Format**: Binary CMD packet (8 bytes)

#### CMD Packet (iPhone → PC)

| Offset | Field | Type | Bytes |
|--------|-------|------|-------|
| 0 | header | - | 6 |
| 6 | cmd_type | `uint8` | 1 |
| 7 | value | `uint8` | 1 |
| **Total** | | | **8** |

#### Command Types

| ID | Name | Values |
|----|------|--------|
| 1 | RECORDING | `1`=start, `0`=stop |
| 2 | KEEP_RECORDING | `1`=keep, `0`=discard |

**Note**: This is identical to WIFI CMD format. Same parsing code works for both.

---

## Disconnect Detection

BLE provides connection state natively, but the heartbeat adds app-level liveness:

| Direction | Mechanism | Timeout |
|-----------|-----------|---------|
| iPhone → PC | BLE disconnection event | Immediate |
| PC → iPhone | BLE disconnection event OR heartbeat stops | 3 seconds |

The 3-second heartbeat timeout catches cases where:
- Python app crashes but OS keeps BLE connection alive briefly
- Python app is suspended/paused

---

## Callback Event Format

Same format as WIFI for compatibility:

```python
# Pose event
{
    "type": "pose",
    "data": {
        "absolute_input": {
            "movement_start": True,
            "x": 0.1, "y": 0.2, "z": 0.05,
            "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0,
        }
    }
}

# Command event
{"type": "command", "name": "recording", "value": True}

# Connection events
{"type": "ble_connected"}
{"type": "ble_authenticated"}
{"type": "ble_disconnected"}
```

---

## Shared Parsing Code

Both BLE and WIFI can use the same binary parsing:

```python
import struct

HEADER_FORMAT = "<4sBB"  # magic, msg_type, version
POSE_FORMAT = "<4sBBHQBB7f"
CMD_FORMAT = "<4sBBBB"
HEARTBEAT_FORMAT = "<4sBBII"

def parse_header(data: bytes) -> tuple[bytes, int, int]:
    """Parse common header. Returns (magic, msg_type, version)."""
    return struct.unpack(HEADER_FORMAT, data[:6])

def parse_pose(data: bytes) -> dict:
    """Parse POSE packet to dict matching callback format."""
    magic, msg_type, version, seq, ts, flags, _, x, y, z, qx, qy, qz, qw = \
        struct.unpack(POSE_FORMAT, data)
    
    if magic != b"TELE" or msg_type != 3:
        raise ValueError("Invalid POSE packet")
    
    return {
        "movement_start": bool(flags & 0x01),
        "x": x, "y": y, "z": z,
        "qx": qx, "qy": qy, "qz": qz, "qw": qw,
        "seq": seq,
        "timestamp_us": ts,
    }

def parse_cmd(data: bytes) -> tuple[int, int]:
    """Parse CMD packet. Returns (cmd_type, value)."""
    magic, msg_type, version, cmd_type, value = struct.unpack(CMD_FORMAT, data)
    
    if magic != b"TELE" or msg_type != 5:
        raise ValueError("Invalid CMD packet")
    
    return cmd_type, value

def pack_heartbeat(counter: int, uptime_ms: int) -> bytes:
    """Pack HEARTBEAT packet for BLE characteristic."""
    return struct.pack(HEARTBEAT_FORMAT, b"TELE", 6, 1, counter, uptime_ms)
```

---

## Connection Flow

1. **Python app starts**: Creates BLE peripheral, starts advertising
2. **QR code displayed**: Shows peripheral name + 6-char code
3. **User scans QR**: Televoodoo App discovers and connects
4. **Authentication**: App writes code to Auth characteristic
5. **Heartbeat starts**: Python updates heartbeat at 2 Hz
6. **Pose streaming**: App writes binary POSE packets
7. **Commands**: App writes binary CMD packets as needed
8. **Disconnect**: BLE disconnection OR heartbeat timeout

---

## Backwards Compatibility

During transition, Python can support both v1 (JSON) and v2 (binary) formats:

```python
def handle_pose_write(data: bytes):
    if data[:4] == b"TELE":
        # v2 binary format
        pose = parse_pose(data)
    else:
        # v1 JSON format (legacy)
        pose = json.loads(data.decode("utf-8"))
    
    emit_pose_event(pose)
```

This allows gradual migration of iOS app without breaking existing users.

---

## Packet Size Considerations

BLE MTU is typically 20-512 bytes depending on negotiation. The packets are designed to fit comfortably:

| Packet | Size | Fits in minimum MTU (20 bytes)? |
|--------|------|---------------------------------|
| POSE | 46 bytes | No (needs MTU negotiation) |
| CMD | 8 bytes | Yes |
| HEARTBEAT | 14 bytes | Yes |

**Recommendation**: iOS app should request MTU ≥ 64 bytes during connection. Most modern devices support 185+ bytes.
