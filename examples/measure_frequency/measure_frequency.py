"""Measure pose input frequency.

Can also measure upsampled frequency to verify upsampling output rate.
"""

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from televoodoo import start_televoodoo

parser = argparse.ArgumentParser()
parser.add_argument("--samples", type=int, default=100, help="Number of samples")
parser.add_argument("--plot", action="store_true", help="Save Δt plot to example directory")
parser.add_argument(
    "--connection", "--transport",
    type=str,
    choices=["auto", "ble", "wifi", "usb"],
    default="auto",
    dest="connection",
    help="Connection type: 'auto' (default), 'ble', 'wifi', or 'usb'",
)
parser.add_argument("--wifi-port", type=int, default=50000, help="UDP port for WIFI")
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
args = parser.parse_args()

timestamps = []
done = False

# macOS: stop CoreFoundation run loop gracefully
try:
    import CoreFoundation as CF
except ImportError:
    CF = None


def save_data_csv(timestamps_list: list, deltas_ms: list):
    """Save measurement data to CSV file."""
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = Path(__file__).parent / f"frequency_{timestamp_str}.csv"
    
    with open(filename, 'w') as f:
        f.write("sample,timestamp,delta_ms\n")
        for i, ts in enumerate(timestamps_list):
            delta = deltas_ms[i - 1] if i > 0 else 0.0
            f.write(f"{i},{ts:.6f},{delta:.3f}\n")
    
    print(f"Saved data to {filename}")
    return timestamp_str


def save_plot(deltas_ms: list, timestamp_str: str):
    """Save plot if requested."""
    if not args.plot or not deltas_ms:
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
        print(f"Saved plot to {filename}")
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")


def save_and_exit(timestamps_list: list, deltas_ms: list):
    """Save data and plot, then exit."""
    # Always save CSV data
    timestamp_str = save_data_csv(timestamps_list, deltas_ms)
    
    # Save plot if requested
    save_plot(deltas_ms, timestamp_str)
    
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
    
    timestamps.append(time.time())
    print(f"Collecting... {len(timestamps)}/{args.samples}", end="\r")
    
    if len(timestamps) >= args.samples:
        done = True
        deltas_ms = [(timestamps[i+1] - timestamps[i]) * 1000 for i in range(len(timestamps)-1)]
        mean_ms = sum(deltas_ms) / len(deltas_ms)
        hz = 1000 / mean_ms if mean_ms > 0 else 0
        mode = f"upsampled to {args.upsample_hz} Hz" + (" (no-regulated)" if args.no_regulated else "") if args.upsample_hz else "raw"
        print(f"\n{len(timestamps)} samples ({mode}): mean={mean_ms:.1f}ms (~{hz:.1f} Hz)")
        
        # Save data, plot, and exit
        save_and_exit(timestamps, deltas_ms)


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
    wifi_port=args.wifi_port,
    upsample_to_hz=args.upsample_hz,
    regulated=regulated,
)
