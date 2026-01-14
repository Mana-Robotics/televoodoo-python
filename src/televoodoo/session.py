"""Session and credential utilities for Televoodoo."""

import json
import random
import socket
import string
from typing import Literal, Optional, Tuple

TransportType = Literal["ble", "wifi", "usb"]


def generate_credentials() -> Tuple[str, str]:
    """Generate random connection credentials.

    Returns:
        Tuple of (name, code) where:
        - name: Peripheral name like "voodooXX"
        - code: 6-character alphanumeric auth code
    """
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    name = f"voodoo{suffix}"
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return name, code


def _get_local_ip() -> str:
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_session_qr(
    name: str,
    code: str,
    transport: TransportType = "ble",
    wifi_port: Optional[int] = None,
    wifi_ip: Optional[str] = None,
    usb_ip: Optional[str] = None,
) -> None:
    """Print session info as JSON and display QR code for phone app.

    The QR code contains minimal data for mDNS-based discovery:
    - name: Service name (app discovers via <name>._televoodoo._udp.local.)
    - code: Authentication code
    - transport: Connection type ("ble", "wifi", or "usb")

    For WiFi/USB, the phone app discovers the server via mDNS - no IP needed in QR.

    Args:
        name: Peripheral/server name (used for mDNS discovery)
        code: Authentication code
        transport: Connection type ("ble", "wifi", or "usb")
        wifi_port: UDP port for WIFI/USB (default: 50000, included in mDNS TXT record)
        wifi_ip: Optional IP address override (for logging only)
        usb_ip: Deprecated, unused (mDNS handles discovery)
    """
    # Build session info for logging
    session_info = {
        "type": "session",
        "name": name,
        "code": code,
        "transport": transport,
    }
    
    # Add port for WiFi/USB (for logging; actual discovery via mDNS)
    if transport in ("wifi", "usb"):
        session_info["port"] = wifi_port or 50000
        # Include detected IP for informational purposes
        session_info["ip"] = wifi_ip or _get_local_ip()
    
    print(json.dumps(session_info), flush=True)
    
    try:
        import qrcode

        # QR code payload - minimal data, mDNS handles discovery
        # Phone app uses: <name>._televoodoo._udp.local. to find the service
        payload_data = {
            "name": name,
            "code": code,
            "transport": transport,
        }
        
        payload = json.dumps(payload_data)
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.make()
        qr.print_ascii(invert=True)
    except Exception:
        # QR printing is best-effort; session JSON is already printed
        pass
