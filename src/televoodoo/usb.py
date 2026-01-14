"""USB tethering connection backend for Televoodoo.

This module provides USB tethering as a connection alternative to WiFi and BLE.
USB tethering creates a virtual network interface between the phone and computer,
allowing the same UDP protocol to work with lower latency and higher reliability.

Key differences from WiFi:
- No mDNS discovery (direct IP known via interface detection)
- Uses the phone's USB tethering interface IP
- Lower latency (~5-10ms vs ~16ms WiFi)
- More reliable (wired connection)

Prerequisites:
- Android: Enable USB Tethering in Settings → Network → Hotspot & Tethering
- iOS: Enable Personal Hotspot and connect via USB cable
- Linux (for iOS): Install libimobiledevice and usbmuxd packages
"""

from __future__ import annotations

import json
import platform
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .wifi import WlanServer, DEFAULT_PORT

# Common USB tethering IP ranges by platform
# Android typically uses 192.168.42.x (phone at .1, computer at .129 or similar)
# iOS typically uses 172.20.10.x (phone at .1, computer gets DHCP address)
# iOS can also use 192.0.0.x for USB Ethernet mode
# macOS Internet Sharing uses 192.168.2.x (Mac at .1, phone gets DHCP)
USB_TETHERING_PREFIXES = [
    "192.168.42.",   # Android USB tethering (most common)
    "192.168.44.",   # Some Android variants
    "172.20.10.",    # iOS Personal Hotspot over USB
    "192.168.2.",    # macOS Internet Sharing over USB
    "192.0.0.",      # iOS USB Ethernet mode (limited, usually doesn't work)
    "169.254.",      # Link-local (fallback when DHCP fails) - lowest priority
]

# Interface name patterns for USB tethering
USB_INTERFACE_PATTERNS = {
    "darwin": [
        r"^en\d+$",      # macOS USB Ethernet adapters
        r"^bridge\d+$",  # macOS bridge interfaces (iOS)
    ],
    "linux": [
        r"^usb\d+$",     # Linux USB network
        r"^enp\d+s\d+u\d+.*$",  # Linux USB Ethernet (systemd naming)
        r"^eth\d+$",     # Legacy naming
    ],
    "windows": [
        r".*",  # Windows uses different enumeration
    ],
}


@dataclass
class UsbInterface:
    """Detected USB tethering interface."""
    name: str
    ip: str
    gateway: Optional[str] = None
    is_android: bool = False
    is_ios: bool = False


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


def _detect_usb_interfaces_darwin() -> List[UsbInterface]:
    """Detect USB tethering interfaces on macOS."""
    interfaces = []
    
    # Get all interfaces with their IPs using ifconfig
    ifconfig_output = _run_command(["ifconfig"])
    if not ifconfig_output:
        return interfaces
    
    current_iface = None
    current_ip = None
    
    for line in ifconfig_output.split("\n"):
        # New interface starts with no leading whitespace
        if line and not line[0].isspace() and ":" in line:
            # Save previous interface if it had a USB tethering IP
            if current_iface and current_ip:
                for prefix in USB_TETHERING_PREFIXES:
                    if current_ip.startswith(prefix):
                        is_android = prefix.startswith("192.168.42") or prefix.startswith("192.168.44")
                        is_ios = prefix.startswith("172.20.10") or prefix.startswith("192.0.0.")
                        interfaces.append(UsbInterface(
                            name=current_iface,
                            ip=current_ip,
                            gateway=prefix + "1" if is_android or is_ios else None,
                            is_android=is_android,
                            is_ios=is_ios,
                        ))
                        break
            
            current_iface = line.split(":")[0]
            current_ip = None
        
        # Look for inet address
        if "inet " in line and "inet6" not in line:
            match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
            if match:
                current_ip = match.group(1)
    
    # Don't forget the last interface
    if current_iface and current_ip:
        for prefix in USB_TETHERING_PREFIXES:
            if current_ip.startswith(prefix):
                is_android = prefix.startswith("192.168.42") or prefix.startswith("192.168.44")
                is_ios = prefix.startswith("172.20.10") or prefix.startswith("192.0.0.")
                interfaces.append(UsbInterface(
                    name=current_iface,
                    ip=current_ip,
                    gateway=prefix + "1" if is_android or is_ios else None,
                    is_android=is_android,
                    is_ios=is_ios,
                ))
                break
    
    return interfaces


def _detect_usb_interfaces_linux() -> List[UsbInterface]:
    """Detect USB tethering interfaces on Linux."""
    interfaces = []
    
    # Use ip addr to get interfaces
    ip_output = _run_command(["ip", "addr"])
    if not ip_output:
        # Fallback to ifconfig
        ip_output = _run_command(["ifconfig", "-a"])
    
    if not ip_output:
        return interfaces
    
    current_iface = None
    current_ip = None
    
    for line in ip_output.split("\n"):
        # ip addr format: "2: eth0: <FLAGS>"
        if re.match(r"^\d+:\s+\w+", line):
            # Save previous
            if current_iface and current_ip:
                for prefix in USB_TETHERING_PREFIXES:
                    if current_ip.startswith(prefix):
                        is_android = prefix.startswith("192.168.42") or prefix.startswith("192.168.44")
                        is_ios = prefix.startswith("172.20.10") or prefix.startswith("192.0.0.")
                        interfaces.append(UsbInterface(
                            name=current_iface,
                            ip=current_ip,
                            gateway=prefix + "1" if is_android or is_ios else None,
                            is_android=is_android,
                            is_ios=is_ios,
                        ))
                        break
            
            match = re.match(r"^\d+:\s+(\w+)", line)
            if match:
                current_iface = match.group(1)
                current_ip = None
        
        # ip addr format: "inet 192.168.42.129/24"
        if "inet " in line and "inet6" not in line:
            match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
            if match:
                current_ip = match.group(1)
    
    # Last interface
    if current_iface and current_ip:
        for prefix in USB_TETHERING_PREFIXES:
            if current_ip.startswith(prefix):
                is_android = prefix.startswith("192.168.42") or prefix.startswith("192.168.44")
                is_ios = prefix.startswith("172.20.10") or prefix.startswith("192.0.0.")
                interfaces.append(UsbInterface(
                    name=current_iface,
                    ip=current_ip,
                    gateway=prefix + "1" if is_android or is_ios else None,
                    is_android=is_android,
                    is_ios=is_ios,
                ))
                break
    
    return interfaces


def detect_usb_interfaces() -> List[UsbInterface]:
    """Detect USB tethering interfaces on the current platform.
    
    Returns:
        List of detected USB tethering interfaces with their IPs.
        Sorted by priority: non-link-local IPs first.
        Empty list if no USB tethering is detected.
    """
    system = platform.system().lower()
    
    if system == "darwin":
        interfaces = _detect_usb_interfaces_darwin()
    elif system == "linux":
        interfaces = _detect_usb_interfaces_linux()
    else:
        # Windows or other - try generic approach
        interfaces = _detect_usb_interfaces_darwin()  # ifconfig-style might work
    
    # Sort to prefer non-link-local IPs (169.254.x.x should be last resort)
    def priority(iface: UsbInterface) -> int:
        if iface.ip.startswith("169.254."):
            return 1  # Lower priority
        return 0  # Higher priority
    
    return sorted(interfaces, key=priority)


def get_usb_ip() -> Optional[str]:
    """Get the local IP address on the USB tethering interface.
    
    Returns:
        The local IP on the USB interface, or None if not found.
    """
    interfaces = detect_usb_interfaces()
    if interfaces:
        return interfaces[0].ip
    return None


def get_usb_gateway() -> Optional[str]:
    """Get the phone's IP (gateway) on the USB tethering interface.
    
    This is the IP the phone uses on the USB network, typically:
    - Android: 192.168.42.1
    - iOS: 172.20.10.1
    
    Returns:
        The phone's IP on the USB interface, or None if not found.
    """
    interfaces = detect_usb_interfaces()
    if interfaces and interfaces[0].gateway:
        return interfaces[0].gateway
    return None


class UsbServer(WlanServer):
    """USB tethering server for Televoodoo pose streaming.
    
    This is a specialized version of WlanServer that:
    - Skips mDNS advertisement (not needed for USB, phone knows the IP)
    - Binds only to the USB interface IP (more secure)
    - Reports USB-specific connection events
    """
    
    def __init__(
        self,
        name: str,
        code: str,
        port: int = DEFAULT_PORT,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        quiet: bool = False,
        usb_ip: Optional[str] = None,
    ):
        # Detect USB interface if not provided
        if usb_ip is None:
            usb_ip = get_usb_ip()
        
        self.usb_ip = usb_ip
        self.usb_gateway = get_usb_gateway()
        
        # Initialize parent with USB IP
        super().__init__(
            name=name,
            code=code,
            port=port,
            callback=callback,
            quiet=quiet,
        )
        
        # Override local_ip with USB interface IP
        if self.usb_ip:
            self.local_ip = self.usb_ip
    
    def _start_mdns(self) -> None:
        """Skip mDNS for USB - phone connects directly via known IP."""
        # Emit info about USB mode instead
        self._emit({
            "type": "usb_mode",
            "message": "mDNS skipped for USB (direct IP connection)",
            "phone_ip": self.usb_gateway,
        })
    
    def _stop_mdns(self) -> None:
        """No mDNS to stop for USB."""
        pass
    
    def _emit(self, event: Dict[str, Any]) -> None:
        """Emit event with USB-specific type naming."""
        event_type = event.get("type", "")
        
        # Rename wifi_* events to usb_* events
        if event_type.startswith("wifi_"):
            event = dict(event)
            event["type"] = "usb_" + event_type[5:]
        
        super()._emit(event)
    
    def start(self) -> None:
        """Start the USB server."""
        if self.usb_ip is None:
            self._emit({
                "type": "error",
                "message": "No USB tethering interface detected. "
                           "Please enable USB tethering on your phone and reconnect.",
            })
            raise RuntimeError("No USB tethering interface detected")
        
        self._emit({
            "type": "usb_starting",
            "name": self.name,
            "port": self.port,
            "ip": self.usb_ip,
            "phone_ip": self.usb_gateway,
        })
        
        super().start()


def run_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    port: int = DEFAULT_PORT,
) -> None:
    """Run the Televoodoo USB server.

    This starts a UDP server on the USB tethering interface. The phone
    connects directly to this IP (no mDNS discovery needed).

    Args:
        name: Server name (for identification)
        code: Authentication code
        callback: Function called for each event
        quiet: Suppress high-frequency logging
        port: UDP port to listen on (default: 50000)

    Raises:
        RuntimeError: If no USB tethering interface is detected.
    """
    import signal
    
    server = UsbServer(
        name=name,
        code=code,
        port=port,
        callback=callback,
        quiet=quiet,
    )
    
    def handle_signal(signum, frame):
        server.stop()
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    server.start()


def is_usb_available() -> bool:
    """Check if USB tethering is currently available.
    
    Returns:
        True if a USB tethering interface is detected, False otherwise.
    """
    return len(detect_usb_interfaces()) > 0


def get_usb_info() -> Optional[Dict[str, Any]]:
    """Get information about the USB tethering connection.
    
    Returns:
        Dict with USB connection info, or None if not available.
        
        Example:
        {
            "interface": "en5",
            "local_ip": "192.168.42.129",
            "phone_ip": "192.168.42.1",
            "platform": "android"
        }
    """
    interfaces = detect_usb_interfaces()
    if not interfaces:
        return None
    
    iface = interfaces[0]
    platform_type = "android" if iface.is_android else ("ios" if iface.is_ios else "unknown")
    
    return {
        "interface": iface.name,
        "local_ip": iface.ip,
        "phone_ip": iface.gateway,
        "platform": platform_type,
    }
