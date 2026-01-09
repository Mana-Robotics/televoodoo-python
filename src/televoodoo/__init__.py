"""Televoodoo - Real-time 6DoF pose streaming from smartphone to Python.

Main exports:
- start_televoodoo: Start the connection and receive pose data
- PoseProvider: Get transformed poses from teleoperation events
- Pose: Pose data structure
- load_config: Load configuration from JSON file
"""

from .pose import Pose
from .config import OutputConfig, load_config
from .pose_provider import PoseProvider
from .connection import start_televoodoo
from .session import generate_credentials, print_session_qr
from . import math

__all__ = [
    # Main API
    "start_televoodoo",
    "PoseProvider",
    "Pose",
    "OutputConfig",
    "load_config",
    # Session utilities
    "generate_credentials",
    "print_session_qr",
    # Math utilities
    "math",
]
