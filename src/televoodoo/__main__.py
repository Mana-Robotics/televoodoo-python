"""Televoodoo CLI entry point.

Usage:
    python -m televoodoo [--name NAME] [--code CODE] [--config CONFIG]
    python -m televoodoo --transport wifi [--wifi-port 50000]
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
        help="Static peripheral/server name (default: randomly generated)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Static authentication code (default: randomly generated 6-char code)",
    )
    parser.add_argument(
        "--connection",
        "--transport",
        type=str,
        choices=["auto", "ble", "wifi"],
        default="auto",
        dest="connection",
        help="Connection type: 'auto' (default), 'ble', or 'wifi'",
    )
    parser.add_argument(
        "--wifi-port",
        type=int,
        default=50000,
        help="UDP port for WIFI server (default: 50000)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress high-frequency logging (pose, heartbeat)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run pose simulation instead of waiting for phone connection",
    )
    parser.add_argument(
        "--upsample-hz",
        type=float,
        default=None,
        help="Upsample poses to target frequency (Hz) using linear extrapolation",
    )
    parser.add_argument(
        "--rate-limit-hz",
        type=float,
        default=None,
        help="Rate limit pose output to maximum frequency (Hz)",
    )
    parser.add_argument(
        "--no-regulated",
        action="store_true",
        dest="no_regulated",
        help="Disable fixed-interval timing (zero latency but irregular timing)",
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
        # Resampling is handled internally when upsample_to_hz or rate_limit_hz is set
        # regulated=None uses default (True when upsampling), False disables it
        regulated = False if args.no_regulated else None
        
        start_televoodoo(
            callback=on_pose,
            name=args.name,
            code=args.code,
            connection=args.connection,
            quiet=args.quiet,
            wifi_port=args.wifi_port,
            upsample_to_hz=args.upsample_hz,
            rate_limit_hz=args.rate_limit_hz,
            regulated=regulated,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
