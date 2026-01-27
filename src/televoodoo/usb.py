"""USB connection backend for Televoodoo.

USB connections use the same TCP server as WiFi. The server binds to all
interfaces (0.0.0.0) and broadcasts UDP beacons, so the phone discovers
the server regardless of whether it's connected via WiFi or USB.

Usage:
    from televoodoo.usb import run_server, send_haptic

    def on_event(evt):
        print(evt)

    run_server(name="myvoodoo", code="ABC123", callback=on_event)

See docs/USB_API.md for setup details and docs/MOBILE_PROTOCOL.md for protocol.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# Re-export TCP server functionality (same as WiFi)
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


# USB interface detection utilities (for diagnostics)


@dataclass
class UsbInterface:
    """Detected USB network interface."""
    name: str
    device: str
    ip: Optional[str] = None


def _run_command(cmd: List[str]) -> str:
    """Run a command and return stdout, or empty string on error."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return result.stdout
    except Exception:
        return ""


def detect_usb_interfaces() -> List[UsbInterface]:
    """Detect USB network interfaces on the current platform.
    
    This is a diagnostic utility. The TCP server works without detection
    since it binds to all interfaces.
    
    Returns:
        List of detected USB network interfaces.
    """
    system = platform.system().lower()
    
    if system == "darwin":
        return _detect_usb_interfaces_darwin()
    else:
        return []


def _detect_usb_interfaces_darwin() -> List[UsbInterface]:
    """Detect USB network interfaces on macOS using networksetup."""
    interfaces = []
    
    output = _run_command(["networksetup", "-listallhardwareports"])
    if not output:
        return interfaces
    
    current_name = None
    
    # Known non-USB hardware port prefixes to exclude
    exclude_prefixes = [
        "Wi-Fi",
        "Ethernet",
        "Thunderbolt",
        "VLAN",
        "Bluetooth",
        "FireWire",
    ]
    
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("Hardware Port:"):
            current_name = line.replace("Hardware Port:", "").strip()
        elif line.startswith("Device:") and current_name:
            device = line.replace("Device:", "").strip()
            
            is_excluded = any(current_name.startswith(prefix) for prefix in exclude_prefixes)
            if "Ethernet Adapter" in current_name:
                is_excluded = True
            
            if not is_excluded and current_name and device:
                interfaces.append(UsbInterface(name=current_name, device=device))
            
            current_name = None
    
    return interfaces


def get_usb_interface_names() -> List[str]:
    """Get names of detected USB network interfaces."""
    return [iface.name for iface in detect_usb_interfaces()]


def is_usb_available() -> bool:
    """Check if a USB network interface is detected."""
    return len(detect_usb_interfaces()) > 0


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
    # USB utilities
    "UsbInterface",
    "detect_usb_interfaces",
    "get_usb_interface_names",
    "is_usb_available",
]
