"""WiFi connection backend for Televoodoo.

This module provides the WiFi entry point for Televoodoo. The phone app
connects over the local WiFi network, discovering the server via UDP beacons.

Usage:
    from televoodoo.wifi import run_server, send_haptic

    def on_event(evt):
        print(evt)

    run_server(name="myvoodoo", code="ABC123", callback=on_event)

See docs/WIFI_API.md for setup details and docs/MOBILE_PROTOCOL.md for protocol.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

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

__all__ = [
    # Constants
    "DEFAULT_TCP_PORT",
    "DEFAULT_BEACON_PORT",
    # Classes
    "TcpServer",
    "Session",
    # Functions
    "run_server",
    "get_server_url",
    "send_haptic",
    "send_config",
]
