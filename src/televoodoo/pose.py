from dataclasses import dataclass


@dataclass
class Pose:
    pose_start: bool
    x: float
    y: float
    z: float
    x_rot: float
    y_rot: float
    z_rot: float
    qx: float
    qy: float
    qz: float
    qw: float


