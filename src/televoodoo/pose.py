"""Pose data structure for Televoodoo."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class Pose:
    """6DoF pose with position and orientation.

    The binary protocol sends: movement_start, x, y, z, qx, qy, qz, qw.
    Euler angles are NOT in the protocol — use PoseProvider to compute them.

    Attributes:
        movement_start: True when this pose marks the start of a new movement
                       (origin for delta calculations should be reset).
        x, y, z: Position in meters.
        qx, qy, qz, qw: Quaternion orientation (scalar-last convention).
    """

    movement_start: bool
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Pose":
        """Create a Pose from a dictionary (e.g., from protocol event data).

        Missing fields default to 0.0, except qw which defaults to 1.0 (identity).
        """
        return cls(
            movement_start=bool(d.get("movement_start", False)),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            z=float(d.get("z", 0.0)),
            qx=float(d.get("qx", 0.0)),
            qy=float(d.get("qy", 0.0)),
            qz=float(d.get("qz", 0.0)),
            qw=float(d.get("qw", 1.0)),
        )

    @classmethod
    def from_teleop_event(cls, evt: Dict[str, Any]) -> Optional["Pose"]:
        """Create a Pose from a Televoodoo teleoperation event dictionary.

        Returns None if the event is not a pose event.

        Args:
            evt: Event dictionary from Televoodoo callback, expected format:
                 {"type": "pose", "data": {"absolute_input": {...}}}

        Returns:
            Pose object or None if not a pose event.
        """
        if evt.get("type") != "pose":
            return None
        ai = evt.get("data", {}).get("absolute_input", {})
        if not ai:
            return None
        try:
            return cls.from_dict(ai)
        except Exception:
            return None

    @property
    def position(self) -> Tuple[float, float, float]:
        """Position as (x, y, z) tuple."""
        return (self.x, self.y, self.z)

    @property
    def quaternion(self) -> Tuple[float, float, float, float]:
        """Orientation as (qx, qy, qz, qw) quaternion tuple (scalar-last)."""
        return (self.qx, self.qy, self.qz, self.qw)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "movement_start": self.movement_start,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "qx": self.qx,
            "qy": self.qy,
            "qz": self.qz,
            "qw": self.qw,
        }
