"""Televoodoo CLI entry point.

Usage:
    python -m televoodoo [--name NAME] [--code CODE] [--config CONFIG]
"""

import argparse
import json
import sys
import threading
import time

from televoodoo import start_televoodoo, PoseProvider
from televoodoo.config import OutputConfig
from televoodoo.ble import run_simulation


def main() -> int:
    parser = argparse.ArgumentParser(description="Televoodoo - 6DoF pose streaming")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Static peripheral name (default: randomly generated)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Static authentication code (default: randomly generated 6-char code)",
    )
    parser.add_argument(
        "--connection",
        type=str,
        choices=["auto", "ble", "wlan"],
        default="auto",
        help="Connection type (default: auto-detect)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run pose simulation instead of waiting for phone connection",
    )
    args = parser.parse_args()

    config = OutputConfig(
        includeFormats={
            "absolute_input": True,
            "delta_input": False,
            "absolute_transformed": True,
            "delta_transformed": False,
        },
        includeOrientation={
            "quaternion": True,
            "euler_radian": False,
            "euler_degree": False,
        },
        scale=1.0,
        outputAxes={"x": 1.0, "y": 1.0, "z": 1.0},
    )
    pose_provider = PoseProvider(config)

    def on_pose(pose):
        out = pose_provider.transform(pose)
        print(json.dumps({"type": "pose", "data": out}), flush=True)

    # Heartbeat thread
    def heartbeat():
        counter = 0
        while True:
            counter += 1
            print(
                json.dumps({"type": "service_heartbeat", "counter": counter}),
                flush=True,
            )
            time.sleep(1.0)

    threading.Thread(target=heartbeat, daemon=True).start()

    if args.simulate:
        # Run simulation without phone connection
        run_simulation(on_pose)
    else:
        # Start Televoodoo and wait for phone connection
        start_televoodoo(
            name=args.name,
            code=args.code,
            connection=args.connection,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
