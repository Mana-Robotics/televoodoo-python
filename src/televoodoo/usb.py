"""USB connection utilities for Televoodoo.

USB connections use the same UDP/mDNS server as WiFi. The phone app discovers
the server via mDNS on whatever network interface it's connected to (WiFi or USB).

This module provides utility functions for USB interface detection, which can
be useful for diagnostics and troubleshooting.

Note: The main run_server functionality is provided by wifi.py - USB uses the
same server since mDNS advertises on all interfaces.
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional


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


def detect_usb_interfaces_darwin() -> List[UsbInterface]:
    """Detect USB network interfaces on macOS using networksetup.
    
    This identifies interfaces by their hardware port name, excluding
    known non-USB types (Wi-Fi, Ethernet, Thunderbolt).
    
    Returns:
        List of USB interfaces (e.g., "Pixel 9a", "iPhone USB")
    """
    interfaces = []
    
    output = _run_command(["networksetup", "-listallhardwareports"])
    if not output:
        return interfaces
    
    # Parse output: Hardware Port: <name>\nDevice: <device>
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
            
            # Check if this is likely a USB device (not in exclude list)
            is_excluded = any(current_name.startswith(prefix) for prefix in exclude_prefixes)
            # Also exclude generic "Ethernet Adapter" entries
            if "Ethernet Adapter" in current_name:
                is_excluded = True
            
            if not is_excluded and current_name and device:
                interfaces.append(UsbInterface(
                    name=current_name,
                    device=device,
                ))
            
            current_name = None
    
    return interfaces


def detect_usb_interfaces() -> List[UsbInterface]:
    """Detect USB network interfaces on the current platform.
    
    Returns:
        List of detected USB network interfaces.
    """
    system = platform.system().lower()
    
    if system == "darwin":
        return detect_usb_interfaces_darwin()
    else:
        # On other platforms, return empty list
        # The mDNS approach works regardless of detection
        return []


def get_usb_interface_names() -> List[str]:
    """Get the names of USB network interfaces.
    
    Returns:
        List of interface names (e.g., ["Pixel 9a", "iPhone USB"])
    """
    return [iface.name for iface in detect_usb_interfaces()]


def is_usb_available() -> bool:
    """Check if a USB network interface is available.
    
    Returns:
        True if at least one USB network interface is detected.
    """
    return len(detect_usb_interfaces()) > 0


def get_usb_info() -> Optional[dict]:
    """Get information about USB network interfaces.
    
    Returns:
        Dict with USB interface info, or None if not available.
    """
    interfaces = detect_usb_interfaces()
    if not interfaces:
        return None
    
    return {
        "interfaces": [{"name": i.name, "device": i.device} for i in interfaces],
        "count": len(interfaces),
    }


# Backward compatibility - these functions are deprecated but kept for existing code
def get_usb_ip() -> Optional[str]:
    """Deprecated: IP detection not needed with mDNS approach."""
    return None


def get_usb_gateway() -> Optional[str]:
    """Deprecated: Gateway detection not needed with mDNS approach."""
    return None
