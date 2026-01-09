"""WLAN connection backend for Televoodoo.

This module provides a WiFi/network-based connection alternative to BLE.
The phone app connects over the local network instead of Bluetooth.

Status: NOT YET IMPLEMENTED - Boilerplate for future development.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

# Default port for Televoodoo WLAN server
DEFAULT_PORT = 8765

# Suppress high-frequency event logging when True
QUIET_HIGH_FREQUENCY = False


def run_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
) -> None:
    """Run the Televoodoo WLAN server.

    This starts a WebSocket server that the phone app can connect to
    over the local network. The phone and computer must be on the same
    WiFi network.

    Args:
        name: Server name (for discovery/identification)
        code: Authentication code (phone must provide this to connect)
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging

    Raises:
        NotImplementedError: WLAN backend is not yet implemented.
    """
    global QUIET_HIGH_FREQUENCY
    QUIET_HIGH_FREQUENCY = quiet

    # TODO: Implement WLAN server
    # 
    # Planned implementation:
    # 1. Start a WebSocket server on DEFAULT_PORT
    # 2. Broadcast server availability via mDNS/Bonjour (name.local)
    # 3. Accept connections from phone app
    # 4. Validate auth code on connection
    # 5. Receive pose data as JSON messages
    # 6. Call callback with event dictionaries (same format as BLE)
    #
    # Event format (same as BLE for compatibility):
    # - {"type": "pose", "data": {"absolute_input": {...}}}
    # - {"type": "command", "name": "...", "value": ...}
    # - {"type": "wlan_connected"}
    # - {"type": "wlan_disconnected"}

    raise NotImplementedError(
        "WLAN connection backend is not yet implemented. "
        "Please use BLE connection (connection='ble') or wait for a future release."
    )


def get_server_url(port: int = DEFAULT_PORT) -> str:
    """Get the WebSocket URL for the WLAN server.

    Args:
        port: Server port (default: 8765)

    Returns:
        WebSocket URL like "ws://192.168.1.100:8765"
    """
    import socket

    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"ws://{ip}:{port}"
    except Exception:
        return f"ws://localhost:{port}"


def _emit_event(
    callback: Optional[Callable[[Dict[str, Any]], None]],
    event: Dict[str, Any],
) -> None:
    """Emit an event to the callback and optionally log it.

    Args:
        callback: Optional callback function
        event: Event dictionary to emit
    """
    event_type = event.get("type", "")
    is_high_freq = event_type in ("pose", "heartbeat")

    if not QUIET_HIGH_FREQUENCY or not is_high_freq:
        print(json.dumps(event), flush=True)

    if callback:
        try:
            callback(event)
        except Exception:
            pass

