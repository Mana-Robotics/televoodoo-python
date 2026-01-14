"""Rate-limited pose output example.

This example demonstrates using rate limiting to cap the frequency of pose
data from the phone. Useful when your downstream consumer (robot, simulation)
can only handle a limited update rate.

Key features:
- Caps output to a maximum frequency (e.g., 30 Hz)
- Drops excess poses while keeping the latest
- No added latency - poses are forwarded immediately when allowed
"""

import argparse
from televoodoo import start_televoodoo, PoseProvider, load_config

parser = argparse.ArgumentParser()
parser.add_argument(
    "--rate-limit-hz",
    type=float,
    default=None,
    help="Maximum frequency in Hz (e.g., 30). If not provided, no rate limiting is applied.",
)
parser.add_argument("--config", type=str, default=None, help="Config file path")
parser.add_argument(
    "--connection",
    type=str,
    choices=["auto", "ble", "wifi", "usb"],
    default="auto",
    help="Connection type: 'auto' (default), 'ble', 'wifi', or 'usb'",
)
args = parser.parse_args()

# Load config (optional)
config = load_config(args.config)
pose_provider = PoseProvider(config)

# Counter for statistics
pose_count = 0

# Get rate limit value
rate_limit_hz = args.rate_limit_hz


def on_pose(evt):
    """Called at rate-limited frequency with real poses."""
    global pose_count

    pose = pose_provider.get_absolute(evt)
    if pose is None:
        return

    pose_count += 1

    # Print every pose with counter
    print(
        f"[{pose_count:4d}] "
        f"x={pose['x']:+.3f} y={pose['y']:+.3f} z={pose['z']:+.3f}"
    )


if rate_limit_hz:
    print(f"Starting with {rate_limit_hz} Hz rate limit via {args.connection}...")
    print("Excess poses will be dropped to maintain this rate.")
else:
    print("=" * 65)
    print("NO RATE LIMITING - PLEASE PROVIDE CLI FLAG --rate-limit-hz <value>")
    print("Example: python data_rate_limiting.py --rate-limit-hz 30")
    print("=" * 65)
    print(f"\nStarting without rate limiting via {args.connection}...")

print("Ctrl+C to exit.\n")

start_televoodoo(
    callback=on_pose,
    connection=args.connection,
    rate_limit_hz=rate_limit_hz,
    quiet=True,
)
