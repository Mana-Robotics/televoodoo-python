"""Televoodoo binary protocol - shared by BLE and WLAN transports.

This module implements the v2 binary protocol as specified in:
- BLE_PERIPHERAL_API_v2.md
- WLAN_API_v2.md

All messages use little-endian byte order.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Optional, Tuple

# Protocol constants
MAGIC = b"TELE"
PROTOCOL_VERSION = 1

# Struct formats (little-endian)
HEADER_FORMAT = "<4sBB"  # magic(4), msg_type(1), version(1) = 6 bytes
HELLO_FORMAT = "<4sBBI6sH"  # header + session_id(4) + code(6) + reserved(2) = 18 bytes
ACK_FORMAT = "<4sBBBB"  # header + status(1) + reserved(1) = 8 bytes
POSE_FORMAT = "<4sBBHQBB7f"  # header + seq(2) + ts(8) + flags(1) + reserved(1) + 7 floats = 46 bytes
BYE_FORMAT = "<4sBBI"  # header + session_id(4) = 10 bytes
CMD_FORMAT = "<4sBBBB"  # header + cmd_type(1) + value(1) = 8 bytes
HEARTBEAT_FORMAT = "<4sBBII"  # header + counter(4) + uptime_ms(4) = 14 bytes

# Sizes
HEADER_SIZE = 6
HELLO_SIZE = 18
ACK_SIZE = 8
POSE_SIZE = 46
BYE_SIZE = 10
CMD_SIZE = 8
HEARTBEAT_SIZE = 14


class MsgType(IntEnum):
    """Message type IDs."""
    HELLO = 1
    ACK = 2
    POSE = 3
    BYE = 4
    CMD = 5
    HEARTBEAT = 6


class AckStatus(IntEnum):
    """ACK status codes."""
    OK = 0
    BAD_CODE = 1
    BUSY = 2
    VERSION_UNSUPPORTED = 3


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
        return self.magic == MAGIC and self.version == PROTOCOL_VERSION


@dataclass
class HelloMsg:
    """HELLO message (iPhone → PC)."""
    session_id: int
    code: str


@dataclass
class AckMsg:
    """ACK message (PC → iPhone)."""
    status: AckStatus


@dataclass
class PoseMsg:
    """POSE message (iPhone → PC)."""
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
    """BYE message (iPhone → PC)."""
    session_id: int


@dataclass
class CmdMsg:
    """CMD message (iPhone → PC)."""
    cmd_type: CmdType
    value: int


@dataclass
class HeartbeatMsg:
    """HEARTBEAT message (PC → iPhone, BLE only)."""
    counter: int
    uptime_ms: int


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
        return HelloMsg(session_id=session_id, code=code)
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


def is_binary_protocol(data: bytes) -> bool:
    """Check if data starts with the TELE magic bytes (v2 protocol)."""
    return len(data) >= 4 and data[:4] == MAGIC


# =============================================================================
# Packing functions
# =============================================================================


def pack_ack(status: AckStatus) -> bytes:
    """Pack ACK message."""
    return struct.pack(ACK_FORMAT, MAGIC, MsgType.ACK, PROTOCOL_VERSION, status, 0)


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


# =============================================================================
# Conversion to callback event format
# =============================================================================


def pose_to_event(pose: PoseMsg) -> Dict[str, Any]:
    """Convert PoseMsg to callback event format (matches BLE/WLAN callback format)."""
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
