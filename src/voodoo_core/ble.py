import json
import platform
from typing import Callable, Dict, Any, Optional
import qrcode
import random
import string
import time
from typing import Callable, Iterator
from .pose import Pose


def generate_session() -> tuple[str, str]:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
    name = f"prsntr{suffix}"
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return name, code


def simulate_pose_stream() -> Iterator[Pose]:
    t = 0.0
    while True:
        t += 0.05
        yield Pose(
            pose_start=True,
            x=0.1 * random.uniform(-1, 1),
            y=0.1 * random.uniform(-1, 1),
            z=0.1 * random.uniform(-1, 1),
            x_rot=0.0,
            y_rot=0.0,
            z_rot=0.0,
            qx=0.0,
            qy=0.0,
            qz=0.0,
            qw=1.0,
        )
        time.sleep(0.033)


def run_simulation(on_pose: Callable[[Pose], None]) -> None:
    for p in simulate_pose_stream():
        on_pose(p)


def _print_session_and_qr(name: str, code: str) -> None:
    print(json.dumps({"type": "session", "name": name, "code": code}), flush=True)
    try:
        payload = json.dumps({"name": name, "code": code})
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.make()
        qr.print_ascii(invert=True)
    except Exception:
        # QR printing is best-effort; session JSON is already printed
        pass


def start_peripheral(callback: Optional[Callable[[Dict[str, Any]], None]] = None, quiet: bool = False) -> None:
    """Generate a session and start the platform BLE peripheral.

    When quiet=True, suppress only high-frequency event prints (pose, heartbeat),
    but still print the session/QR and connection status messages needed by the app.
    """
    name, code = generate_session()
    # Always print session/QR so clients can connect
    _print_session_and_qr(name, code)

    system = platform.system().lower()
    distro = ""
    if system == "linux":
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                content = f.read().lower()
                if "ubuntu" in content:
                    distro = "ubuntu"
        except Exception:
            pass

    try:
        if system == "darwin":
            import televoodoo.ble_peripheral_macos as _mac  # type: ignore
            try:
                _mac.QUIET_HIGH_FREQUENCY = bool(quiet)  # type: ignore[attr-defined]
            except Exception:
                pass
            _mac.run_macos_peripheral(name, code, callback)
        elif system == "linux" and distro == "ubuntu":
            import televoodoo.ble_peripheral_ubuntu as _ubu  # type: ignore
            try:
                _ubu.QUIET_HIGH_FREQUENCY = bool(quiet)  # type: ignore[attr-defined]
            except Exception:
                pass
            _ubu.run_ubuntu_peripheral(name, code, callback)
        else:
            raise RuntimeError(f"Unsupported platform for BLE peripheral: {platform.platform()}")
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"BLE peripheral failed: {e}"}), flush=True)



