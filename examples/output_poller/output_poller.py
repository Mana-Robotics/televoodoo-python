import argparse
import json
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from televoodoo import Pose, PoseProvider, load_config, start_televoodoo


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll current OUTPUT pose at a fixed rate")
    parser.add_argument("--config", type=str, required=True, help="Path to voodoo_settings.json")
    parser.add_argument("--hz", type=float, default=5.0, help="Polling frequency in Hz (default 5)")
    args = parser.parse_args()

    # Load config and create pose provider
    voodoo_config = load_config(args.config)
    pose_provider = PoseProvider(voodoo_config)

    # Shared latest pose
    voodoo_latest_pose: Dict[str, Any] = {}
    voodoo_latest_pose_lock = threading.Lock()

    # Teleoperation event callback: feed incoming poses into provider
    def on_teleop_event(evt: Dict[str, Any]) -> None:
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return
        out = pose_provider.transform(pose)
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
        # Use credentials from config if specified
        start_televoodoo(
            on_teleop_event,
            quiet=True,
            name=voodoo_config.auth_name,
            code=voodoo_config.auth_code
        )
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Televoodoo failed: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
