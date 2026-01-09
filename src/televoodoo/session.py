"""Session and credential utilities for Televoodoo."""

import json
import random
import string
from typing import Tuple


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


def print_session_qr(name: str, code: str) -> None:
    """Print session info as JSON and display QR code for phone app.

    Args:
        name: Peripheral/server name
        code: Authentication code
    """
    print(json.dumps({"type": "session", "name": name, "code": code}), flush=True)
    try:
        import qrcode

        payload = json.dumps({"name": name, "code": code})
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.make()
        qr.print_ascii(invert=True)
    except Exception:
        # QR printing is best-effort; session JSON is already printed
        pass

