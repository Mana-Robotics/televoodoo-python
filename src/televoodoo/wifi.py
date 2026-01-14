"""WiFi connection backend for Televoodoo.

This module provides the WiFi entry point for Televoodoo. It uses the
transport-agnostic UDP service from udp_service.py.

The phone app connects over the local WiFi network via mDNS discovery.
The phone and computer must be on the same WiFi network.

See WIFI_API.md for the protocol specification.

Note: Most functionality is in udp_service.py - this module provides
backward-compatible exports and WiFi-specific convenience functions.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# Re-export core functionality from udp_service for backward compatibility
from .udp_service import (
    # Constants
    DEFAULT_PORT,
    SESSION_TIMEOUT,
    SERVICE_TYPE,
    # Classes
    UdpServer as WlanServer,  # Backward-compat alias
    Session,
    # Functions
    run_server,
    get_server_url,
    send_haptic,
)

# For internal compatibility - deprecated, use udp_service directly
QUIET_HIGH_FREQUENCY = False


def get_wifi_url(port: int = DEFAULT_PORT) -> str:
    """Get the UDP endpoint info for the WiFi server.
    
    Convenience alias for get_server_url().

    Args:
        port: Server port (default: 50000)

    Returns:
        UDP endpoint like "udp://192.168.1.100:50000"
    """
    return get_server_url(port)


__all__ = [
    # Constants
    "DEFAULT_PORT",
    "SESSION_TIMEOUT",
    "SERVICE_TYPE",
    # Classes (WlanServer for backward compatibility)
    "WlanServer",
    "Session",
    # Functions
    "run_server",
    "get_server_url",
    "get_wifi_url",
    "send_haptic",
]
