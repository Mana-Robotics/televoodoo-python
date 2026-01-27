"""Session and credential utilities for Televoodoo."""

import json
import random
import string
from typing import Literal, Optional, Tuple

TransportType = Literal["ble", "wifi", "usb"]


def generate_credentials() -> Tuple[str, str]:
    """Generate random connection credentials.

    Returns:
        Tuple of (name, code) where:
        - name: Peripheral name like "voodooXX"
        - code: 6-character alphanumeric auth code (uppercase A-Z and 0-9)
    """
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    name = f"voodoo{suffix}"
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return name, code


def print_session_qr(
    name: str,
    code: str,
    transport: TransportType = "wifi",
) -> None:
    """Print session info as JSON and display QR code for phone app.

    The QR code contains minimal data for beacon-based discovery:
    - name: Service name (app discovers via UDP beacon with matching name)
    - code: Authentication code
    - transport: Connection type ("ble", "wifi", or "usb")

    No IP address is included - the phone app discovers the server via:
    - UDP beacons for WiFi/USB
    - BLE advertising for BLE

    Args:
        name: Peripheral/server name (used for beacon matching)
        code: Authentication code
        transport: Connection type ("ble", "wifi", or "usb")
    """
    # Build session info for logging
    session_info = {
        "type": "session",
        "name": name,
        "code": code,
        "transport": transport,
    }
    
    # Start on a fresh line (in case previous output used \r for in-place updates)
    print("", flush=True)
    print(json.dumps(session_info), flush=True)
    
    try:
        import qrcode

        # QR code payload - minimal data, beacon discovery handles finding the host
        # Phone app listens for UDP beacons with matching name
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
