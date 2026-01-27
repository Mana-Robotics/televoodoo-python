"""BLE (Bluetooth Low Energy) connection backend for Televoodoo.

This module provides the BLE peripheral that the phone app connects to.
"""

from __future__ import annotations

import json
import platform
import random
import time
from typing import Any, Callable, Dict, Iterator, Optional

from .pose import Pose

# Active BLE haptic sender (registered by platform backends)
_ble_send_haptic: Optional[Callable[[float], bool]] = None


def register_ble_haptic_sender(sender: Optional[Callable[[float], bool]]) -> None:
    """Register a BLE haptic sender callable (set by platform-specific backend)."""
    global _ble_send_haptic
    _ble_send_haptic = sender


def send_haptic_ble(intensity: float) -> bool:
    """Send haptic via BLE if a sender is registered."""
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
        quiet: Suppress high-frequency logging
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


# =============================================================================
# Simulation utilities (for testing without phone)
# =============================================================================


def simulate_pose_stream() -> Iterator[Pose]:
    """Generate a stream of simulated pose data.

    Yields random poses at ~30 Hz for testing purposes.

    Yields:
        Pose objects with random position values.
    """
    while True:
        yield Pose(
            movement_start=True,
            x=0.1 * random.uniform(-1, 1),
            y=0.1 * random.uniform(-1, 1),
            z=0.1 * random.uniform(-1, 1),
            qx=0.0,
            qy=0.0,
            qz=0.0,
            qw=1.0,
        )
        time.sleep(0.033)


def run_simulation(on_pose: Callable[[Pose], None]) -> None:
    """Run pose simulation for testing.

    Continuously generates random poses and calls the callback.
    This is useful for testing without a phone connection.

    Args:
        on_pose: Callback function receiving Pose objects.
    """
    for p in simulate_pose_stream():
        on_pose(p)
