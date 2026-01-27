"""Televoodoo - Real-time 6DoF pose streaming from smartphone to Python.

Main exports:
- start_televoodoo: Start the connection and receive pose data
- send_haptic: Send haptic feedback to the phone app
- send_config: Send configuration updates to the phone app
- PoseProvider: Get transformed poses from teleoperation events
- Pose: Pose data structure
- load_config: Load configuration from JSON file
- protocol: Binary protocol parsing/packing
"""

from .pose import Pose
from .config import OutputConfig, load_config
from .pose_provider import PoseProvider
from .resampler import PoseResampler
from .motion_limiter import MotionLimiter
from .connection import start_televoodoo
from .session import generate_credentials, print_session_qr
from .tcp_service import send_haptic, send_config
from . import math
from . import protocol

__all__ = [
    # Main API
    "start_televoodoo",
    "send_haptic",
    "send_config",
    "PoseProvider",
    "PoseResampler",
    "MotionLimiter",
    "Pose",
    "OutputConfig",
    "load_config",
    # Session utilities
    "generate_credentials",
    "print_session_qr",
    # Math utilities
    "math",
    # Protocol (binary)
    "protocol",
]
