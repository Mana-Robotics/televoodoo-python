"""Configuration loading and data structures for Televoodoo."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
import json
import math


@dataclass
class OutputConfig:
    """Configuration for pose transformation and output formatting.
    
    Attributes:
        logData: Which data to include in CLI log output (absolute_input, delta_input, velocity, etc.)
            Only affects `python -m televoodoo` JSON output; has no effect on PoseProvider methods
            like get_delta(), get_absolute(), or get_velocity().
        logDataFormat: Which orientation formats to include in CLI log output (quaternion, rotation_vector, euler_radian, euler_degree).
            Only affects `python -m televoodoo` JSON output; PoseProvider methods always include all formats.
        scale: Scale factor applied to position values
        outputAxes: Axis multipliers for output (can flip axes with -1)
        targetFrame: Pose of target coordinate system relative to reference/world (Euler radians)
        auth_name: Optional static peripheral name (overrides random generation)
        auth_code: Optional static authentication code (overrides random generation)
        upsample_to_frequency_hz: Target frequency for upsampling via linear extrapolation
        rate_limit_frequency_hz: Maximum output frequency (drops excess poses)
        vel_limit: Maximum velocity in m/s (position limiting for safety)
        acc_limit: Maximum acceleration in m/s² (symmetric, applies to deceleration too)
    """
    logData: Dict[str, bool]
    logDataFormat: Dict[str, bool]
    scale: float
    outputAxes: Dict[str, float]
    # Pose of Target Coordinate System relative to reference/world (Euler radians)
    targetFrame: Optional[Dict[str, float]] = None
    # Authentication credentials (optional, can be set in config file)
    auth_name: Optional[str] = None
    auth_code: Optional[str] = None
    # Resampling settings
    upsample_to_frequency_hz: Optional[float] = None
    rate_limit_frequency_hz: Optional[float] = None
    # Motion limiting settings
    vel_limit: Optional[float] = None  # Maximum velocity in m/s
    acc_limit: Optional[float] = None  # Maximum acceleration in m/s²


def load_config(path: Optional[str] = None) -> OutputConfig:
    """Load an OutputConfig from a JSON file.

    If path is None or empty, returns a default config.
    
    Relative paths are resolved by trying (in order):
    1. Current working directory
    2. Next to the calling script (__main__.__file__)
    3. Next to this module file

    Args:
        path: Path to a JSON config file, or None for defaults.

    Returns:
        OutputConfig with the loaded (or default) settings.
    """
    if not path:
        return OutputConfig(
            logData={
                "absolute_input": True,
                "delta_input": False,
                "absolute_transformed": False,
                "delta_transformed": False,
                "velocity": False,
            },
            logDataFormat={
                "quaternion": True,
                "rotation_vector": False,
                "euler_radian": False,
                "euler_degree": False,
            },
            scale=1.0,
            outputAxes={"x": 1.0, "y": 1.0, "z": 1.0},
        )

    p = Path(path)
    if not p.is_absolute() and not p.exists():
        # Try relative to the importing script if available (runtime dependent)
        try:
            import __main__  # type: ignore
            main_file = getattr(__main__, "__file__", None)
            if isinstance(main_file, str):
                alt = Path(main_file).parent.joinpath(path)
                if alt.exists():
                    p = alt
        except Exception:
            pass
    if not p.is_absolute() and not p.exists():
        # Try relative to this module file
        alt2 = Path(__file__).parent.joinpath(path)
        if alt2.exists():
            p = alt2

    data: Dict[str, Any] = json.loads(p.read_text())

    tf_deg = data.get("targetFramePose")
    targetFrame = None
    if tf_deg:
        targetFrame = {
            "x": float(tf_deg.get("x", 0.0)),
            "y": float(tf_deg.get("y", 0.0)),
            "z": float(tf_deg.get("z", 0.0)),
            "x_rot": math.radians(float(tf_deg.get("x_rot_deg", 0.0))),
            "y_rot": math.radians(float(tf_deg.get("y_rot_deg", 0.0))),
            "z_rot": math.radians(float(tf_deg.get("z_rot_deg", 0.0))),
        }
    else:
        tf = data.get("targetFrame")
        if tf:
            targetFrame = tf

    # Parse authentication credentials
    auth = data.get("authCredentials")
    auth_name = auth.get("name") if isinstance(auth, dict) else None
    auth_code = auth.get("code") if isinstance(auth, dict) else None

    # Parse resampling settings
    upsample_hz = data.get("upsample_to_frequency_hz")
    rate_limit_hz = data.get("rate_limit_frequency_hz")
    
    # Convert to float if provided, otherwise None
    upsample_to_frequency_hz = float(upsample_hz) if upsample_hz is not None else None
    rate_limit_frequency_hz = float(rate_limit_hz) if rate_limit_hz is not None else None

    # Parse motion limiting settings
    vel_limit_raw = data.get("vel_limit")
    acc_limit_raw = data.get("acc_limit")
    vel_limit = float(vel_limit_raw) if vel_limit_raw is not None else None
    acc_limit = float(acc_limit_raw) if acc_limit_raw is not None else None

    return OutputConfig(
        logData=data.get(
            "logData",
            data.get(  # Backwards compatibility: fall back to old names
                "logFormats",
                data.get(
                    "includeFormats",
                    {
                        "absolute_input": True,
                        "delta_input": False,
                        "absolute_transformed": False,
                        "delta_transformed": False,
                        "velocity": False,
                    },
                ),
            ),
        ),
        logDataFormat=data.get(
            "logDataFormat",
            data.get(  # Backwards compatibility: fall back to old name
                "includeOrientation",
                {"quaternion": True, "rotation_vector": False, "euler_radian": False, "euler_degree": False},
            ),
        ),
        scale=float(data.get("scale", 1.0)),
        outputAxes=data.get("outputAxes", {"x": 1.0, "y": 1.0, "z": 1.0}),
        targetFrame=targetFrame,
        auth_name=auth_name,
        auth_code=auth_code,
        upsample_to_frequency_hz=upsample_to_frequency_hz,
        rate_limit_frequency_hz=rate_limit_frequency_hz,
        vel_limit=vel_limit,
        acc_limit=acc_limit,
    )

