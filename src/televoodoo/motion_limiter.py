"""Motion limiting for Televoodoo.

Provides velocity and acceleration limiting for pose data to ensure safe robot motion.
When incoming poses would cause motion exceeding configured limits, the output pose
is clamped to respect maximum velocity and acceleration.
"""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from .pose import Pose


@dataclass
class _TimestampedPose:
    """Pose with timestamp for motion calculations."""
    pose: Pose
    timestamp: float  # monotonic time


class MotionLimiter:
    """Limits velocity and acceleration of pose stream for safety.
    
    When incoming poses would cause motion exceeding the configured limits,
    the output pose is clamped to respect maximum velocity/acceleration.
    Orientation is passed through unchanged (only position is limited).
    
    The limiter tracks:
    - Previous pose and timestamp for velocity calculation
    - Previous velocity for acceleration calculation
    
    On movement_start, internal state is reset (first pose passes through).
    
    Example:
        >>> from televoodoo import MotionLimiter
        >>> 
        >>> limiter = MotionLimiter(vel_limit=0.5, acc_limit=2.0)
        >>> limiter.start(callback=robot_handler)
        >>> 
        >>> def on_pose(evt):
        ...     limiter.feed(evt)
        >>> 
        >>> start_televoodoo(callback=on_pose)
    """
    
    def __init__(
        self,
        vel_limit: Optional[float] = None,
        acc_limit: Optional[float] = None,
        quiet: bool = False,
    ):
        """Initialize the motion limiter.
        
        Args:
            vel_limit: Maximum velocity in m/s. If None, velocity is not limited.
            acc_limit: Maximum acceleration in m/s². Applies symmetrically to
                acceleration and deceleration. If None, acceleration is not limited.
            quiet: If True, suppress warning messages when limits are applied.
        """
        self.vel_limit = vel_limit
        self.acc_limit = acc_limit
        self.quiet = quiet
        
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._running = False
        
        # State for limiting calculations
        self._prev_pose: Optional[_TimestampedPose] = None
        self._prev_velocity: float = 0.0  # Previous velocity magnitude (m/s)
        self._lock = threading.Lock()
        
        # Track last emitted (potentially limited) position for continuity
        self._last_emitted_position: Optional[Tuple[float, float, float]] = None
    
    def start(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Start the motion limiter with the given callback.
        
        Args:
            callback: Function called for each output pose event. Will receive
                pose events in the same format as the Televoodoo callback,
                with an additional "limited" field if limiting was applied.
        """
        if self._running:
            return
        
        self._callback = callback
        self._running = True
        self._reset_state()
    
    def stop(self) -> None:
        """Stop the motion limiter."""
        self._running = False
        self._callback = None
        self._reset_state()
    
    def _reset_state(self) -> None:
        """Reset internal state (called on start, stop, and movement_start)."""
        with self._lock:
            self._prev_pose = None
            self._prev_velocity = 0.0
            self._last_emitted_position = None
    
    def feed(self, evt: Dict[str, Any]) -> None:
        """Feed a pose event to the limiter.
        
        Non-pose events are passed through directly. Pose events are processed
        and potentially limited before being forwarded to the callback.
        
        Args:
            evt: Event dictionary from Televoodoo callback.
        """
        if not self._running or self._callback is None:
            return
        
        # Pass through non-pose events immediately
        if evt.get("type") != "pose":
            self._callback(evt)
            return
        
        # Parse pose from event
        pose = Pose.from_teleop_event(evt)
        if pose is None:
            return
        
        now = time.monotonic()
        
        with self._lock:
            # Reset state on movement_start
            if pose.movement_start:
                self._prev_pose = None
                self._prev_velocity = 0.0
                self._last_emitted_position = None
            
            # First pose after reset - pass through unchanged
            if self._prev_pose is None:
                self._prev_pose = _TimestampedPose(pose=pose, timestamp=now)
                self._last_emitted_position = (pose.x, pose.y, pose.z)
                self._emit_pose(evt, limited=False)
                return
            
            # Calculate time delta
            dt = now - self._prev_pose.timestamp
            if dt <= 0:
                # Same timestamp - pass through unchanged
                self._emit_pose(evt, limited=False)
                return
            
            # Use last emitted position as reference (for continuity after limiting)
            ref_pos = self._last_emitted_position
            if ref_pos is None:
                ref_pos = (self._prev_pose.pose.x, self._prev_pose.pose.y, self._prev_pose.pose.z)
            
            # Calculate displacement from reference position
            dx = pose.x - ref_pos[0]
            dy = pose.y - ref_pos[1]
            dz = pose.z - ref_pos[2]
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)
            
            # Calculate current velocity
            velocity = distance / dt if dt > 0 else 0.0
            
            # Apply limits
            limited_velocity = velocity
            limited = False
            limit_reasons = []
            
            # Acceleration limiting (symmetric - applies to both acceleration and deceleration)
            if self.acc_limit is not None and self.acc_limit > 0:
                acceleration = (velocity - self._prev_velocity) / dt
                if abs(acceleration) > self.acc_limit:
                    # Clamp acceleration
                    sign = 1.0 if acceleration > 0 else -1.0
                    max_velocity_change = self.acc_limit * dt
                    limited_velocity = self._prev_velocity + sign * max_velocity_change
                    # Ensure velocity doesn't go negative
                    limited_velocity = max(0.0, limited_velocity)
                    limited = True
                    limit_reasons.append(f"acc={acceleration:.2f}m/s² > {self.acc_limit}m/s²")
            
            # Velocity limiting (after acceleration limiting)
            if self.vel_limit is not None and self.vel_limit > 0:
                if limited_velocity > self.vel_limit:
                    limited_velocity = self.vel_limit
                    limited = True
                    if f"vel={velocity:.2f}m/s > {self.vel_limit}m/s" not in limit_reasons:
                        limit_reasons.append(f"vel={velocity:.2f}m/s > {self.vel_limit}m/s")
            
            # Calculate limited position
            if limited and distance > 0:
                # Scale displacement to match limited velocity
                limited_distance = limited_velocity * dt
                scale = limited_distance / distance
                
                new_x = ref_pos[0] + dx * scale
                new_y = ref_pos[1] + dy * scale
                new_z = ref_pos[2] + dz * scale
                
                # Log warning
                if not self.quiet and limit_reasons:
                    self._log_warning(limit_reasons)
                
                # Create limited event
                limited_evt = self._create_limited_event(evt, new_x, new_y, new_z)
                self._last_emitted_position = (new_x, new_y, new_z)
                self._prev_velocity = limited_velocity
                self._prev_pose = _TimestampedPose(pose=pose, timestamp=now)
                self._emit_pose(limited_evt, limited=True)
            else:
                # No limiting needed
                self._last_emitted_position = (pose.x, pose.y, pose.z)
                self._prev_velocity = velocity
                self._prev_pose = _TimestampedPose(pose=pose, timestamp=now)
                self._emit_pose(evt, limited=False)
    
    def _emit_pose(self, evt: Dict[str, Any], limited: bool) -> None:
        """Emit a pose event through the callback.
        
        Args:
            evt: Pose event to emit.
            limited: Whether this pose was limited.
        """
        if self._callback is None:
            return
        
        # Add limited flag to event
        if limited:
            evt = self._add_limited_flag(evt)
        
        try:
            self._callback(evt)
        except Exception:
            pass
    
    def _add_limited_flag(self, evt: Dict[str, Any]) -> Dict[str, Any]:
        """Add limited=True flag to pose event data.
        
        Args:
            evt: Original pose event.
            
        Returns:
            New event with limited flag added.
        """
        # Deep copy the event to avoid modifying the original
        new_evt = {"type": "pose", "data": {}}
        
        data = evt.get("data", {})
        for key, value in data.items():
            if isinstance(value, dict):
                new_evt["data"][key] = {**value, "limited": True}
            else:
                new_evt["data"][key] = value
        
        return new_evt
    
    def _create_limited_event(
        self,
        original_evt: Dict[str, Any],
        new_x: float,
        new_y: float,
        new_z: float,
    ) -> Dict[str, Any]:
        """Create a new event with limited position values.
        
        Orientation (quaternion) is preserved unchanged.
        
        Args:
            original_evt: Original pose event.
            new_x, new_y, new_z: Limited position values.
            
        Returns:
            New event with limited position.
        """
        data = original_evt.get("data", {})
        new_data: Dict[str, Any] = {}
        
        for key, value in data.items():
            if isinstance(value, dict) and "x" in value and "y" in value and "z" in value:
                # This is a pose dict - update position, keep orientation
                new_value = dict(value)
                new_value["x"] = new_x
                new_value["y"] = new_y
                new_value["z"] = new_z
                new_data[key] = new_value
            else:
                new_data[key] = value
        
        return {"type": "pose", "data": new_data}
    
    def _log_warning(self, reasons: list[str]) -> None:
        """Log a warning message about motion limiting.
        
        Args:
            reasons: List of limit reasons (e.g., ["vel=1.5m/s > 0.5m/s"]).
        """
        msg = {
            "type": "motion_limit_warning",
            "message": f"Motion limited: {', '.join(reasons)}",
            "reasons": reasons,
        }
        print(json.dumps(msg), flush=True)
    
    @property
    def is_running(self) -> bool:
        """Whether the limiter is currently running."""
        return self._running
