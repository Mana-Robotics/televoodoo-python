"""Televoodoo binary protocol - shared by all transports (TCP, BLE).

See Multi-transport-spec.md for the full protocol specification.

All messages use little-endian byte order.
TCP messages are wrapped with a 2-byte length prefix.
BLE messages are sent without framing (each write is a complete message).
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Optional

# Protocol constants
MAGIC = b"TELE"
PROTOCOL_VERSION = 1
MIN_SUPPORTED_VERSION = 1
MAX_SUPPORTED_VERSION = 1

# Default ports
TCP_DATA_PORT = 50000
UDP_BEACON_PORT = 50001

# Struct formats (little-endian)
HEADER_FORMAT = "<4sBB"  # magic(4), msg_type(1), version(1) = 6 bytes
HELLO_FORMAT = "<4sBBI6sH"  # header + session_id(4) + code(6) + reserved(2) = 18 bytes
ACK_FORMAT = "<4sBBBBBBH"  # header + status(1) + reserved(1) + min_version(1) + max_version(1) + reserved2(2) = 12 bytes
POSE_FORMAT = "<4sBBHQBB7f"  # header + seq(2) + ts(8) + flags(1) + reserved(1) + 7 floats = 46 bytes
BYE_FORMAT = "<4sBBI"  # header + session_id(4) = 10 bytes
CMD_FORMAT = "<4sBBBB"  # header + cmd_type(1) + value(1) = 8 bytes
HEARTBEAT_FORMAT = "<4sBBII"  # header + counter(4) + uptime_ms(4) = 14 bytes
HAPTIC_FORMAT = "<4sBBfBB"  # header + intensity(4) + channel(1) + reserved(1) = 12 bytes
BEACON_FORMAT = "<4sBBHBB"  # header + port(2) + name_len(1) + reserved(1) = 10 bytes (+ name)
CONFIG_HEADER_FORMAT = "<4sBBH"  # header + config_len(2) = 8 bytes (+ config JSON)

# Sizes
HEADER_SIZE = 6
HELLO_SIZE = 18
ACK_SIZE = 12
POSE_SIZE = 46
BYE_SIZE = 10
CMD_SIZE = 8
HEARTBEAT_SIZE = 14
HAPTIC_SIZE = 12
BEACON_HEADER_SIZE = 10
CONFIG_HEADER_SIZE = 8


class MsgType(IntEnum):
    """Message type IDs."""
    HELLO = 1
    ACK = 2
    POSE = 3
    BYE = 4
    CMD = 5
    HEARTBEAT = 6
    HAPTIC = 7
    BEACON = 8
    CONFIG = 9


class AckStatus(IntEnum):
    """ACK status codes."""
    OK = 0
    BAD_CODE = 1
    BUSY = 2
    VERSION_MISMATCH = 3


class CmdType(IntEnum):
    """Command type IDs."""
    RECORDING = 1
    KEEP_RECORDING = 2


# Pose flags
FLAG_MOVEMENT_START = 0x01


@dataclass
class Header:
    """Common message header."""
    magic: bytes
    msg_type: int
    version: int

    def is_valid(self) -> bool:
        return self.magic == MAGIC


@dataclass
class HelloMsg:
    """HELLO message (Mobile → Host)."""
    session_id: int
    code: str
    version: int = PROTOCOL_VERSION


@dataclass
class AckMsg:
    """ACK message (Host → Mobile)."""
    status: AckStatus
    min_version: int = MIN_SUPPORTED_VERSION
    max_version: int = MAX_SUPPORTED_VERSION


@dataclass
class PoseMsg:
    """POSE message (Mobile → Host)."""
    seq: int
    timestamp_us: int
    movement_start: bool
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float


@dataclass
class ByeMsg:
    """BYE message (Mobile → Host)."""
    session_id: int


@dataclass
class CmdMsg:
    """CMD message (Mobile → Host)."""
    cmd_type: CmdType
    value: int


@dataclass
class HeartbeatMsg:
    """HEARTBEAT message (Host → Mobile, BLE only)."""
    counter: int
    uptime_ms: int


@dataclass
class HapticMsg:
    """HAPTIC message (Host → Mobile).
    
    Used to trigger haptic feedback on the phone based on robot sensor values.
    The intensity is normalized to 0.0-1.0 range by the sender.
    """
    intensity: float  # 0.0 to 1.0
    channel: int = 0  # Reserved for future use


@dataclass
class BeaconMsg:
    """BEACON message (Host → Broadcast, UDP only).
    
    Discovery beacon broadcast by host for mobile to find the service.
    """
    port: int  # TCP data port
    name: str  # Service name


@dataclass
class ConfigMsg:
    """CONFIG message (Host → Mobile).
    
    Runtime configuration sent after authentication and on config changes.
    """
    config: Dict[str, Any]  # JSON config payload


# =============================================================================
# Parsing functions
# =============================================================================


def parse_header(data: bytes) -> Optional[Header]:
    """Parse common header from bytes.
    
    Returns None if data is too short or invalid.
    """
    if len(data) < HEADER_SIZE:
        return None
    magic, msg_type, version = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return Header(magic=magic, msg_type=msg_type, version=version)


def parse_hello(data: bytes) -> Optional[HelloMsg]:
    """Parse HELLO message."""
    if len(data) < HELLO_SIZE:
        return None
    try:
        magic, msg_type, version, session_id, code_bytes, _ = struct.unpack(HELLO_FORMAT, data[:HELLO_SIZE])
        if magic != MAGIC or msg_type != MsgType.HELLO:
            return None
        # Code is 6 bytes, strip null padding
        code = code_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        return HelloMsg(session_id=session_id, code=code, version=version)
    except Exception:
        return None


def parse_ack(data: bytes) -> Optional[AckMsg]:
    """Parse ACK message."""
    if len(data) < ACK_SIZE:
        return None
    try:
        magic, msg_type, version, status, _, min_ver, max_ver, _ = struct.unpack(ACK_FORMAT, data[:ACK_SIZE])
        if magic != MAGIC or msg_type != MsgType.ACK:
            return None
        return AckMsg(status=AckStatus(status), min_version=min_ver, max_version=max_ver)
    except Exception:
        return None


def parse_pose(data: bytes) -> Optional[PoseMsg]:
    """Parse POSE message."""
    if len(data) < POSE_SIZE:
        return None
    try:
        magic, msg_type, version, seq, ts, flags, _, x, y, z, qx, qy, qz, qw = struct.unpack(POSE_FORMAT, data[:POSE_SIZE])
        if magic != MAGIC or msg_type != MsgType.POSE:
            return None
        return PoseMsg(
            seq=seq,
            timestamp_us=ts,
            movement_start=bool(flags & FLAG_MOVEMENT_START),
            x=x, y=y, z=z,
            qx=qx, qy=qy, qz=qz, qw=qw,
        )
    except Exception:
        return None


def parse_bye(data: bytes) -> Optional[ByeMsg]:
    """Parse BYE message."""
    if len(data) < BYE_SIZE:
        return None
    try:
        magic, msg_type, version, session_id = struct.unpack(BYE_FORMAT, data[:BYE_SIZE])
        if magic != MAGIC or msg_type != MsgType.BYE:
            return None
        return ByeMsg(session_id=session_id)
    except Exception:
        return None


def parse_cmd(data: bytes) -> Optional[CmdMsg]:
    """Parse CMD message."""
    if len(data) < CMD_SIZE:
        return None
    try:
        magic, msg_type, version, cmd_type, value = struct.unpack(CMD_FORMAT, data[:CMD_SIZE])
        if magic != MAGIC or msg_type != MsgType.CMD:
            return None
        return CmdMsg(cmd_type=CmdType(cmd_type), value=value)
    except Exception:
        return None


def parse_beacon(data: bytes) -> Optional[BeaconMsg]:
    """Parse BEACON message."""
    if len(data) < BEACON_HEADER_SIZE:
        return None
    try:
        magic, msg_type, version, port, name_len, _ = struct.unpack(BEACON_FORMAT, data[:BEACON_HEADER_SIZE])
        if magic != MAGIC or msg_type != MsgType.BEACON:
            return None
        if len(data) < BEACON_HEADER_SIZE + name_len:
            return None
        name = data[BEACON_HEADER_SIZE:BEACON_HEADER_SIZE + name_len].decode('utf-8', errors='replace')
        return BeaconMsg(port=port, name=name)
    except Exception:
        return None


def parse_config(data: bytes) -> Optional[ConfigMsg]:
    """Parse CONFIG message."""
    if len(data) < CONFIG_HEADER_SIZE:
        return None
    try:
        magic, msg_type, version, config_len = struct.unpack(CONFIG_HEADER_FORMAT, data[:CONFIG_HEADER_SIZE])
        if magic != MAGIC or msg_type != MsgType.CONFIG:
            return None
        if len(data) < CONFIG_HEADER_SIZE + config_len:
            return None
        config_json = data[CONFIG_HEADER_SIZE:CONFIG_HEADER_SIZE + config_len].decode('utf-8', errors='replace')
        config = json.loads(config_json)
        return ConfigMsg(config=config)
    except Exception:
        return None


def is_binary_protocol(data: bytes) -> bool:
    """Check if data starts with the TELE magic bytes."""
    return len(data) >= 4 and data[:4] == MAGIC


def is_version_supported(version: int) -> bool:
    """Check if a protocol version is supported."""
    return MIN_SUPPORTED_VERSION <= version <= MAX_SUPPORTED_VERSION


# =============================================================================
# Packing functions
# =============================================================================


def pack_ack(status: AckStatus) -> bytes:
    """Pack ACK message."""
    return struct.pack(
        ACK_FORMAT, MAGIC, MsgType.ACK, PROTOCOL_VERSION,
        status, 0, MIN_SUPPORTED_VERSION, MAX_SUPPORTED_VERSION, 0
    )


def pack_heartbeat(counter: int, uptime_ms: int) -> bytes:
    """Pack HEARTBEAT message for BLE characteristic."""
    return struct.pack(HEARTBEAT_FORMAT, MAGIC, MsgType.HEARTBEAT, PROTOCOL_VERSION, counter, uptime_ms)


def pack_pose(
    seq: int,
    timestamp_us: int,
    movement_start: bool,
    x: float, y: float, z: float,
    qx: float, qy: float, qz: float, qw: float,
) -> bytes:
    """Pack POSE message."""
    flags = FLAG_MOVEMENT_START if movement_start else 0
    return struct.pack(
        POSE_FORMAT, MAGIC, MsgType.POSE, PROTOCOL_VERSION,
        seq, timestamp_us, flags, 0,
        x, y, z, qx, qy, qz, qw,
    )


def pack_hello(session_id: int, code: str) -> bytes:
    """Pack HELLO message."""
    code_bytes = code.encode('utf-8')[:6].ljust(6, b'\x00')
    return struct.pack(HELLO_FORMAT, MAGIC, MsgType.HELLO, PROTOCOL_VERSION, session_id, code_bytes, 0)


def pack_bye(session_id: int) -> bytes:
    """Pack BYE message."""
    return struct.pack(BYE_FORMAT, MAGIC, MsgType.BYE, PROTOCOL_VERSION, session_id)


def pack_cmd(cmd_type: CmdType, value: int) -> bytes:
    """Pack CMD message."""
    return struct.pack(CMD_FORMAT, MAGIC, MsgType.CMD, PROTOCOL_VERSION, cmd_type, value)


def pack_haptic(intensity: float, channel: int = 0) -> bytes:
    """Pack HAPTIC message.
    
    Args:
        intensity: Haptic intensity from 0.0 (off) to 1.0 (max)
        channel: Haptic channel (reserved for future use, default 0)
    
    Returns:
        12-byte HAPTIC message
    """
    # Clamp intensity to valid range
    intensity = max(0.0, min(1.0, intensity))
    return struct.pack(HAPTIC_FORMAT, MAGIC, MsgType.HAPTIC, PROTOCOL_VERSION, intensity, channel, 0)


def pack_beacon(name: str, port: int = TCP_DATA_PORT) -> bytes:
    """Pack BEACON message for UDP broadcast.
    
    Args:
        name: Service name (1-20 chars)
        port: TCP data port
    
    Returns:
        BEACON message bytes (10 + name_len bytes)
    """
    name_bytes = name.encode('utf-8')[:255]  # Max 255 chars
    name_len = len(name_bytes)
    header = struct.pack(BEACON_FORMAT, MAGIC, MsgType.BEACON, PROTOCOL_VERSION, port, name_len, 0)
    return header + name_bytes


def pack_config(config: Dict[str, Any]) -> bytes:
    """Pack CONFIG message.
    
    Args:
        config: Configuration dictionary to send as JSON
    
    Returns:
        CONFIG message bytes (8 + config_len bytes)
    """
    config_json = json.dumps(config, separators=(',', ':')).encode('utf-8')
    config_len = len(config_json)
    header = struct.pack(CONFIG_HEADER_FORMAT, MAGIC, MsgType.CONFIG, PROTOCOL_VERSION, config_len)
    return header + config_json


# =============================================================================
# TCP Framing utilities
# =============================================================================


def frame_message(payload: bytes) -> bytes:
    """Frame a message for TCP transport with 2-byte length prefix.
    
    Args:
        payload: Raw message bytes (e.g., from pack_* functions)
    
    Returns:
        Framed message with length prefix
    """
    length = len(payload)
    if length > 65535:
        raise ValueError(f"Message too large for framing: {length} bytes")
    return struct.pack("<H", length) + payload


def read_frame_length(length_bytes: bytes) -> int:
    """Read frame length from 2-byte prefix.
    
    Args:
        length_bytes: 2 bytes containing little-endian length
    
    Returns:
        Payload length
    """
    if len(length_bytes) != 2:
        raise ValueError("Length prefix must be exactly 2 bytes")
    return struct.unpack("<H", length_bytes)[0]


# =============================================================================
# Conversion to callback event format
# =============================================================================


def pose_to_event(pose: PoseMsg) -> Dict[str, Any]:
    """Convert PoseMsg to callback event format (matches BLE/TCP callback format)."""
    return {
        "type": "pose",
        "data": {
            "absolute_input": {
                "movement_start": pose.movement_start,
                "x": pose.x,
                "y": pose.y,
                "z": pose.z,
                "qx": pose.qx,
                "qy": pose.qy,
                "qz": pose.qz,
                "qw": pose.qw,
            }
        }
    }


def cmd_to_event(cmd: CmdMsg) -> Dict[str, Any]:
    """Convert CmdMsg to callback event format."""
    if cmd.cmd_type == CmdType.RECORDING:
        return {"type": "command", "name": "recording", "value": bool(cmd.value)}
    elif cmd.cmd_type == CmdType.KEEP_RECORDING:
        return {"type": "command", "name": "keep_recording", "value": bool(cmd.value)}
    else:
        return {"type": "command", "name": f"unknown_{cmd.cmd_type}", "value": cmd.value}
