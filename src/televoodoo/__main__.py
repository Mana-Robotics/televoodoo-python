"""Televoodoo CLI entry point.

Usage:
    python -m televoodoo [--name NAME] [--code CODE] [--config CONFIG]
    python -m televoodoo --connection wifi [--tcp-port 50000]
    python -m televoodoo --connection usb
    python -m televoodoo --log-data delta_transformed,velocity --log-format quaternion,euler_degree
"""

import argparse
import json
import sys

from televoodoo import start_televoodoo, PoseProvider, load_config
from televoodoo.pose import Pose
from televoodoo.tcp_service import DEFAULT_TCP_PORT, DEFAULT_BEACON_PORT


def main() -> int:
    parser = argparse.ArgumentParser(description="Televoodoo - 6DoF pose streaming")
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Path to config JSON file (for transforms, limits, credentials)",
    )
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
        choices=["auto", "ble", "wifi", "usb"],
        default="auto",
        dest="connection",
        help="Connection type: 'auto' (default), 'ble', 'wifi', or 'usb'",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=DEFAULT_TCP_PORT,
        help=f"TCP port for data (default: {DEFAULT_TCP_PORT})",
    )
    parser.add_argument(
        "--beacon-port",
        type=int,
        default=DEFAULT_BEACON_PORT,
        help=f"UDP port for beacon broadcast (default: {DEFAULT_BEACON_PORT})",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress high-frequency logging (pose, heartbeat)",
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
    parser.add_argument(
        "--vel-limit",
        type=float,
        default=None,
        help="Maximum velocity in m/s (limits position changes for safety)",
    )
    parser.add_argument(
        "--acc-limit",
        type=float,
        default=None,
        help="Maximum acceleration in m/s² (symmetric, applies to deceleration too)",
    )
    parser.add_argument(
        "--log-data",
        type=str,
        default=None,
        help="Comma-separated list of data to log: absolute_input,delta_input,absolute_transformed,delta_transformed,velocity",
    )
    parser.add_argument(
        "--log-format",
        type=str,
        default=None,
        help="Comma-separated list of orientation formats to log: quaternion,rotation_vector,euler_radian,euler_degree",
    )
    args = parser.parse_args()

    # Valid options for --log-data and --log-format
    VALID_LOG_DATA = {"absolute_input", "delta_input", "absolute_transformed", "delta_transformed", "velocity"}
    VALID_LOG_FORMAT = {"quaternion", "rotation_vector", "euler_radian", "euler_degree"}

    # Load config from file if specified, otherwise use defaults
    config = load_config(args.config if args.config else None)

    # Override logData from CLI if specified
    if args.log_data is not None:
        requested = set(args.log_data.split(",")) if args.log_data else set()
        # Filter out empty strings from splitting
        requested = {r.strip() for r in requested if r.strip()}
        # Warn about unknown options
        unknown = requested - VALID_LOG_DATA
        if unknown:
            print(json.dumps({
                "type": "warning",
                "message": f"Unknown --log-data option(s): {', '.join(sorted(unknown))}. Valid options: {', '.join(sorted(VALID_LOG_DATA))}"
            }), flush=True)
        config.logData = {
            "absolute_input": "absolute_input" in requested,
            "delta_input": "delta_input" in requested,
            "absolute_transformed": "absolute_transformed" in requested,
            "delta_transformed": "delta_transformed" in requested,
            "velocity": "velocity" in requested,
        }

    # Override logDataFormat from CLI if specified
    if args.log_format is not None:
        requested = set(args.log_format.split(",")) if args.log_format else set()
        # Filter out empty strings from splitting
        requested = {r.strip() for r in requested if r.strip()}
        # Warn about unknown options
        unknown = requested - VALID_LOG_FORMAT
        if unknown:
            print(json.dumps({
                "type": "warning",
                "message": f"Unknown --log-format option(s): {', '.join(sorted(unknown))}. Valid options: {', '.join(sorted(VALID_LOG_FORMAT))}"
            }), flush=True)
        config.logDataFormat = {
            "quaternion": "quaternion" in requested,
            "rotation_vector": "rotation_vector" in requested,
            "euler_radian": "euler_radian" in requested,
            "euler_degree": "euler_degree" in requested,
        }

    pose_provider = PoseProvider(config)

    def on_pose(evt):
        # evt is an event dict like {"type": "pose", "data": {"absolute_input": {...}}}
        if args.quiet:
            return  # Suppress pose output in quiet mode
        # Convert to Pose object for transform()
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return  # Not a pose event
        out = pose_provider.transform(pose)
        print(json.dumps({"type": "pose", "data": out}), flush=True)

    # Start Televoodoo and wait for phone connection
    # Resampling is handled internally when upsample_to_hz or rate_limit_hz is set
    # regulated=None uses default (True when upsampling), False disables it
    regulated = False if args.no_regulated else None
    
    start_televoodoo(
        callback=on_pose,
        name=args.name or config.auth_name,
        code=args.code or config.auth_code,
        connection=args.connection,
        quiet=True,  # Suppress raw pose output; callback handles transformed output
        tcp_port=args.tcp_port,
        beacon_port=args.beacon_port,
        config=config,  # Pass config for settings from config file
        upsample_to_hz=args.upsample_hz,  # CLI args override config
        rate_limit_hz=args.rate_limit_hz,
        regulated=regulated,
        vel_limit=args.vel_limit,
        acc_limit=args.acc_limit,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
