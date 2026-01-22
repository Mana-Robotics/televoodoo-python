"""Teleoperate a UFACTORY xArm using Televoodoo 6DoF poses."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

from televoodoo import PoseProvider, load_config, start_televoodoo
from televoodoo import math as tvm

try:
    from xarm.wrapper import XArmAPI
except ImportError:
    XArmAPI = None


def main() -> int:

    # -----------------------------------------------------------------------
    # CLI Arguments
    # -----------------------------------------------------------------------

    default_config = Path(__file__).parent / "xarm_config.json"

    parser = argparse.ArgumentParser(
        description="Stream Televoodoo poses to xArm robot."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(default_config),
        help="Path to Televoodoo config JSON (set scale: 1000.0 for mm output).",
    )
    parser.add_argument(
        "--ip",
        type=str,
        default="",
        help="xArm IP address (required unless --dry-run).",
    )
    parser.add_argument(
        "--enable-motion",
        action="store_true",
        help="Actually enable robot motion and send servo commands (dangerous).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not connect to xArm; print computed poses only (default).",
    )
    parser.add_argument(
        "--vel-limit",
        type=float,
        default=None,
        help="Maximum velocity in m/s (limits position changes for safety).",
    )
    parser.add_argument(
        "--acc-limit",
        type=float,
        default=None,
        help="Maximum acceleration in m/s² (symmetric, applies to deceleration too).",
    )
    parser.add_argument(
        "--ang-limit",
        type=float,
        default=None,
        help="Maximum angular velocity in rad/s (for velocity mode).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["delta-pose", "velocity"],
        default=None,
        help="Control mode: delta-pose (position via deltas), velocity (velocity control). Absolute-pose (absolute positions) is forbidden.",
    )
    args = parser.parse_args()

    dry_run = bool(args.dry_run) or (not args.enable_motion)
    if not dry_run and not args.ip:
        print(
            "error: --ip is required when --enable-motion is set (or run with --dry-run).",
            file=sys.stderr,
        )
        return 2

    # -----------------------------------------------------------------------
    # Televoodoo Setup
    # -----------------------------------------------------------------------

    if not os.path.exists(args.config):
        print(f"error: config file not found: {args.config}", file=sys.stderr)
        return 2

    config = load_config(args.config)
    pose_provider = PoseProvider(config)
    print(f"Using config: {args.config}", flush=True)

    # Determine control mode (required CLI argument)
    VALID_MODES = ["delta-pose", "velocity"]
    
    if args.mode is None:
        print(
            "\n❌ ERROR: No control mode specified!\n"
            "   You must set --mode via CLI.\n"
            "\n"
            "   Available modes:\n"
            "     delta-pose    - Position control via deltas from movement origin\n"
            "     velocity      - Velocity control (vx, vy, vz, wx, wy, wz)\n"
            "\n"
            "   Example: --mode delta-pose\n",
            file=sys.stderr,
        )
        return 2
    
    effective_mode = args.mode
    print(f"Control mode: {effective_mode}", flush=True)

    # Check if motion limits are configured (CLI args override config file)
    effective_vel_limit = args.vel_limit if args.vel_limit is not None else config.vel_limit
    effective_acc_limit = args.acc_limit if args.acc_limit is not None else config.acc_limit

    if effective_vel_limit is None or effective_acc_limit is None:
        missing = []
        if effective_vel_limit is None:
            missing.append("vel_limit")
        if effective_acc_limit is None:
            missing.append("acc_limit")
        print(
            f"\n⚠️  WARNING: No motion limits configured ({', '.join(missing)})!\n"
            f"   This is dangerous for robot teleoperation.\n"
            f"   Set limits via --vel-limit/--acc-limit flags or in config file.\n"
            f"   Recommended: --vel-limit 0.3 --acc-limit 10.0\n",
            file=sys.stderr,
        )

    # -----------------------------------------------------------------------
    # Robot Setup
    # -----------------------------------------------------------------------

    arm = None
    robot_start_pos: tuple[float, float, float] = (0.0, 0.0, 0.0)
    robot_start_q: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    have_origin = False

    if not dry_run:
        if XArmAPI is None:
            print(
                "error: xArm SDK not installed. Run: pip install xarm-python-sdk",
                file=sys.stderr,
            )
            return 2
        arm = XArmAPI(args.ip)
        arm.motion_enable(enable=True)
        if effective_mode == "velocity":
            arm.set_mode(5)  # Cartesian velocity control mode
            print("xArm mode: 5 (Cartesian velocity control)", flush=True)
            
            # Set TCP acceleration and jerk limits on xArm Controller for snappier velocity response
            # Must be set for velocity control mode, otherwise the robot will move with a slow acceleration.
            tcp_maxacc = 50000  # in mm/s² for velocity mode (higher = snappier response)
            tcp_jerk = 100000  # in mm/s³ for velocity mode (higher = snappier response)
            
            arm.set_tcp_maxacc(tcp_maxacc)
            print(f"  TCP max acceleration: {tcp_maxacc} mm/s²", flush=True)
            arm.set_tcp_jerk(tcp_jerk)
            print(f"  TCP jerk: {tcp_jerk} mm/s³", flush=True)

        else:
            # delta-pose uses servo mode
            arm.set_mode(1)  # servo motion mode required for set_servo_cartesian_aa
            print("xArm mode: 1 (servo position control)", flush=True)
        arm.set_state(0)
        time.sleep(0.1)

    def get_robot_pose() -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
        """Get current robot pose as (position, quaternion)."""
        if arm is None:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        try:
            # xArm returns pose as [x, y, z, rx, ry, rz] in axis-angle format
            code, pose_aa = arm.get_position_aa(is_radian=True)
            if code == 0 and pose_aa and len(pose_aa) >= 6:
                pos = (float(pose_aa[0]), float(pose_aa[1]), float(pose_aa[2]))
                # Convert axis-angle to quaternion for proper rotation composition
                q = tvm.rotvec_to_quat((float(pose_aa[3]), float(pose_aa[4]), float(pose_aa[5])))
                return (pos, q)
        except Exception:
            pass
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))

    # -----------------------------------------------------------------------
    # Teleoperation Event Handler (delta-pose mode)
    # -----------------------------------------------------------------------

    def on_teleop_event_delta_pose(evt: Dict[str, Any]) -> None:
        nonlocal have_origin, robot_start_pos, robot_start_q

        # Get transformed delta directly from event
        delta = pose_provider.get_delta(evt)
        if delta is None:
            return

        # On movement_start, reset robot origin pose (for delta-based control)
        if delta.get("movement_start") or not have_origin:
            have_origin = True
            robot_start_pos, robot_start_q = get_robot_pose()
            return

        # Extract position delta (already scaled per config)
        dx = float(delta.get("dx", 0.0))
        dy = float(delta.get("dy", 0.0))
        dz = float(delta.get("dz", 0.0))

        # Extract rotation delta as quaternion
        dq = (
            float(delta.get("dqx", 0.0)),
            float(delta.get("dqy", 0.0)),
            float(delta.get("dqz", 0.0)),
            float(delta.get("dqw", 1.0)),
        )

        # Compute robot target position: robot_start + delta
        x_target = robot_start_pos[0] + dx
        y_target = robot_start_pos[1] + dy
        z_target = robot_start_pos[2] + dz

        # Compute robot target orientation: robot_start_q * dq
        q_target = tvm.quat_multiply(dq, robot_start_q)
        rx_target, ry_target, rz_target = tvm.quat_to_rotvec(q_target)

        # Build robot target pose: [x, y, z, rx, ry, rz]
        pose_target = [x_target, y_target, z_target, rx_target, ry_target, rz_target]

        if dry_run or arm is None:
            print(f"delta-pose target: {pose_target}", flush=True)
            return

        # Send command to robot
        arm.set_servo_cartesian_aa(
            pose_target,
            speed=None,
            is_radian=True,
            is_tool_coord=False,
            relative=False,
        )

   
    # -----------------------------------------------------------------------
    # Teleoperation Event Handler (Velocity Mode)
    # -----------------------------------------------------------------------

    def clamp(value: float, limit: float | None) -> float:
        """Clamp value to [-limit, limit]. If limit is None, return value unchanged."""
        if limit is None:
            return value
        return max(-limit, min(limit, value))

    def on_teleop_event_velocity(evt: Dict[str, Any]) -> None:
        nonlocal have_origin

        # Get velocity from consecutive poses
        velocity = pose_provider.get_velocity(evt)
        if velocity is None:
            return

        # On movement_start, mark that we have origin but send zero velocity
        if velocity.get("movement_start"):
            have_origin = True
            if not dry_run and arm is not None:
                # Stop the robot on movement_start
                arm.vc_set_cartesian_velocity([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            if dry_run:
                print("velocity: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] (movement_start)", flush=True)
            return

        if not have_origin:
            return

        # Extract linear velocity (already scaled per config, e.g., mm/s if scale=1000)
        vx = float(velocity.get("vx", 0.0))
        vy = float(velocity.get("vy", 0.0))
        vz = float(velocity.get("vz", 0.0))

        # Extract angular velocity (rad/s)
        wx = float(velocity.get("wx", 0.0))
        wy = float(velocity.get("wy", 0.0))
        wz = float(velocity.get("wz", 0.0))

        # Apply velocity limits if configured
        # --vel-limit is in m/s, scale it to match the scaled velocity units
        scaled_vel_limit = effective_vel_limit * config.scale if effective_vel_limit is not None else None
        ang_limit = args.ang_limit  # Already in rad/s, no scaling needed

        vx = clamp(vx, scaled_vel_limit)
        vy = clamp(vy, scaled_vel_limit)
        vz = clamp(vz, scaled_vel_limit)
        wx = clamp(wx, ang_limit)
        wy = clamp(wy, ang_limit)
        wz = clamp(wz, ang_limit)

        # Build velocity command: [vx, vy, vz, wx, wy, wz]
        velocity_cmd = [vx, vy, vz, wx, wy, wz]

        if dry_run or arm is None:
            dt = velocity.get("dt", 0.0)
            print(f"velocity: {velocity_cmd} (dt={dt:.4f}s)", flush=True)
            return

        # Send velocity command to robot using vc_set_cartesian_velocity
        # This is the continuous velocity control API for mode 5
        # duration=0.1 means it's keeping the velocity constant for 0.1 seconds if no new command is sent.
        arm.vc_set_cartesian_velocity(velocity_cmd, is_radian=True, is_tool_coord=False, duration=0.1)

    # Select the appropriate event handler based on mode
    if effective_mode == "delta-pose":
        on_teleop_event = on_teleop_event_delta_pose
    elif effective_mode == "velocity":
        on_teleop_event = on_teleop_event_velocity
    else:
        # Should not reach here due to earlier validation
        raise ValueError(f"Unknown mode: {effective_mode}")

    # -----------------------------------------------------------------------
    # Start Televoodoo (blocks until connection closes)
    # -----------------------------------------------------------------------

    start_televoodoo(
        callback=on_teleop_event,
        quiet=True,
        name=config.auth_name,
        code=config.auth_code,
        config=config,  # Pass config for vel_limit, acc_limit from config file
        vel_limit=args.vel_limit,  # CLI args override config file
        acc_limit=args.acc_limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

