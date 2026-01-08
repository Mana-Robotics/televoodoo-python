import argparse
import json
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from televoodoo import Pose, PoseTransformer, load_config
from televoodoo.ble import generate_session, start_peripheral


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll current OUTPUT pose at a fixed rate")
    parser.add_argument("--config", type=str, required=True, help="Path to voodoo_settings.json")
    parser.add_argument("--hz", type=float, default=5.0, help="Polling frequency in Hz (default 5)")
    args = parser.parse_args()

    # start_peripheral prints session + QR and starts BLE

    # Load config and create transformer
    voodoo_config = load_config(args.config)
    voodoo_transformer = PoseTransformer(voodoo_config)

    # Shared latest pose
    voodoo_latest_pose: Dict[str, Any] = {}
    voodoo_latest_pose_lock = threading.Lock()

    # BLE event callback: feed incoming poses into transformer; mirror events to stdout
    def evt_cb(evt: Dict[str, Any]) -> None:
        # print(json.dumps(evt), flush=True)  # comment out verbose input logging
        if evt.get("type") == "pose":
            ai = evt.get("data", {}).get("absolute_input", {})
            try:
                pose = Pose(
                    movement_start=bool(ai.get("movement_start", False)),
                    x=float(ai.get("x", 0.0)),
                    y=float(ai.get("y", 0.0)),
                    z=float(ai.get("z", 0.0)),
                    x_rot=float(ai.get("x_rot", 0.0)),
                    y_rot=float(ai.get("y_rot", 0.0)),
                    z_rot=float(ai.get("z_rot", 0.0)),
                    qx=float(ai.get("qx", 0.0)),
                    qy=float(ai.get("qy", 0.0)),
                    qz=float(ai.get("qz", 0.0)),
                    qw=float(ai.get("qw", 1.0)),
                )
            except Exception:
                return
            out = voodoo_transformer.transform(pose)
            with voodoo_latest_pose_lock:
                voodoo_latest_pose.clear()
                voodoo_latest_pose.update(out)

    # Poller at requested frequency (background thread)
    period = 1.0 / max(0.1, float(args.hz))

    def poller() -> None:
        while True:
            time.sleep(period)
            with voodoo_latest_pose_lock:
                if voodoo_latest_pose:
                    print(json.dumps({"polled_output": voodoo_latest_pose}), flush=True)

    t_poll = threading.Thread(target=poller, daemon=True)
    t_poll.start()

    # Graceful shutdown on Ctrl+C / SIGTERM by stopping the CoreFoundation main run loop
    try:
        import CoreFoundation as CF  # type: ignore
    except Exception:
        CF = None  # type: ignore

    def stop_run_loop(*_args: object) -> None:
        if CF is not None:
            try:
                CF.CFRunLoopStop(CF.CFRunLoopGetMain())
            except Exception:
                pass

    # Only install CoreFoundation stop handler on macOS; on other platforms,
    # keep default SIGINT behavior so Ctrl+C raises KeyboardInterrupt.
    if CF is not None:
        signal.signal(signal.SIGINT, lambda *_: stop_run_loop())
        signal.signal(signal.SIGTERM, lambda *_: stop_run_loop())

    try:
        # Use BLE credentials from config if specified
        start_peripheral(
            evt_cb,
            quiet=True,
            name=voodoo_config.ble_name,
            code=voodoo_config.ble_code
        )
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"BLE peripheral failed: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


