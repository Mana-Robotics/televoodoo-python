import argparse
import json
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from televoodoo import Pose
from televoodoo.ble import run_simulation, start_peripheral

# Directory where this script lives (for default output path)
SCRIPT_DIR = Path(__file__).parent


def main() -> int:
    # Generate default filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_out = SCRIPT_DIR / f"pose_frequency_{timestamp}.png"

    parser = argparse.ArgumentParser(description="Measure pose input frequency and plot Δt between samples")
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Use simulation mode instead of BLE peripheral (default)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Auto-exit after N seconds (best-effort on macOS for BLE)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(default_out),
        help="Path to save the plot image (PNG). Default: example directory with timestamp",
    )
    args = parser.parse_args()

    deltas_ms: List[float] = []
    last_ts: float | None = None

    def observe_tick() -> None:
        nonlocal last_ts
        now = time.time()
        if last_ts is not None:
            deltas_ms.append((now - last_ts) * 1000.0)
        last_ts = now

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

        def on_ble_event(evt: Dict[str, Any]) -> None:
            # mirror incoming events for context (optional)
            print(json.dumps(evt), flush=True)
            if evt.get("type") == "pose":
                observe_tick()

        # Optional auto-exit timer (best-effort on macOS by stopping CF run loop)
        if args.duration is not None and CF is not None:
            def timer_stop() -> None:
                time.sleep(max(0.0, float(args.duration)))
                stop_run_loop()
            threading.Thread(target=timer_stop, daemon=True).start()

        try:
            start_peripheral(on_ble_event, quiet=True)
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"BLE peripheral failed: {e}"}), flush=True)
    else:
        def on_pose(_pose: Pose) -> None:
            observe_tick()

        if args.duration is not None:
            t = threading.Thread(target=run_simulation, args=(on_pose,), daemon=True)
            t.start()
            time.sleep(max(0.0, float(args.duration)))
        else:
            try:
                run_simulation(on_pose)
            except KeyboardInterrupt:
                pass

    # After run returns, plot and save
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("matplotlib is required for plotting. Install with: pip install matplotlib", flush=True)
        return 1

    if not deltas_ms:
        print("No pose samples captured; nothing to plot.", flush=True)
        return 0

    xs = list(range(len(deltas_ms)))
    plt.figure(figsize=(10, 4))
    plt.plot(xs, deltas_ms, linewidth=1.2)
    plt.xlabel("Sample index")
    plt.ylabel("Δt (ms)")
    try:
        mean_ms = sum(deltas_ms) / len(deltas_ms)
        fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0
        plt.title(f"Pose input Δt over time (mean={mean_ms:.1f} ms, ~{fps:.1f} FPS)")
    except Exception:
        plt.title("Pose input Δt over time")
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Saved plot to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


