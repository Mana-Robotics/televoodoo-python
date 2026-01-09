"""Connection management for Televoodoo.

This module provides the main entry point for starting Televoodoo with
different connection backends (BLE, WLAN, etc.).
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Literal, Optional

from .session import generate_credentials, print_session_qr


ConnectionType = Literal["auto", "ble", "wlan"]


def start_televoodoo(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    name: Optional[str] = None,
    code: Optional[str] = None,
    connection: ConnectionType = "auto",
) -> None:
    """Start Televoodoo and wait for phone app connection.

    Generates a session with QR code for the phone app to scan, then starts
    the connection backend and calls the callback for each teleoperation event.

    Args:
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging (pose, heartbeat)
        name: Static peripheral/server name (default: random)
        code: Static auth code (default: random)
        connection: Connection type - "auto" (default), "ble", or "wlan"

    Raises:
        RuntimeError: If the requested connection type is not supported on this platform.
    """
    # Use provided credentials or generate random ones
    if name is None or code is None:
        gen_name, gen_code = generate_credentials()
        name = name or gen_name
        code = code or gen_code

    # Always print session/QR so clients can connect
    print_session_qr(name, code)

    # Determine connection backend
    if connection == "auto":
        connection = _detect_best_connection()

    try:
        if connection == "ble":
            _start_ble(name, code, callback, quiet)
        elif connection == "wlan":
            _start_wlan(name, code, callback, quiet)
        else:
            raise RuntimeError(f"Unknown connection type: {connection}")
    except Exception as e:
        print(
            json.dumps({"type": "error", "message": f"Connection failed: {e}"}),
            flush=True,
        )
        raise


def _detect_best_connection() -> ConnectionType:
    """Detect the best available connection type for this platform.

    Currently defaults to BLE on supported platforms.
    """
    system = platform.system().lower()

    if system == "darwin":
        return "ble"
    elif system == "linux":
        # Check for Ubuntu (BlueZ support)
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                if "ubuntu" in f.read().lower():
                    return "ble"
        except Exception:
            pass

    # Default to BLE, let it fail with a clear error if unsupported
    return "ble"


def _start_ble(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
) -> None:
    """Start BLE peripheral backend."""
    from . import ble

    ble.run_peripheral(name, code, callback, quiet)


def _start_wlan(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
) -> None:
    """Start WLAN server backend."""
    from . import wlan

    wlan.run_server(name, code, callback, quiet)

