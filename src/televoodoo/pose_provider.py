"""Pose provider for Televoodoo.

Provides transformed pose data from teleoperation events.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import math
import time

from .pose import Pose
from .config import OutputConfig
from . import math as tvm


@dataclass
class _TimestampedPose:
    """Pose with timestamp for velocity calculations."""
    pose: Pose
    timestamp: float  # monotonic time


class PoseProvider:
    """Provides transformed pose data from teleoperation events.

    Handles internally:
    - Coordinate frame transformations (via targetFrame config)
    - Axis flipping and scaling
    - Position and rotation delta calculations from movement origin
    - Output format selection

    Primary usage:
        provider = PoseProvider(config)
        
        # For robot teleoperation (recommended):
        delta = provider.get_delta(event)
        
        # For absolute poses (e.g., digital twin):
        pose = provider.get_absolute(event)
    """

    def __init__(self, config: OutputConfig) -> None:
        self.config = config
        self._origin: Pose | None = None
        # State for velocity calculations
        self._prev_timestamped_pose: Optional[_TimestampedPose] = None

    def reset_origin(self) -> None:
        """Clear the stored origin pose and velocity state."""
        self._origin = None
        self._prev_timestamped_pose = None

    def get_absolute(self, evt: Dict[str, Any]) -> Dict[str, Any] | None:
        """Get transformed absolute pose from a teleoperation event.

        Returns the pose transformed to the target frame with scaling and
        axis adjustments applied.

        The returned pose contains:
        - movement_start: True if this is a new movement origin
        - x, y, z: Absolute position (scaled per config)
        - qx, qy, qz, qw: Orientation as quaternion
        - rx, ry, rz: Orientation as rotation vector (radians)
        - x_rot, y_rot, z_rot: Euler angles (radians)
        - x_rot_deg, y_rot_deg, z_rot_deg: Euler angles (degrees)

        Args:
            evt: Event dictionary from Televoodoo callback.

        Returns:
            Pose dictionary with transformed absolute values, or None if
            the event is not a pose event.
        """
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return None

        # Reset origin on movement_start (for delta tracking consistency)
        if pose.movement_start:
            self._origin = pose

        # Build target frame transform
        (tx, ty, tz), target_q = self._build_target_frame_quat()
        invT = (-target_q[0], -target_q[1], -target_q[2], target_q[3])

        # Position in target: R_T^T * (p_ref - t)
        px, py, pz = pose.x - tx, pose.y - ty, pose.z - tz
        tposx, tposy, tposz = self._rotate_vector_by_quat((px, py, pz), invT)

        # Orientation in target: qT^{-1} * q_ref
        qrel = self._quat_multiply(invT, (pose.qx, pose.qy, pose.qz, pose.qw))

        # Apply output axes and scale
        result: Dict[str, Any] = {
            "movement_start": pose.movement_start,
            "x": self._apply_scale(tposx * self.config.outputAxes.get("x", 1)),
            "y": self._apply_scale(tposy * self.config.outputAxes.get("y", 1)),
            "z": self._apply_scale(tposz * self.config.outputAxes.get("z", 1)),
            "qx": qrel[0],
            "qy": qrel[1],
            "qz": qrel[2],
            "qw": qrel[3],
        }

        # Add rotation vector (axis-angle) representation
        rx, ry, rz = tvm.quat_to_rotvec(qrel)
        result.update({"rx": rx, "ry": ry, "rz": rz})

        # Add Euler angles (radians and degrees)
        xr, yr, zr = self._quat_to_euler_xyz(qrel)
        result.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
        result.update({
            "x_rot_deg": (xr * 180.0 / math.pi),
            "y_rot_deg": (yr * 180.0 / math.pi),
            "z_rot_deg": (zr * 180.0 / math.pi),
        })

        return result

    def get_delta(self, evt: Dict[str, Any]) -> Dict[str, Any] | None:
        """Get transformed delta directly from a teleoperation event.

        The returned delta contains:
        - movement_start: True if this is a new movement origin
        - dx, dy, dz: Position delta (scaled per config)
        - dqx, dqy, dqz, dqw: Rotation delta as quaternion
        - rx, ry, rz: Rotation delta as rotation vector (radians)
        - x_rot, y_rot, z_rot: Rotation delta as Euler angles (radians)
        - x_rot_deg, y_rot_deg, z_rot_deg: Rotation delta as Euler angles (degrees)
        - qx, qy, qz, qw: Current absolute orientation as quaternion

        Args:
            evt: Event dictionary from Televoodoo callback.

        Returns:
            Delta dictionary with position/rotation deltas, or None if:
            - Event is not a pose event
            - No origin has been set yet (waiting for first movement_start)
        """
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return None

        # Reset origin on movement_start
        if pose.movement_start:
            self._origin = pose

        # No origin yet - can't compute delta
        if self._origin is None:
            return None

        # Build target frame transform
        (tx, ty, tz), target_q = self._build_target_frame_quat()
        invT = (-target_q[0], -target_q[1], -target_q[2], target_q[3])

        # Position delta in target frame
        dx = pose.x - self._origin.x
        dy = pose.y - self._origin.y
        dz = pose.z - self._origin.z
        ddx, ddy, ddz = self._rotate_vector_by_quat((dx, dy, dz), invT)

        delta: Dict[str, Any] = {
            "movement_start": pose.movement_start,
            "dx": self._apply_scale(ddx * self.config.outputAxes.get("x", 1)),
            "dy": self._apply_scale(ddy * self.config.outputAxes.get("y", 1)),
            "dz": self._apply_scale(ddz * self.config.outputAxes.get("z", 1)),
        }

        # Rotation delta in target frame
        origin_q = (self._origin.qx, self._origin.qy, self._origin.qz, self._origin.qw)
        current_q = (pose.qx, pose.qy, pose.qz, pose.qw)
        origin_q_target = self._quat_multiply(invT, origin_q)
        current_q_target = self._quat_multiply(invT, current_q)

        # Compute delta quaternion (base frame: q_delta = q_current * inv(q_origin))
        q_delta = tvm.quat_delta(origin_q_target, current_q_target, frame="base")
        delta.update({
            "dqx": q_delta[0],
            "dqy": q_delta[1],
            "dqz": q_delta[2],
            "dqw": q_delta[3],
        })

        # Rotation delta as rotation vector (axis-angle, radians)
        drx, dry, drz = tvm.quat_to_rotvec(q_delta)
        delta.update({"rx": drx, "ry": dry, "rz": drz})

        # Rotation delta as Euler angles (radians and degrees)
        xr, yr, zr = self._quat_to_euler_xyz(q_delta)
        delta.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
        delta.update({
            "x_rot_deg": (xr * 180.0 / math.pi),
            "y_rot_deg": (yr * 180.0 / math.pi),
            "z_rot_deg": (zr * 180.0 / math.pi),
        })

        # Include current absolute orientation for convenience
        delta.update({
            "qx": current_q_target[0],
            "qy": current_q_target[1],
            "qz": current_q_target[2],
            "qw": current_q_target[3],
        })

        return delta

    def get_velocity(self, evt: Dict[str, Any], min_dt: float = 0.001) -> Dict[str, Any] | None:
        """Get velocity (linear and angular) from consecutive pose events.

        This method computes instantaneous velocities by comparing the current
        pose with the previous pose and dividing by the elapsed time. Useful
        for velocity-based robot control (e.g., xArm set_cartesian_velo_continuous).

        The returned velocity contains:
        - vx, vy, vz: Linear velocity in units/s (scaled per config, e.g., mm/s if scale=1000)
        - wx, wy, wz: Angular velocity in rad/s (rotation vector derivative)
        - dt: Time delta since last pose (seconds)
        - movement_start: True if this is a new movement origin (velocities will be zero)

        Note: On movement_start, velocities are returned as zero since there is no
        previous pose to compute velocity from. The first pose after movement_start
        will have valid velocities.

        Args:
            evt: Event dictionary from Televoodoo callback.
            min_dt: Minimum time delta in seconds. If dt < min_dt, None is returned
                to avoid division by very small numbers. Default: 0.001 (1ms).

        Returns:
            Velocity dictionary with linear/angular velocities, or None if:
            - Event is not a pose event
            - Time delta is too small (< min_dt)
        """
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return None

        now = time.monotonic()

        # Reset state on movement_start
        if pose.movement_start:
            self._origin = pose
            self._prev_timestamped_pose = _TimestampedPose(pose=pose, timestamp=now)
            # Return zero velocities on movement_start
            return {
                "movement_start": True,
                "vx": 0.0,
                "vy": 0.0,
                "vz": 0.0,
                "wx": 0.0,
                "wy": 0.0,
                "wz": 0.0,
                "dt": 0.0,
            }

        # No previous pose yet - can't compute velocity
        if self._prev_timestamped_pose is None:
            self._prev_timestamped_pose = _TimestampedPose(pose=pose, timestamp=now)
            return None

        # Calculate time delta
        dt = now - self._prev_timestamped_pose.timestamp
        if dt < min_dt:
            # Time delta too small - skip to avoid numerical issues
            return None

        prev_pose = self._prev_timestamped_pose.pose

        # Build target frame transform
        (tx, ty, tz), target_q = self._build_target_frame_quat()
        invT = (-target_q[0], -target_q[1], -target_q[2], target_q[3])

        # Position delta in target frame
        dx = pose.x - prev_pose.x
        dy = pose.y - prev_pose.y
        dz = pose.z - prev_pose.z
        ddx, ddy, ddz = self._rotate_vector_by_quat((dx, dy, dz), invT)

        # Apply output axes and scale to position delta, then compute velocity
        vx = self._apply_scale(ddx * self.config.outputAxes.get("x", 1)) / dt
        vy = self._apply_scale(ddy * self.config.outputAxes.get("y", 1)) / dt
        vz = self._apply_scale(ddz * self.config.outputAxes.get("z", 1)) / dt

        # Rotation delta in target frame (for angular velocity)
        prev_q = (prev_pose.qx, prev_pose.qy, prev_pose.qz, prev_pose.qw)
        current_q = (pose.qx, pose.qy, pose.qz, pose.qw)
        prev_q_target = self._quat_multiply(invT, prev_q)
        current_q_target = self._quat_multiply(invT, current_q)

        # Compute delta quaternion (base frame: q_delta = q_current * inv(q_prev))
        q_delta = tvm.quat_delta(prev_q_target, current_q_target, frame="base")

        # Convert delta quaternion to rotation vector (axis-angle)
        drx, dry, drz = tvm.quat_to_rotvec(q_delta)

        # Angular velocity = rotation vector / dt (rad/s)
        wx = drx / dt
        wy = dry / dt
        wz = drz / dt

        # Update state for next call
        self._prev_timestamped_pose = _TimestampedPose(pose=pose, timestamp=now)

        return {
            "movement_start": False,
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "wx": wx,
            "wy": wy,
            "wz": wz,
            "dt": dt,
        }

    @staticmethod
    def _quat_multiply(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        return tvm.quat_multiply(a, b)

    @staticmethod
    def _quat_conjugate(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        return tvm.quat_conjugate(q)

    @staticmethod
    def _rotate_vector_by_quat(v: Tuple[float, float, float], q: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
        return tvm.rotate_vector(v, q)

    @staticmethod
    def _quat_to_euler_xyz(q: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
        # Convert quaternion to Euler angles (XYZ, radians)
        x, y, z, w = q
        # roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        # pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)
        # yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return (roll, pitch, yaw)

    def _apply_scale(self, value: float) -> float:
        return value * float(self.config.scale)

    def _build_target_frame_quat(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]:
        """Build target frame translation and quaternion from config."""
        tx, ty, tz = 0.0, 0.0, 0.0
        txr, tyr, tzr = 0.0, 0.0, 0.0

        if self.config.targetFrame:
            tx = float(self.config.targetFrame.get("x", 0.0))
            ty = float(self.config.targetFrame.get("y", 0.0))
            tz = float(self.config.targetFrame.get("z", 0.0))
            txr = float(self.config.targetFrame.get("x_rot", 0.0))
            tyr = float(self.config.targetFrame.get("y_rot", 0.0))
            tzr = float(self.config.targetFrame.get("z_rot", 0.0))

        # Build quaternion from Euler XYZ radians
        cx, sx = math.cos(txr / 2.0), math.sin(txr / 2.0)
        cy, sy = math.cos(tyr / 2.0), math.sin(tyr / 2.0)
        cz, sz = math.cos(tzr / 2.0), math.sin(tzr / 2.0)
        # XYZ intrinsic
        tqw = cx * cy * cz - sx * sy * sz
        tqx = sx * cy * cz + cx * sy * sz
        tqy = cx * sy * cz - sx * cy * sz
        tqz = cx * cy * sz + sx * sy * cz

        return (tx, ty, tz), (tqx, tqy, tqz, tqw)

    def transform(self, pose: Pose) -> Dict[str, Any]:
        """Transform a pose and return data for CLI log output.

        This method is used internally by `python -m televoodoo` to produce
        JSON output. For programmatic use, prefer get_delta(), get_absolute(),
        or get_velocity() instead.

        Args:
            pose: Input pose from the phone/tracker.

        Returns:
            Dictionary with data enabled in config.logData:
            - absolute_input: Raw pose data
            - delta_input: Position delta from origin (raw frame)
            - absolute_transformed: Pose in target frame
            - delta_transformed: Position and rotation deltas in target frame
            - velocity: Linear and angular velocities
        """
        # Reset origin on movement_start
        if pose.movement_start:
            self._origin = pose

        absolute_input: Dict[str, Any] = {
            "movement_start": pose.movement_start,
            "x": pose.x,
            "y": pose.y,
            "z": pose.z,
        }

        # Add quaternion if configured (default True)
        if self.config.logDataFormat.get("quaternion", True):
            absolute_input.update({
                "qx": pose.qx,
                "qy": pose.qy,
                "qz": pose.qz,
                "qw": pose.qw,
            })

        # Add rotation vector
        rx, ry, rz = tvm.quat_to_rotvec((pose.qx, pose.qy, pose.qz, pose.qw))
        if self.config.logDataFormat.get("rotation_vector"):
            absolute_input.update({"rx": rx, "ry": ry, "rz": rz})

        # Compute Euler angles from quaternion if requested
        if self.config.logDataFormat.get("euler_radian"):
            xr, yr, zr = self._quat_to_euler_xyz((pose.qx, pose.qy, pose.qz, pose.qw))
            absolute_input.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
        if self.config.logDataFormat.get("euler_degree"):
            xr, yr, zr = self._quat_to_euler_xyz((pose.qx, pose.qy, pose.qz, pose.qw))
            absolute_input.update({
                "x_rot_deg": (xr * 180.0 / math.pi),
                "y_rot_deg": (yr * 180.0 / math.pi),
                "z_rot_deg": (zr * 180.0 / math.pi),
            })

        delta_input = None
        if self._origin is not None:
            delta_input = {
                "dx": pose.x - self._origin.x,
                "dy": pose.y - self._origin.y,
                "dz": pose.z - self._origin.z,
            }

        # Build target frame transform
        (tx, ty, tz), target_q = self._build_target_frame_quat()
        invT = (-target_q[0], -target_q[1], -target_q[2], target_q[3])

        # Position in target: R_T^T * (p_ref - t)
        px, py, pz = pose.x - tx, pose.y - ty, pose.z - tz
        tposx, tposy, tposz = self._rotate_vector_by_quat((px, py, pz), invT)

        # Orientation in target: qT^{-1} * q_ref
        qrel = self._quat_multiply(invT, (pose.qx, pose.qy, pose.qz, pose.qw))

        # Apply output axes and scale
        absolute_transformed: Dict[str, Any] = {
            "movement_start": pose.movement_start,
            "x": self._apply_scale(tposx * self.config.outputAxes.get("x", 1)),
            "y": self._apply_scale(tposy * self.config.outputAxes.get("y", 1)),
            "z": self._apply_scale(tposz * self.config.outputAxes.get("z", 1)),
        }

        # Add quaternion if configured (default True)
        if self.config.logDataFormat.get("quaternion", True):
            absolute_transformed.update({
                "qx": qrel[0],
                "qy": qrel[1],
                "qz": qrel[2],
                "qw": qrel[3],
            })

        # Add rotation vector (axis-angle) representation
        rx, ry, rz = tvm.quat_to_rotvec(qrel)
        if self.config.logDataFormat.get("rotation_vector"):
            absolute_transformed.update({"rx": rx, "ry": ry, "rz": rz})

        if self.config.logDataFormat.get("euler_radian"):
            xr, yr, zr = self._quat_to_euler_xyz(qrel)
            absolute_transformed.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
        if self.config.logDataFormat.get("euler_degree"):
            xr, yr, zr = self._quat_to_euler_xyz(qrel)
            absolute_transformed.update({
                "x_rot_deg": (xr * 180.0 / math.pi),
                "y_rot_deg": (yr * 180.0 / math.pi),
                "z_rot_deg": (zr * 180.0 / math.pi),
            })

        delta_transformed = None
        if self._origin is not None:
            # Position delta
            dx = pose.x - self._origin.x
            dy = pose.y - self._origin.y
            dz = pose.z - self._origin.z
            # Rotate delta by inv target rotation, then scale/axes
            ddx, ddy, ddz = self._rotate_vector_by_quat((dx, dy, dz), invT)

            delta_transformed = {
                "dx": self._apply_scale(ddx * self.config.outputAxes.get("x", 1)),
                "dy": self._apply_scale(ddy * self.config.outputAxes.get("y", 1)),
                "dz": self._apply_scale(ddz * self.config.outputAxes.get("z", 1)),
            }

            # Rotation delta: q_current * inv(q_origin) in transformed frame
            origin_q = (self._origin.qx, self._origin.qy, self._origin.qz, self._origin.qw)
            # Transform both to target frame first
            origin_q_target = self._quat_multiply(invT, origin_q)
            current_q_target = qrel  # already transformed

            # Compute delta quaternion (base frame convention: q_delta = q_current * inv(q_origin))
            q_delta = tvm.quat_delta(origin_q_target, current_q_target, frame="base")

            # Add delta quaternion if configured (default True)
            if self.config.logDataFormat.get("quaternion", True):
                delta_transformed.update({
                    "dqx": q_delta[0],
                    "dqy": q_delta[1],
                    "dqz": q_delta[2],
                    "dqw": q_delta[3],
                })

            # Rotation delta as rotation vector (axis-angle, radians)
            drx, dry, drz = tvm.quat_to_rotvec(q_delta)
            if self.config.logDataFormat.get("rotation_vector"):
                delta_transformed.update({"rx": drx, "ry": dry, "rz": drz})

            # Current absolute orientation (for convenience)
            if self.config.logDataFormat.get("quaternion", True):
                delta_transformed.update({"qx": qrel[0], "qy": qrel[1], "qz": qrel[2], "qw": qrel[3]})

            if self.config.logDataFormat.get("euler_radian"):
                xr, yr, zr = self._quat_to_euler_xyz(qrel)
                delta_transformed.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
            if self.config.logDataFormat.get("euler_degree"):
                xr, yr, zr = self._quat_to_euler_xyz(qrel)
                delta_transformed.update({
                    "x_rot_deg": (xr * 180.0 / math.pi),
                    "y_rot_deg": (yr * 180.0 / math.pi),
                    "z_rot_deg": (zr * 180.0 / math.pi),
                })

        result: Dict[str, Any] = {}
        if self.config.logData.get("absolute_input"):
            result["absolute_input"] = absolute_input
        if self.config.logData.get("delta_input") and delta_input is not None:
            result["delta_input"] = delta_input
        if self.config.logData.get("absolute_transformed"):
            result["absolute_transformed"] = absolute_transformed
        if self.config.logData.get("delta_transformed") and delta_transformed is not None:
            result["delta_transformed"] = delta_transformed
        if self.config.logData.get("velocity"):
            # Build a synthetic event dict for get_velocity (must match teleop event format)
            evt = {
                "type": "pose",
                "data": {
                    "absolute_input": {
                        "movement_start": pose.movement_start,
                        "x": pose.x, "y": pose.y, "z": pose.z,
                        "qx": pose.qx, "qy": pose.qy, "qz": pose.qz, "qw": pose.qw,
                    }
                }
            }
            velocity = self.get_velocity(evt)
            if velocity is not None:
                result["velocity"] = velocity
        return result
