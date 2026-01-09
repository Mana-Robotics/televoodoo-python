"""Measure pose input frequency."""

import argparse
import time
from datetime import datetime
from pathlib import Path
from televoodoo import start_televoodoo

parser = argparse.ArgumentParser()
parser.add_argument("--samples", type=int, default=100, help="Number of samples")
parser.add_argument("--plot", action="store_true", help="Save Δt plot to example directory")
args = parser.parse_args()

timestamps = []
deltas_ms = []
done = False

# macOS: stop CoreFoundation run loop gracefully
try:
    import CoreFoundation as CF
except ImportError:
    CF = None

def on_pose(evt):
    global done, deltas_ms
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
        if CF:
            CF.CFRunLoopStop(CF.CFRunLoopGetMain())

start_televoodoo(callback=on_pose, quiet=True)

# Save plot if requested
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

