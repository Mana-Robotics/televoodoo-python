"""BLE (Bluetooth Low Energy) connection backend for Televoodoo.

This module provides the BLE peripheral that the phone app connects to.

Usage:
    from televoodoo.ble import run_peripheral, send_haptic_ble

    def on_event(evt):
        print(evt)

    run_peripheral(name="myvoodoo", code="ABC123", callback=on_event)

See docs/BLE_API.md for setup details and docs/MOBILE_PROTOCOL.md for protocol.
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Optional


# BLE Service and Characteristic UUIDs (shared by all platform backends)
SERVICE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF61"
CHAR_CONTROL_UUID = "1C8FD138-FC18-4846-954D-E509366AEF62"
CHAR_AUTH_UUID = "1C8FD138-FC18-4846-954D-E509366AEF63"
CHAR_POSE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF64"
CHAR_HEARTBEAT_UUID = "1C8FD138-FC18-4846-954D-E509366AEF65"
CHAR_COMMAND_UUID = "1C8FD138-FC18-4846-954D-E509366AEF66"
CHAR_HAPTIC_UUID = "1C8FD138-FC18-4846-954D-E509366AEF67"
CHAR_CONFIG_UUID = "1C8FD138-FC18-4846-954D-E509366AEF68"

# Heartbeat rate: 2 Hz for 3-second timeout detection
HEARTBEAT_INTERVAL = 0.5


# Active BLE haptic sender (registered by platform backends)
_ble_send_haptic: Optional[Callable[[float], bool]] = None


def register_ble_haptic_sender(sender: Optional[Callable[[float], bool]]) -> None:
    """Register a BLE haptic sender callable (set by platform-specific backend)."""
    global _ble_send_haptic
    _ble_send_haptic = sender


def send_haptic_ble(intensity: float) -> bool:
    """Send haptic feedback via BLE if a sender is registered.
    
    Args:
        intensity: Haptic intensity from 0.0 (off) to 1.0 (max).
    
    Returns:
        True if sent successfully, False if no BLE connection or error.
    """
    sender = _ble_send_haptic
    if sender is None:
        return False
    try:
        return bool(sender(intensity))
    except Exception:
        return False


# Suppress high-frequency event logging when True
QUIET_HIGH_FREQUENCY = False


def run_peripheral(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    initial_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Run the BLE peripheral for phone app connection.

    This starts the platform-specific BLE peripheral that advertises
    the Televoodoo service and handles pose data from the phone.

    Args:
        name: Peripheral name (advertised to phone)
        code: Authentication code (phone must provide this to connect)
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging (pose, heartbeat)
        initial_config: Initial configuration to send to phone after connection

    Raises:
        RuntimeError: If BLE is not supported on this platform.
    """
    global QUIET_HIGH_FREQUENCY
    QUIET_HIGH_FREQUENCY = quiet

    system = platform.system().lower()
    distro = ""

    if system == "linux":
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                content = f.read().lower()
                if "ubuntu" in content:
                    distro = "ubuntu"
        except Exception:
            pass

    if system == "darwin":
        import televoodoo.ble_peripheral_macos as _mac  # type: ignore

        try:
            _mac.QUIET_HIGH_FREQUENCY = bool(quiet)  # type: ignore[attr-defined]
        except Exception:
            pass
        _mac.run_macos_peripheral(name, code, callback, register_ble_haptic_sender, initial_config)

    elif system == "linux" and distro == "ubuntu":
        import televoodoo.ble_peripheral_ubuntu as _ubu  # type: ignore

        try:
            _ubu.QUIET_HIGH_FREQUENCY = bool(quiet)  # type: ignore[attr-defined]
        except Exception:
            pass
        _ubu.run_ubuntu_peripheral(name, code, callback, register_ble_haptic_sender, initial_config)

    else:
        raise RuntimeError(
            f"BLE peripheral not supported on this platform: {platform.platform()}. "
            "Supported: macOS, Ubuntu Linux."
        )


__all__ = [
    # UUIDs
    "SERVICE_UUID",
    "CHAR_CONTROL_UUID",
    "CHAR_AUTH_UUID",
    "CHAR_POSE_UUID",
    "CHAR_HEARTBEAT_UUID",
    "CHAR_COMMAND_UUID",
    "CHAR_HAPTIC_UUID",
    "CHAR_CONFIG_UUID",
    # Constants
    "HEARTBEAT_INTERVAL",
    # Functions
    "run_peripheral",
    "send_haptic_ble",
    "register_ble_haptic_sender",
]
