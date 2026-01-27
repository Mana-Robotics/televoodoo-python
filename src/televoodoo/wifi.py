"""WiFi connection backend for Televoodoo.

This module provides the WiFi entry point for Televoodoo. It uses the
transport-agnostic TCP service from tcp_service.py.

The phone app connects over the local WiFi network via UDP beacon discovery.
The phone and computer must be on the same WiFi network.

See Multi-transport-spec.md for the protocol specification.

Note: Most functionality is in tcp_service.py - this module provides
convenience exports for WiFi-specific use cases.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# Re-export core functionality from tcp_service
from .tcp_service import (
    # Constants
    DEFAULT_TCP_PORT,
    DEFAULT_BEACON_PORT,
    # Classes
    TcpServer,
    Session,
    # Functions
    run_server,
    get_server_url,
    send_haptic,
    send_config,
)

# Aliases for backward compatibility (deprecated)
DEFAULT_PORT = DEFAULT_TCP_PORT


def get_wifi_url(port: int = DEFAULT_TCP_PORT) -> str:
    """Get the TCP endpoint info for the WiFi server.
    
    Convenience alias for get_server_url().

    Args:
        port: Server port (default: 50000)

    Returns:
        TCP endpoint like "tcp://192.168.1.100:50000"
    """
    return get_server_url(port)


__all__ = [
    # Constants
    "DEFAULT_TCP_PORT",
    "DEFAULT_BEACON_PORT",
    "DEFAULT_PORT",  # Deprecated alias
    # Classes
    "TcpServer",
    "Session",
    # Functions
    "run_server",
    "get_server_url",
    "get_wifi_url",
    "send_haptic",
    "send_config",
]
