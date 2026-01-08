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
        includeFormats: Which output formats to include (absolute_input, delta_input, etc.)
        includeOrientation: Which orientation formats to include (quaternion, euler_radian, euler_degree)
        scale: Scale factor applied to position values
        outputAxes: Axis multipliers for output (can flip axes with -1)
        targetFrame: Pose of target coordinate system relative to reference/world (Euler radians)
        ble_name: Optional static BLE peripheral name (overrides random generation)
        ble_code: Optional static authentication code (overrides random generation)
    """
    includeFormats: Dict[str, bool]
    includeOrientation: Dict[str, bool]
    scale: float
    outputAxes: Dict[str, float]
    # Pose of Target Coordinate System relative to reference/world (Euler radians)
    targetFrame: Optional[Dict[str, float]] = None
    # BLE credentials (optional, can be set in config file)
    ble_name: Optional[str] = None
    ble_code: Optional[str] = None


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
            includeFormats={
                "absolute_input": True,
                "delta_input": False,
                "absolute_transformed": True,
                "delta_transformed": False,
            },
            includeOrientation={
                "quaternion": True,
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

    tf_deg = data.get("targetFrameDegrees")
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

    # Parse BLE credentials if present
    ble = data.get("ble", {})
    ble_name = ble.get("name") if isinstance(ble, dict) else None
    ble_code = ble.get("code") if isinstance(ble, dict) else None

    return OutputConfig(
        includeFormats=data.get(
            "includeFormats",
            {
                "absolute_input": True,
                "delta_input": False,
                "absolute_transformed": True,
                "delta_transformed": False,
            },
        ),
        includeOrientation=data.get(
            "includeOrientation",
            {"quaternion": True, "euler_radian": False, "euler_degree": False},
        ),
        scale=float(data.get("scale", 1.0)),
        outputAxes=data.get("outputAxes", {"x": 1.0, "y": 1.0, "z": 1.0}),
        targetFrame=targetFrame,
        ble_name=ble_name,
        ble_code=ble_code,
    )

