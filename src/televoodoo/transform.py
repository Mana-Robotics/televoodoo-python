"""Pose transformation logic for Televoodoo."""

from __future__ import annotations
from typing import Dict, Any, Tuple
import math

from .pose import Pose
from .config import OutputConfig


class PoseTransformer:
    """Transforms raw pose data according to an OutputConfig."""

    def __init__(self, config: OutputConfig) -> None:
        self.config = config
        self._origin: Pose | None = None

    @staticmethod
    def _quat_multiply(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return (
            aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz,
        )

    @staticmethod
    def _quat_conjugate(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x, y, z, w = q
        return (-x, -y, -z, w)

    @staticmethod
    def _rotate_vector_by_quat(v: Tuple[float, float, float], q: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
        # v' = q * (v,0) * q_conj
        vx, vy, vz = v
        x, y, z, w = q
        # compute cross products efficiently
        # t = 2 * cross(q.xyz, v)
        tx = 2 * (y*vz - z*vy)
        ty = 2 * (z*vx - x*vz)
        tz = 2 * (x*vy - y*vx)
        # v' = v + w*t + cross(q.xyz, t)
        vpx = vx + w*tx + (y*tz - z*ty)
        vpy = vy + w*ty + (z*tx - x*tz)
        vpz = vz + w*tz + (x*ty - y*tx)
        return (vpx, vpy, vpz)

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

    def transform(self, pose: Pose) -> Dict[str, Any]:
        if self._origin is None and pose.movement_start:
            self._origin = pose

        absolute_input = {
            "movement_start": pose.movement_start,
            "x": pose.x,
            "y": pose.y,
            "z": pose.z,
            "qx": pose.qx,
            "qy": pose.qy,
            "qz": pose.qz,
            "qw": pose.qw,
        }

        if self.config.includeOrientation.get("euler_radian") or self.config.includeOrientation.get("euler_degree"):
            absolute_input.update({
                "x_rot": pose.x_rot,
                "y_rot": pose.y_rot,
                "z_rot": pose.z_rot,
            })

        delta_input = None
        if self._origin is not None:
            delta_input = {
                "dx": pose.x - self._origin.x,
                "dy": pose.y - self._origin.y,
                "dz": pose.z - self._origin.z,
            }

        # Transform pose from reference/world to target coordinates if targetFrame provided
        tx, ty, tz = 0.0, 0.0, 0.0
        # target orientation in radians (XYZ)
        txr, tyr, tzr = 0.0, 0.0, 0.0
        if self.config.targetFrame:
            tx = float(self.config.targetFrame.get("x", 0.0))
            ty = float(self.config.targetFrame.get("y", 0.0))
            tz = float(self.config.targetFrame.get("z", 0.0))
            txr = float(self.config.targetFrame.get("x_rot", 0.0))
            tyr = float(self.config.targetFrame.get("y_rot", 0.0))
            tzr = float(self.config.targetFrame.get("z_rot", 0.0))

        # build quaternion from Euler XYZ radians
        cx, sx = math.cos(txr/2.0), math.sin(txr/2.0)
        cy, sy = math.cos(tyr/2.0), math.sin(tyr/2.0)
        cz, sz = math.cos(tzr/2.0), math.sin(tzr/2.0)
        # XYZ intrinsic
        tqw = cx*cy*cz - sx*sy*sz
        tqx = sx*cy*cz + cx*sy*sz
        tqy = cx*sy*cz - sx*cy*sz
        tqz = cx*cy*sz + sx*sy*cz

        # position in target: R_T^T * (p_ref - t)
        px, py, pz = pose.x - tx, pose.y - ty, pose.z - tz
        invT = (-tqx, -tqy, -tqz, tqw)
        tposx, tposy, tposz = self._rotate_vector_by_quat((px, py, pz), invT)
        # orientation in target: qT^{-1} * q_ref
        qrel = self._quat_multiply(invT, (pose.qx, pose.qy, pose.qz, pose.qw))

        absolute_transformed = {
            "x": self._apply_scale(tposx * self.config.outputAxes.get("x", 1)),
            "y": self._apply_scale(tposy * self.config.outputAxes.get("y", 1)),
            "z": self._apply_scale(tposz * self.config.outputAxes.get("z", 1)),
            "qx": qrel[0],
            "qy": qrel[1],
            "qz": qrel[2],
            "qw": qrel[3],
        }
        if self.config.includeOrientation.get("euler_radian"):
            xr, yr, zr = self._quat_to_euler_xyz(qrel)
            absolute_transformed.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
        if self.config.includeOrientation.get("euler_degree"):
            xr, yr, zr = self._quat_to_euler_xyz(qrel)
            absolute_transformed.update({
                "x_rot_deg": (xr * 180.0 / math.pi),
                "y_rot_deg": (yr * 180.0 / math.pi),
                "z_rot_deg": (zr * 180.0 / math.pi),
            })

        delta_transformed = None
        if self._origin is not None:
            dx = pose.x - self._origin.x
            dy = pose.y - self._origin.y
            dz = pose.z - self._origin.z
            # rotate delta by inv target rotation, then scale/axes
            ddx, ddy, ddz = self._rotate_vector_by_quat((dx, dy, dz), invT)
            delta_transformed = {
                "dx": self._apply_scale(ddx * self.config.outputAxes.get("x", 1)),
                "dy": self._apply_scale(ddy * self.config.outputAxes.get("y", 1)),
                "dz": self._apply_scale(ddz * self.config.outputAxes.get("z", 1)),
            }
            # include current orientation in delta outputs per UI expectation
            delta_transformed.update({"qx": qrel[0], "qy": qrel[1], "qz": qrel[2], "qw": qrel[3]})
            if self.config.includeOrientation.get("euler_radian"):
                xr, yr, zr = self._quat_to_euler_xyz(qrel)
                delta_transformed.update({"x_rot": xr, "y_rot": yr, "z_rot": zr})
            if self.config.includeOrientation.get("euler_degree"):
                xr, yr, zr = self._quat_to_euler_xyz(qrel)
                delta_transformed.update({
                    "x_rot_deg": (xr * 180.0 / math.pi),
                    "y_rot_deg": (yr * 180.0 / math.pi),
                    "z_rot_deg": (zr * 180.0 / math.pi),
                })

        result: Dict[str, Any] = {}
        if self.config.includeFormats.get("absolute_input"):
            result["absolute_input"] = absolute_input
        if self.config.includeFormats.get("delta_input") and delta_input is not None:
            result["delta_input"] = delta_input
        if self.config.includeFormats.get("absolute_transformed"):
            result["absolute_transformed"] = absolute_transformed
        if self.config.includeFormats.get("delta_transformed") and delta_transformed is not None:
            result["delta_transformed"] = delta_transformed
        return result
