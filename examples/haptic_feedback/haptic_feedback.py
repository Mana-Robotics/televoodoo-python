"""Haptic feedback example with simulated sensor values.

Demonstrates sending haptic feedback to the iOS app using a sine wave
to simulate changing sensor values (e.g., force feedback from a robot).
Also displays the latest pose values received from the phone.
"""

from __future__ import annotations

import argparse
import math
import threading
import time

from televoodoo import start_televoodoo, send_haptic, PoseProvider, load_config


# Simulation parameters
PERIOD_SECONDS = 3.0  # Sine wave period (3 seconds)
UPDATE_RATE_HZ = 20   # Haptic update frequency

# Shared state for latest pose (protected by lock)
_pose_lock = threading.Lock()
_latest_pose: dict | None = None


def haptic_simulation_loop():
    """Simulate changing sensor values with a sine wave.
    
    Runs in a background thread and sends haptic feedback to the iOS app.
    The sine wave oscillates between 0.0 and 1.0 with a 3-second period.
    """
    # Wait for QR code to be printed before starting display updates
    time.sleep(1.0)
    
    start_time = time.monotonic()
    
    while True:
        # Calculate elapsed time
        elapsed = time.monotonic() - start_time
        
        # Generate sine wave value (0.0 to 1.0)
        # sin outputs -1 to 1, so we normalize to 0 to 1
        raw_sine = math.sin(2 * math.pi * elapsed / PERIOD_SECONDS)
        value = (raw_sine + 1.0) / 2.0  # Normalize to 0.0 - 1.0
        
        # Send haptic feedback (already normalized, so min=0, max=1)
        sent = send_haptic(value, min_value=0.0, max_value=1.0)
        
        # Build haptic bar
        bar_length = int(value * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        status = "✓" if sent else "○"
        haptic_line = f"{status} Haptic: [{bar}] {value:.2f}"
        
        # Get latest pose (thread-safe)
        with _pose_lock:
            pose = _latest_pose
        
        # Build pose line
        if pose is not None:
            pose_line = (
                f"  Pose: x={pose['x']:+.3f} y={pose['y']:+.3f} z={pose['z']:+.3f} | "
                f"qw={pose['qw']:+.3f} qx={pose['qx']:+.3f} qy={pose['qy']:+.3f} qz={pose['qz']:+.3f}"
            )
        else:
            pose_line = "  Pose: waiting for data..."
        
        # Print both lines (use ANSI escape to move cursor up and clear)
        # \033[2K clears the line, \033[1A moves cursor up
        print(f"\r\033[K{haptic_line}\n\033[K{pose_line}\033[1A", end="", flush=True)
        
        # Sleep until next update
        time.sleep(1.0 / UPDATE_RATE_HZ)


def main():
    global _latest_pose
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Haptic feedback example with simulated sensor values."
    )
    parser.add_argument(
        "--connection",
        type=str,
        choices=["auto", "wifi", "ble"],
        default="auto",
        help="Connection type: auto (default), wifi, or ble",
    )
    args = parser.parse_args()
    
    print("Haptic Feedback Example")
    print("=" * 80)
    print(f"Simulating sine wave with {PERIOD_SECONDS}s period")
    print(f"Update rate: {UPDATE_RATE_HZ} Hz")
    print(f"Connection: {args.connection}")
    print()
    print("✓ = haptic sent, ○ = no client connected")
    print()
    print()  # Extra line for pose display
    
    # Start haptic simulation in background thread
    haptic_thread = threading.Thread(target=haptic_simulation_loop, daemon=True)
    haptic_thread.start()
    
    # Load config and create pose provider (for teleoperation callback)
    config = load_config()
    pose_provider = PoseProvider(config)
    
    def on_teleop_event(evt):
        """Handle teleoperation events and store latest pose."""
        global _latest_pose
        
        pose = pose_provider.get_absolute(evt)
        if pose is None:
            return
        
        # Store latest pose (thread-safe)
        with _pose_lock:
            _latest_pose = pose
    
    # Start televoodoo (blocks until disconnected)
    # The haptic thread will run in the background
    start_televoodoo(callback=on_teleop_event, quiet=True, connection=args.connection)


if __name__ == "__main__":
    main()
