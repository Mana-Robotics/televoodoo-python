"""Measure pose input frequency."""

import argparse
import os
import sys
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
    choices=["auto", "ble", "wlan"],
    default="auto",
    dest="connection",
    help="Connection type: 'auto' (default), 'ble', or 'wlan'",
)
parser.add_argument("--wlan-port", type=int, default=50000, help="UDP port for WLAN")
args = parser.parse_args()

timestamps = []
done = False

# macOS: stop CoreFoundation run loop gracefully
try:
    import CoreFoundation as CF
except ImportError:
    CF = None


def save_plot_and_exit(deltas_ms: list):
    """Save plot if requested, then exit."""
    if args.plot and deltas_ms:
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 4))
            plt.plot(deltas_ms, linewidth=1)
            plt.xlabel("Sample")
            plt.ylabel("Δt (ms)")
            mean_ms = sum(deltas_ms) / len(deltas_ms)
            hz = 1000 / mean_ms if mean_ms > 0 else 0
            plt.title(f"Δt between samples (mean={mean_ms:.1f}ms, ~{hz:.1f} Hz)")
            plt.tight_layout()
            filename = Path(__file__).parent / f"frequency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(filename, dpi=150)
            print(f"Saved plot to {filename}")
        except ImportError:
            print("matplotlib not installed. Run: pip install matplotlib")
    
    # Exit based on connection type
    if CF:
        # macOS BLE: stop the run loop gracefully
        CF.CFRunLoopStop(CF.CFRunLoopGetMain())
    else:
        # WLAN or Linux: force exit since server blocks
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
        print(f"\n{len(timestamps)} samples: mean={mean_ms:.1f}ms (~{hz:.1f} Hz)")
        
        # Save plot and exit from within the callback
        save_plot_and_exit(deltas_ms)


start_televoodoo(callback=on_pose, quiet=True, connection=args.connection, wlan_port=args.wlan_port)
