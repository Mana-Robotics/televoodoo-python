"""High-frequency robot control using upsampled pose data.

This example demonstrates using upsampling to convert phone poses (30-60 Hz)
to a higher frequency (200 Hz) suitable for robot arm control, using linear
extrapolation to predict poses between real samples.

Key features:
- Outputs at fixed intervals (regulated mode, default) for consistent timing
- Extrapolated poses fill gaps between real samples
- Extrapolation automatically stops if phone disconnects (safety)
- Up to ~5ms latency at 200 Hz (one tick) for timing consistency
"""

import argparse
from televoodoo import start_televoodoo, PoseProvider, load_config

parser = argparse.ArgumentParser()
parser.add_argument("--hz", type=float, default=200.0, help="Target frequency in Hz")
parser.add_argument("--config", type=str, default=None, help="Config file path")
parser.add_argument(
    "--connection",
    type=str,
    choices=["auto", "ble", "wifi"],
    default="auto",
    help="Connection type: 'auto' (default), 'ble', or 'wifi'",
)
args = parser.parse_args()

# Load config (optional)
config = load_config(args.config)
pose_provider = PoseProvider(config)

# Counter for statistics
pose_count = 0


def robot_handler(evt):
    """Called at ~200 Hz with real or extrapolated poses."""
    global pose_count
    
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    pose_count += 1
    
    # Print every 200th pose (roughly once per second at 200 Hz)
    if pose_count % 200 == 0:
        print(
            f"[{pose_count}] "
            f"dx={delta['dx']:+.4f} dy={delta['dy']:+.4f} dz={delta['dz']:+.4f}"
        )
    
    # In a real application, send to robot:
    # robot.send_delta(delta['dx'], delta['dy'], delta['dz'])


print(f"Starting with {args.hz} Hz upsampling via {args.connection}...")
print("Using regulated mode (default) for consistent timing.")
print("Ctrl+C to exit.\n")

# Just pass upsample_to_hz - resampling is handled internally
start_televoodoo(
    callback=robot_handler,
    connection=args.connection,
    upsample_to_hz=args.hz,
    quiet=True,
)
