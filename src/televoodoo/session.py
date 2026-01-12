"""Session and credential utilities for Televoodoo."""

import json
import random
import socket
import string
from typing import Literal, Optional, Tuple

TransportType = Literal["ble", "wlan"]


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
    wlan_port: Optional[int] = None,
    wlan_ip: Optional[str] = None,
) -> None:
    """Print session info as JSON and display QR code for phone app.

    Args:
        name: Peripheral/server name
        code: Authentication code
        transport: Connection type ("ble" or "wlan")
        wlan_port: UDP port for WLAN (required if transport="wlan")
        wlan_ip: IP address for WLAN (auto-detected if not provided)
    """
    # Build session info
    session_info = {
        "type": "session",
        "name": name,
        "code": code,
        "transport": transport,
    }
    
    # Add WLAN-specific fields
    if transport == "wlan":
        session_info["ip"] = wlan_ip or _get_local_ip()
        session_info["port"] = wlan_port or 50000
    
    print(json.dumps(session_info), flush=True)
    
    try:
        import qrcode

        # QR code payload includes transport info
        payload_data = {"name": name, "code": code, "transport": transport}
        
        if transport == "wlan":
            payload_data["ip"] = session_info["ip"]
            payload_data["port"] = session_info["port"]
        
        payload = json.dumps(payload_data)
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.make()
        qr.print_ascii(invert=True)
    except Exception:
        # QR printing is best-effort; session JSON is already printed
        pass
