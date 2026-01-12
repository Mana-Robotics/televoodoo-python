"""Connection management for Televoodoo.

This module provides the main entry point for starting Televoodoo with
different connection backends (BLE, WIFI, etc.).
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Literal, Optional

from .session import generate_credentials, print_session_qr
from .wifi import DEFAULT_PORT as WIFI_DEFAULT_PORT


ConnectionType = Literal["auto", "ble", "wifi"]


def start_televoodoo(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    name: Optional[str] = None,
    code: Optional[str] = None,
    connection: ConnectionType = "auto",
    wifi_port: int = WIFI_DEFAULT_PORT,
) -> None:
    """Start Televoodoo and wait for phone app connection.

    Generates a session with QR code for the phone app to scan, then starts
    the connection backend and calls the callback for each teleoperation event.

    Args:
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging (pose, heartbeat)
        name: Static peripheral/server name (default: random)
        code: Static auth code (default: random)
        connection: Connection type - "auto" (default), "ble", or "wifi"
        wifi_port: UDP port for WIFI server (default: 50000)

    Raises:
        RuntimeError: If the requested connection type is not supported on this platform.
    """
    # Use provided credentials or generate random ones
    if name is None or code is None:
        gen_name, gen_code = generate_credentials()
        name = name or gen_name
        code = code or gen_code

    # Determine connection backend
    resolved_connection = connection
    if resolved_connection == "auto":
        resolved_connection = _detect_best_connection()

    # Print session/QR with transport info so phone app knows how to connect
    print_session_qr(
        name=name,
        code=code,
        transport=resolved_connection,
        wifi_port=wifi_port if resolved_connection == "wifi" else None,
    )

    try:
        if resolved_connection == "ble":
            _start_ble(name, code, callback, quiet)
        elif resolved_connection == "wifi":
            _start_wifi(name, code, callback, quiet, wifi_port)
        else:
            raise RuntimeError(f"Unknown connection type: {resolved_connection}")
    except Exception as e:
        print(
            json.dumps({"type": "error", "message": f"Connection failed: {e}"}),
            flush=True,
        )
        raise


def _detect_best_connection() -> Literal["ble", "wifi"]:
    """Detect the best available connection type for this platform.

    Defaults to WiFi for better latency and cross-platform compatibility.
    """
    # WiFi is the recommended default:
    # - Lower latency (~16ms consistent vs BLE batching)
    # - Works on all platforms with network access
    # - No platform-specific BLE dependencies
    return "wifi"


def _start_ble(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
) -> None:
    """Start BLE peripheral backend."""
    from . import ble

    ble.run_peripheral(name, code, callback, quiet)


def _start_wifi(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    port: int,
) -> None:
    """Start WIFI server backend."""
    from . import wifi

    wifi.run_server(name, code, callback, quiet, port)
