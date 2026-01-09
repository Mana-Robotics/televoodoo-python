"""Quaternion and rotation math utilities for Televoodoo.

All quaternions use (x, y, z, w) convention (scalar-last).
Rotation vectors are axis-angle format: (rx, ry, rz) where magnitude = angle in radians.
"""

from __future__ import annotations
import math
from typing import Tuple

Quat = Tuple[float, float, float, float]
Vec3 = Tuple[float, float, float]


def quat_normalize(q: Quat) -> Quat:
    """Normalize a quaternion to unit length."""
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n <= 0.0:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / n, y / n, z / n, w / n)


def quat_conjugate(q: Quat) -> Quat:
    """Return the conjugate (inverse for unit quaternions)."""
    x, y, z, w = q
    return (-x, -y, -z, w)


def quat_multiply(a: Quat, b: Quat) -> Quat:
    """Multiply two quaternions: result = a * b."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_to_rotvec(q: Quat) -> Vec3:
    """Convert a unit quaternion to axis-angle rotation vector (rx, ry, rz) in radians.

    The rotation vector magnitude equals the rotation angle.
    """
    x, y, z, w = quat_normalize(q)
    # Prefer the shortest rotation (q and -q represent the same rotation)
    if w < 0.0:
        x, y, z, w = -x, -y, -z, -w

    # Clamp w to avoid numerical issues with acos
    w = max(-1.0, min(1.0, w))
    angle = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))  # == |sin(angle/2)|

    if s < 1e-8 or angle < 1e-8:
        return (0.0, 0.0, 0.0)

    ax, ay, az = (x / s, y / s, z / s)
    return (ax * angle, ay * angle, az * angle)


def rotvec_to_quat(r: Vec3) -> Quat:
    """Convert axis-angle rotation vector (rx, ry, rz) in radians to quaternion."""
    rx, ry, rz = r
    angle = math.sqrt(rx * rx + ry * ry + rz * rz)
    if angle < 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    ax, ay, az = (rx / angle, ry / angle, rz / angle)
    s = math.sin(angle / 2.0)
    c = math.cos(angle / 2.0)
    return (ax * s, ay * s, az * s, c)


def quat_delta(q_from: Quat, q_to: Quat, frame: str = "base") -> Quat:
    """Compute the relative rotation quaternion from q_from to q_to.

    Args:
        q_from: Starting orientation quaternion
        q_to: Target orientation quaternion
        frame: 'base' for world/base frame delta (q_to * inv(q_from)),
               'tool' for tool/body frame delta (inv(q_from) * q_to)

    Returns:
        Delta quaternion representing the rotation from q_from to q_to.
    """
    q_from_inv = quat_conjugate(q_from)
    if frame == "tool":
        return quat_multiply(q_from_inv, q_to)
    else:  # base frame (default)
        return quat_multiply(q_to, q_from_inv)


def rotate_vector(v: Vec3, q: Quat) -> Vec3:
    """Rotate a 3D vector by a quaternion: v' = q * v * q_conj."""
    vx, vy, vz = v
    x, y, z, w = q
    # Efficient rotation using cross products
    # t = 2 * cross(q.xyz, v)
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    # v' = v + w*t + cross(q.xyz, t)
    vpx = vx + w * tx + (y * tz - z * ty)
    vpy = vy + w * ty + (z * tx - x * tz)
    vpz = vz + w * tz + (x * ty - y * tx)
    return (vpx, vpy, vpz)

