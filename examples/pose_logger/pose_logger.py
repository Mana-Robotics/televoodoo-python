import argparse
import json
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from televoodoo import Pose, PoseProvider, load_config, start_televoodoo
from televoodoo.ble import run_simulation


def main() -> int:
    parser = argparse.ArgumentParser(description="Log poses using Televoodoo")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON OutputConfig (same format the app saves)",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Use simulation mode instead of BLE peripheral (default)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Auto-exit after N seconds (works in both simulated and BLE modes)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Static BLE peripheral name (default: randomly generated)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Static authentication code (default: randomly generated 6-char code)",
    )
    args = parser.parse_args()

    # Build pose provider from config
    cfg = load_config(args.config)
    pose_provider = PoseProvider(cfg)

    if not args.sim:  # Default to BLE mode
        # Graceful shutdown on Ctrl+C / SIGTERM by stopping the CoreFoundation main run loop (macOS only)
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

        if CF is not None:
            signal.signal(signal.SIGINT, lambda *_: stop_run_loop())
            signal.signal(signal.SIGTERM, lambda *_: stop_run_loop())

        # Optional auto-exit timer (best-effort on macOS by stopping CF run loop)
        if args.duration is not None and CF is not None:
            def timer_stop() -> None:
                time.sleep(max(0.0, float(args.duration)))
                stop_run_loop()
            threading.Thread(target=timer_stop, daemon=True).start()

        def on_teleop_event(evt: Dict[str, Any]) -> None:
            pose = Pose.from_teleop_event(evt)
            if pose is None:
                return
            out = pose_provider.transform(pose)
            print(json.dumps(out), flush=True)

        try:
            # CLI args override config file; config file overrides random
            auth_name = args.name or cfg.auth_name
            auth_code = args.code or cfg.auth_code
            start_televoodoo(on_teleop_event, quiet=True, name=auth_name, code=auth_code)
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"Televoodoo failed: {e}"}), flush=True)
        return 0
    else:  # sim
        def on_pose(pose: Pose) -> None:
            out = pose_provider.transform(pose)
            print(json.dumps(out), flush=True)

        if args.duration is not None:
            t = threading.Thread(target=run_simulation, args=(on_pose,), daemon=True)
            t.start()
            time.sleep(max(0.0, float(args.duration)))
        else:
            try:
                run_simulation(on_pose)
            except KeyboardInterrupt:
                pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
