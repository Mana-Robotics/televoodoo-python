"""Measure pose input frequency.

Can also measure upsampled frequency to verify upsampling output rate.
Optionally calculate pose deltas (euclidean distances between consecutive samples).
"""

import argparse
import math
import os
import time
from datetime import datetime
from pathlib import Path
from televoodoo import start_televoodoo, PoseProvider, load_config

parser = argparse.ArgumentParser()
parser.add_argument("--samples", type=int, default=100, help="Number of samples")
parser.add_argument("--no-plot", action="store_true", help="Disable saving plots")
parser.add_argument(
    "--connection", "--transport",
    type=str,
    choices=["auto", "ble", "wifi", "usb"],
    default="auto",
    dest="connection",
    help="Connection type: 'auto' (default), 'ble', 'wifi', or 'usb'",
)
parser.add_argument("--tcp-port", type=int, default=50000, help="TCP port for data")
parser.add_argument(
    "--upsample-hz",
    type=float,
    default=None,
    help="Upsample to target frequency (Hz) using linear extrapolation",
)
parser.add_argument(
    "--no-regulated",
    action="store_true",
    dest="no_regulated",
    help="Disable fixed-interval timing (zero latency but irregular timing)",
)
parser.add_argument(
    "--pose-deltas",
    action="store_true",
    dest="pose_deltas",
    help="Calculate and plot euclidean distances between consecutive pose samples",
)
parser.add_argument(
    "--use-delta",
    action="store_true",
    dest="use_delta",
    help="Use get_delta() instead of get_absolute() for pose data (dx/dy/dz from origin)",
)
parser.add_argument(
    "--plot-variants",
    action="store_true",
    dest="plot_variants",
    help="Generate pose delta plots for raw, up60hz, and up100hz variants from recorded raw data",
)
args = parser.parse_args()

# --plot-variants implies --pose-deltas and disables live upsampling
if args.plot_variants:
    args.pose_deltas = True
    if args.upsample_hz:
        print("Warning: --plot-variants disables --upsample-hz (raw data needed for offline resampling)")
        args.upsample_hz = None

timestamps = []
poses = []  # Store pose data for delta calculations
raw_poses_with_timestamps = []  # For --plot-variants: raw poses with timestamps
done = False

# Initialize PoseProvider if pose deltas are requested
pose_provider = None
if args.pose_deltas:
    config = load_config()
    pose_provider = PoseProvider(config)

# macOS: stop CoreFoundation run loop gracefully
try:
    import CoreFoundation as CF
except ImportError:
    CF = None


def save_frequency_csv(timestamps_list: list, deltas_ms: list):
    """Save frequency measurement data to CSV file."""
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = Path(__file__).parent / f"frequency_{timestamp_str}.csv"
    
    with open(filename, 'w') as f:
        f.write("sample,timestamp,delta_ms\n")
        for i, ts in enumerate(timestamps_list):
            delta = deltas_ms[i - 1] if i > 0 else 0.0
            f.write(f"{i},{ts:.6f},{delta:.3f}\n")
    
    print(f"Saved frequency data to {filename}")
    return timestamp_str


def save_frequency_plot(deltas_ms: list, timestamp_str: str):
    """Save frequency plot."""
    if args.no_plot or not deltas_ms:
        return
    
    try:
        # Use non-interactive backend (required when called from background thread)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 4))
        plt.plot(deltas_ms, linewidth=1)
        plt.xlabel("Sample")
        plt.ylabel("Δt (ms)")
        mean_ms = sum(deltas_ms) / len(deltas_ms)
        hz = 1000 / mean_ms if mean_ms > 0 else 0
        plt.title(f"Δt between samples (mean={mean_ms:.1f}ms, ~{hz:.1f} Hz)")
        plt.tight_layout()
        filename = Path(__file__).parent / f"frequency_{timestamp_str}.png"
        plt.savefig(filename, dpi=150)
        plt.close()
        print(f"Saved frequency plot to {filename}")
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")


def calculate_pose_deltas(poses_list: list):
    """Calculate euclidean distances between consecutive poses."""
    deltas = []
    for i in range(1, len(poses_list)):
        prev = poses_list[i - 1]
        curr = poses_list[i]
        dx = curr['x'] - prev['x']
        dy = curr['y'] - prev['y']
        dz = curr['z'] - prev['z']
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)
        deltas.append(distance)
    return deltas


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b."""
    return a + (b - a) * t


def resample_poses_offline(raw_poses: list, target_hz: float) -> list:
    """Resample recorded poses to target frequency using linear interpolation.
    
    Args:
        raw_poses: List of dicts with 'timestamp', 'x', 'y', 'z' keys.
        target_hz: Target output frequency in Hz.
    
    Returns:
        List of resampled poses with 'x', 'y', 'z' keys.
    """
    if len(raw_poses) < 2:
        return raw_poses
    
    # Calculate time range
    t_start = raw_poses[0]['timestamp']
    t_end = raw_poses[-1]['timestamp']
    duration = t_end - t_start
    
    if duration <= 0:
        return raw_poses
    
    # Generate timestamps at target frequency
    interval = 1.0 / target_hz
    resampled = []
    
    t = t_start
    raw_idx = 0
    
    while t <= t_end:
        # Find the two raw poses surrounding this timestamp
        while raw_idx < len(raw_poses) - 1 and raw_poses[raw_idx + 1]['timestamp'] < t:
            raw_idx += 1
        
        if raw_idx >= len(raw_poses) - 1:
            # Use last pose
            p = raw_poses[-1]
            resampled.append({'x': p['x'], 'y': p['y'], 'z': p['z']})
        else:
            # Interpolate between raw_idx and raw_idx + 1
            p0 = raw_poses[raw_idx]
            p1 = raw_poses[raw_idx + 1]
            dt = p1['timestamp'] - p0['timestamp']
            
            if dt > 0:
                alpha = (t - p0['timestamp']) / dt
                alpha = max(0.0, min(1.0, alpha))
                resampled.append({
                    'x': lerp(p0['x'], p1['x'], alpha),
                    'y': lerp(p0['y'], p1['y'], alpha),
                    'z': lerp(p0['z'], p1['z'], alpha),
                })
            else:
                resampled.append({'x': p0['x'], 'y': p0['y'], 'z': p0['z']})
        
        t += interval
    
    return resampled


def save_pose_deltas_csv_variant(poses_list: list, pose_deltas: list, timestamp_str: str, variant: str, use_delta: bool):
    """Save pose delta data to CSV file with variant suffix."""
    filename = Path(__file__).parent / f"pose_deltas_{timestamp_str}_{variant}.csv"
    
    pos_headers = "dx,dy,dz" if use_delta else "x,y,z"
    
    with open(filename, 'w') as f:
        f.write(f"sample,{pos_headers},delta_distance\n")
        for i, pose in enumerate(poses_list):
            delta = pose_deltas[i - 1] if i > 0 else 0.0
            f.write(f"{i},{pose['x']:.6f},{pose['y']:.6f},{pose['z']:.6f},{delta:.6f}\n")
    
    print(f"  Saved {filename.name}")
    return filename


def save_pose_deltas_plot_variant(pose_deltas: list, timestamp_str: str, variant: str, use_delta: bool):
    """Save pose deltas plot with variant suffix."""
    if args.no_plot or not pose_deltas:
        return None
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 4))
        plt.plot(pose_deltas, linewidth=1, color='#e74c3c')
        plt.xlabel("Sample")
        plt.ylabel("Euclidean Distance")
        mean_delta = sum(pose_deltas) / len(pose_deltas)
        max_delta = max(pose_deltas)
        mode_str = "get_delta" if use_delta else "get_absolute"
        plt.title(f"Pose deltas [{mode_str}] [{variant}] (mean={mean_delta:.4f}, max={max_delta:.4f}, n={len(pose_deltas)})")
        plt.tight_layout()
        filename = Path(__file__).parent / f"pose_deltas_{timestamp_str}_{variant}.png"
        plt.savefig(filename, dpi=150)
        plt.close()
        print(f"  Saved {filename.name}")
        return filename
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")
        return None


def generate_pose_delta_variants(raw_poses: list, timestamp_str: str, use_delta: bool):
    """Generate pose delta CSVs and plots for raw, up60hz, up100hz variants."""
    if len(raw_poses) < 2:
        print("Not enough raw poses for variant generation")
        return
    
    variants = [
        ("raw", None),      # No resampling
        ("up60hz", 60.0),   # Upsample to 60Hz
        ("up100hz", 100.0), # Upsample to 100Hz
    ]
    
    print(f"\nGenerating pose delta variants from {len(raw_poses)} raw samples:")
    
    for variant_name, target_hz in variants:
        if target_hz is None:
            # Raw: just use the poses as-is
            poses_list = [{'x': p['x'], 'y': p['y'], 'z': p['z']} for p in raw_poses]
        else:
            # Resample to target frequency
            poses_list = resample_poses_offline(raw_poses, target_hz)
        
        pose_deltas = calculate_pose_deltas(poses_list)
        if pose_deltas:
            mean_delta = sum(pose_deltas) / len(pose_deltas)
            max_delta = max(pose_deltas)
            print(f"\n  [{variant_name}] {len(poses_list)} samples, mean={mean_delta:.4f}, max={max_delta:.4f}")
            save_pose_deltas_csv_variant(poses_list, pose_deltas, timestamp_str, variant_name, use_delta)
            save_pose_deltas_plot_variant(pose_deltas, timestamp_str, variant_name, use_delta)


def save_pose_deltas_csv(poses_list: list, pose_deltas: list, timestamp_str: str, use_delta: bool):
    """Save pose delta data to CSV file."""
    filename = Path(__file__).parent / f"pose_deltas_{timestamp_str}.csv"
    
    # Use dx/dy/dz headers when using get_delta mode
    pos_headers = "dx,dy,dz" if use_delta else "x,y,z"
    
    with open(filename, 'w') as f:
        f.write(f"sample,{pos_headers},delta_distance\n")
        for i, pose in enumerate(poses_list):
            delta = pose_deltas[i - 1] if i > 0 else 0.0
            f.write(f"{i},{pose['x']:.6f},{pose['y']:.6f},{pose['z']:.6f},{delta:.6f}\n")
    
    print(f"Saved pose deltas data to {filename}")


def save_pose_deltas_plot(pose_deltas: list, timestamp_str: str, use_delta: bool):
    """Save pose deltas plot."""
    if args.no_plot or not pose_deltas:
        return
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 4))
        plt.plot(pose_deltas, linewidth=1, color='#e74c3c')
        plt.xlabel("Sample")
        plt.ylabel("Euclidean Distance")
        mean_delta = sum(pose_deltas) / len(pose_deltas)
        max_delta = max(pose_deltas)
        mode_str = "get_delta" if use_delta else "get_absolute"
        plt.title(f"Pose deltas [{mode_str}] (mean={mean_delta:.4f}, max={max_delta:.4f})")
        plt.tight_layout()
        filename = Path(__file__).parent / f"pose_deltas_{timestamp_str}.png"
        plt.savefig(filename, dpi=150)
        plt.close()
        print(f"Saved pose deltas plot to {filename}")
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")


def save_and_exit(timestamps_list: list, deltas_ms: list, poses_list: list, raw_poses: list):
    """Save data and plots, then exit."""
    # Always save frequency CSV data
    timestamp_str = save_frequency_csv(timestamps_list, deltas_ms)
    
    # Save frequency plot (unless --no-plot)
    save_frequency_plot(deltas_ms, timestamp_str)
    
    # Handle --plot-variants: generate raw, up60hz, up100hz variants
    if args.plot_variants and raw_poses:
        generate_pose_delta_variants(raw_poses, timestamp_str, args.use_delta)
    # Save pose deltas if requested (but not if --plot-variants, which handles it differently)
    elif args.pose_deltas and poses_list:
        pose_deltas = calculate_pose_deltas(poses_list)
        if pose_deltas:
            mean_delta = sum(pose_deltas) / len(pose_deltas)
            max_delta = max(pose_deltas)
            mode_str = "get_delta" if args.use_delta else "get_absolute"
            print(f"Pose deltas [{mode_str}]: mean={mean_delta:.4f}, max={max_delta:.4f}")
            save_pose_deltas_csv(poses_list, pose_deltas, timestamp_str, args.use_delta)
            save_pose_deltas_plot(pose_deltas, timestamp_str, args.use_delta)
    
    # Exit based on connection type
    if CF:
        # macOS BLE: stop the run loop gracefully
        CF.CFRunLoopStop(CF.CFRunLoopGetMain())
    else:
        # WIFI or Linux: force exit since server blocks
        os._exit(0)


def on_pose(evt):
    global done
    if done or evt.get("type") != "pose":
        return
    
    now = time.time()
    timestamps.append(now)
    
    # Store pose data if --pose-deltas is enabled
    if args.pose_deltas and pose_provider:
        if args.use_delta:
            pose = pose_provider.get_delta(evt)
            if pose:
                pose_data = {
                    'x': pose['dx'],
                    'y': pose['dy'],
                    'z': pose['dz'],
                }
                poses.append(pose_data)
                # For --plot-variants, also store with timestamp
                if args.plot_variants:
                    raw_poses_with_timestamps.append({**pose_data, 'timestamp': now})
        else:
            pose = pose_provider.get_absolute(evt)
            if pose:
                pose_data = {
                    'x': pose['x'],
                    'y': pose['y'],
                    'z': pose['z'],
                }
                poses.append(pose_data)
                # For --plot-variants, also store with timestamp
                if args.plot_variants:
                    raw_poses_with_timestamps.append({**pose_data, 'timestamp': now})
    
    print(f"Collecting... {len(timestamps)}/{args.samples}", end="\r")
    
    if len(timestamps) >= args.samples:
        done = True
        deltas_ms = [(timestamps[i+1] - timestamps[i]) * 1000 for i in range(len(timestamps)-1)]
        mean_ms = sum(deltas_ms) / len(deltas_ms)
        hz = 1000 / mean_ms if mean_ms > 0 else 0
        mode = f"upsampled to {args.upsample_hz} Hz" + (" (no-regulated)" if args.no_regulated else "") if args.upsample_hz else "raw"
        print(f"\n{len(timestamps)} samples ({mode}): mean={mean_ms:.1f}ms (~{hz:.1f} Hz)")
        
        # Save data, plot, and exit
        save_and_exit(timestamps, deltas_ms, poses, raw_poses_with_timestamps)


if args.upsample_hz:
    mode_str = f"target {args.upsample_hz} Hz"
    if args.no_regulated:
        mode_str += " (no-regulated - irregular timing)"
    else:
        mode_str += " (regulated - fixed timing, default)"
    print(f"Upsampling enabled: {mode_str}")

# Just pass upsample_to_hz - resampling is handled internally
# regulated=None uses default (True when upsampling), False disables it
regulated = False if args.no_regulated else None

start_televoodoo(
    callback=on_pose,
    quiet=True,
    connection=args.connection,
    tcp_port=args.tcp_port,
    upsample_to_hz=args.upsample_hz,
    regulated=regulated,
)
