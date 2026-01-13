"""Pose resampling for Televoodoo.

Provides upsampling (via linear extrapolation) and rate limiting for pose data.
Useful for robot arm controllers that require higher frequency input (100-200 Hz)
than the phone app provides (30-60 Hz).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from .pose import Pose
from . import math as tvm


@dataclass
class _TimestampedPose:
    """Pose with timestamp for extrapolation calculations."""
    pose: Pose
    timestamp: float  # monotonic time


class PoseResampler:
    """Resample pose data to a target frequency using linear extrapolation.
    
    This class receives poses at the phone's native rate (30-60 Hz) and outputs
    poses at a higher target frequency (e.g., 200 Hz) using forward-looking
    linear extrapolation. Real poses are forwarded immediately with zero added
    latency; extrapolated poses fill the gaps between real samples.
    
    Safety feature: Extrapolation only continues for one expected sample interval
    beyond the last real pose. If no new pose arrives, extrapolation stops to
    prevent runaway robot motion from stale predictions.
    
    Example:
        >>> from televoodoo import start_televoodoo, PoseResampler, PoseProvider
        >>> 
        >>> resampler = PoseResampler(upsample_to_hz=200.0)
        >>> provider = PoseProvider(config)
        >>> 
        >>> def robot_handler(evt):
        ...     delta = provider.get_delta(evt)
        ...     if delta:
        ...         robot.send_delta(delta['dx'], delta['dy'], delta['dz'])
        >>> 
        >>> resampler.start(callback=robot_handler)
        >>> 
        >>> def on_raw_pose(evt):
        ...     resampler.feed(evt)
        >>> 
        >>> start_televoodoo(callback=on_raw_pose, quiet=True)
    """
    
    def __init__(
        self,
        upsample_to_hz: Optional[float] = None,
        rate_limit_hz: Optional[float] = None,
        regulated: bool = False,
    ):
        """Initialize the resampler.
        
        Args:
            upsample_to_hz: Target output frequency in Hz. If provided, poses will
                be emitted at this rate using linear extrapolation between real
                samples.
            rate_limit_hz: Maximum output frequency in Hz. If provided, excess
                poses are dropped, always keeping the most recent pose.
            regulated: If True, output ONLY from the upsampling thread at fixed
                intervals. Real poses update the buffer but don't emit directly.
                This gives perfectly consistent timing at the cost of up to one
                tick of latency (e.g., 5ms at 200 Hz). If False (default), real
                poses are forwarded immediately for zero latency.
        """
        self.upsample_to_hz = upsample_to_hz
        self.rate_limit_hz = rate_limit_hz
        self.regulated = regulated
        
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Pose buffer for extrapolation (last 2 poses)
        self._pose_buffer: list[_TimestampedPose] = []
        self._buffer_lock = threading.Lock()
        
        # For tracking input frequency (adaptive extrapolation limit)
        self._input_intervals: list[float] = []
        self._max_interval_samples = 10  # Rolling window for frequency estimation
        
        # Rate limiting state
        self._last_emit_time: float = 0.0
        self._rate_limit_lock = threading.Lock()
        
        # Latest pose for rate-limited emission
        self._latest_pose_for_rate_limit: Optional[Dict[str, Any]] = None
        
        # Track when real poses were emitted (to avoid redundant extrapolation)
        self._last_real_pose_emit_time: float = 0.0
        self._real_pose_lock = threading.Lock()
    
    def start(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Start the resampler with the given callback.
        
        Args:
            callback: Function called for each output pose event. Will receive
                pose events in the same format as the Televoodoo callback.
        """
        if self._running:
            return
        
        self._callback = callback
        self._running = True
        
        # Start upsampling thread if upsampling is enabled
        if self.upsample_to_hz is not None and self.upsample_to_hz > 0:
            self._thread = threading.Thread(
                target=self._upsampling_loop,
                daemon=True,
                name="PoseResampler-Upsampler"
            )
            self._thread.start()
    
    def stop(self) -> None:
        """Stop the resampler."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._callback = None
    
    def feed(self, evt: Dict[str, Any]) -> None:
        """Feed a raw pose event to the resampler.
        
        This should be called from the Televoodoo callback with each incoming
        pose event. Non-pose events are passed through directly.
        
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
        
        with self._buffer_lock:
            # Track input frequency for adaptive extrapolation limit
            if self._pose_buffer:
                interval = now - self._pose_buffer[-1].timestamp
                self._input_intervals.append(interval)
                if len(self._input_intervals) > self._max_interval_samples:
                    self._input_intervals.pop(0)
            
            # Reset buffer on movement_start (can't extrapolate across movements)
            if pose.movement_start:
                self._pose_buffer.clear()
                self._input_intervals.clear()
            
            # Add to buffer (keep last 2)
            self._pose_buffer.append(_TimestampedPose(pose=pose, timestamp=now))
            if len(self._pose_buffer) > 2:
                self._pose_buffer.pop(0)
        
        # In regulated mode, don't emit here - let upsampling thread handle all output
        # In non-regulated mode, emit real pose immediately (zero latency)
        if not self.regulated:
            self._emit_pose(evt, is_real=True)
    
    def _emit_pose(self, evt: Dict[str, Any], is_real: bool = True) -> None:
        """Emit a pose event through the callback, applying rate limiting if configured.
        
        Args:
            evt: Pose event to emit.
            is_real: True if this is a real (non-extrapolated) pose.
        """
        if self._callback is None:
            return
        
        now = time.monotonic()
        
        # Track real pose emit time (for extrapolation thread to avoid redundant outputs)
        if is_real:
            with self._real_pose_lock:
                self._last_real_pose_emit_time = now
        
        # Apply rate limiting if configured
        if self.rate_limit_hz is not None and self.rate_limit_hz > 0:
            min_interval = 1.0 / self.rate_limit_hz
            
            with self._rate_limit_lock:
                # Always store latest pose
                self._latest_pose_for_rate_limit = evt
                
                # Check if enough time has passed
                elapsed = now - self._last_emit_time
                if elapsed < min_interval:
                    # Not time yet - the latest pose will be used when timer fires
                    # For real poses, we skip them if rate limited
                    # For extrapolated poses, we also skip
                    return
                
                self._last_emit_time = now
                # Use the latest pose (which we just stored)
                evt = self._latest_pose_for_rate_limit
        
        try:
            self._callback(evt)
        except Exception:
            pass
    
    def _get_expected_input_interval(self) -> float:
        """Get the expected interval between input poses based on recent history.
        
        Returns:
            Expected interval in seconds. Defaults to 1/30 Hz (BLE worst case)
            if no history is available.
        """
        with self._buffer_lock:
            if not self._input_intervals:
                return 1.0 / 30.0  # Default to 30 Hz (BLE worst case)
            return sum(self._input_intervals) / len(self._input_intervals)
    
    def _upsampling_loop(self) -> None:
        """Background thread that emits extrapolated poses at the target rate."""
        if self.upsample_to_hz is None or self.upsample_to_hz <= 0:
            return
        
        interval = 1.0 / self.upsample_to_hz
        
        # Use fixed-interval scheduling to avoid drift
        next_tick = time.monotonic()
        
        # Track last emitted pose timestamp for regulated mode
        last_emitted_pose_ts = 0.0
        
        while self._running:
            next_tick += interval
            now = time.monotonic()
            
            if self.regulated:
                # Regulated mode: always output at fixed interval
                # Use latest real pose or extrapolation
                evt = self._get_regulated_output(last_emitted_pose_ts)
                if evt is not None:
                    self._emit_pose(evt, is_real=False)
                    # Update last emitted timestamp
                    with self._buffer_lock:
                        if self._pose_buffer:
                            last_emitted_pose_ts = self._pose_buffer[-1].timestamp
            else:
                # Non-regulated mode: skip if real pose was just emitted
                with self._real_pose_lock:
                    time_since_real = now - self._last_real_pose_emit_time
                
                if time_since_real < interval:
                    # Real pose was just emitted, skip this extrapolation tick
                    pass
                else:
                    # Try to extrapolate and emit
                    extrapolated_evt = self._extrapolate_pose()
                    if extrapolated_evt is not None:
                        self._emit_pose(extrapolated_evt, is_real=False)
            
            # Sleep until next tick
            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -interval:
                # We're way behind - reset schedule to avoid catching up bursts
                next_tick = time.monotonic()
    
    def _get_regulated_output(self, last_emitted_ts: float) -> Optional[Dict[str, Any]]:
        """Get output for regulated mode: latest real pose or extrapolation.
        
        In regulated mode, we ALWAYS output at fixed intervals. Each output is either:
        - The latest real pose (if a new one arrived since last_emitted_ts)
        - An extrapolated pose based on velocity
        - The last known pose (if extrapolation fails due to safety limit)
        
        Args:
            last_emitted_ts: Timestamp of the last pose we emitted
            
        Returns:
            Pose event to emit, or None if no data available at all.
        """
        with self._buffer_lock:
            if not self._pose_buffer:
                return None
            
            latest = self._pose_buffer[-1]
            
            # Build the latest real pose event (used as output or fallback)
            latest_pose_evt = {
                "type": "pose",
                "data": {
                    "absolute_input": {
                        "movement_start": False,  # Only first emission of a real pose is movement_start
                        "x": latest.pose.x,
                        "y": latest.pose.y,
                        "z": latest.pose.z,
                        "qx": latest.pose.qx,
                        "qy": latest.pose.qy,
                        "qz": latest.pose.qz,
                        "qw": latest.pose.qw,
                    }
                }
            }
            
            # Check if we have a new real pose since last emission
            if latest.timestamp > last_emitted_ts:
                # New real pose - include movement_start flag
                latest_pose_evt["data"]["absolute_input"]["movement_start"] = latest.pose.movement_start
                return latest_pose_evt
            
            # Need at least 2 poses for extrapolation
            if len(self._pose_buffer) < 2:
                return latest_pose_evt
            
            p0 = self._pose_buffer[0]
            p1 = self._pose_buffer[1]
            now = time.monotonic()
            time_since_last = now - p1.timestamp
            dt_samples = p1.timestamp - p0.timestamp
            
            if dt_samples <= 0:
                return latest_pose_evt
            
            # Position extrapolation
            vx = (p1.pose.x - p0.pose.x) / dt_samples
            vy = (p1.pose.y - p0.pose.y) / dt_samples
            vz = (p1.pose.z - p0.pose.z) / dt_samples
            
            pred_x = p1.pose.x + vx * time_since_last
            pred_y = p1.pose.y + vy * time_since_last
            pred_z = p1.pose.z + vz * time_since_last
            
            # Orientation extrapolation
            q0 = p0.pose.quaternion
            q1 = p1.pose.quaternion
            q_delta = tvm.quat_delta(q0, q1, frame="base")
            omega = tvm.quat_to_rotvec(q_delta)
            scale = time_since_last / dt_samples
            omega_extrapolated = (omega[0] * scale, omega[1] * scale, omega[2] * scale)
            q_extra = tvm.rotvec_to_quat(omega_extrapolated)
            pred_q = tvm.quat_multiply(q_extra, q1)
            pred_q = tvm.quat_normalize(pred_q)
            
            # Check safety limit - but in regulated mode, use last pose as fallback instead of None
            expected_interval = self._get_expected_input_interval_unlocked()
            if time_since_last > expected_interval * 2:  # Allow 2x expected interval before falling back
                # Safety: stop extrapolating, output last known pose (robot holds position)
                return latest_pose_evt
            
            return {
                "type": "pose",
                "data": {
                    "absolute_input": {
                        "movement_start": False,
                        "x": pred_x,
                        "y": pred_y,
                        "z": pred_z,
                        "qx": pred_q[0],
                        "qy": pred_q[1],
                        "qz": pred_q[2],
                        "qw": pred_q[3],
                    }
                }
            }

    def _extrapolate_pose(self) -> Optional[Dict[str, Any]]:
        """Extrapolate a pose based on the last two real poses.
        
        Returns:
            Extrapolated pose event, or None if extrapolation is not possible
            or should be stopped (safety limit reached).
        """
        now = time.monotonic()
        
        with self._buffer_lock:
            # Need at least 2 poses for extrapolation
            if len(self._pose_buffer) < 2:
                return None
            
            p0 = self._pose_buffer[0]  # Older pose
            p1 = self._pose_buffer[1]  # Newer pose (most recent real pose)
            
            # Calculate time since last real pose
            time_since_last = now - p1.timestamp
            
            # Safety limit: only extrapolate for one expected input interval
            # This prevents runaway motion if the phone disconnects
            expected_interval = self._get_expected_input_interval_unlocked()
            if time_since_last > expected_interval:
                # Stop extrapolating - we've gone past when the next pose should have arrived
                return None
            
            # Calculate velocity from the two poses
            dt_samples = p1.timestamp - p0.timestamp
            if dt_samples <= 0:
                return None
            
            # Position extrapolation: p_predicted = p1 + velocity * dt
            vx = (p1.pose.x - p0.pose.x) / dt_samples
            vy = (p1.pose.y - p0.pose.y) / dt_samples
            vz = (p1.pose.z - p0.pose.z) / dt_samples
            
            pred_x = p1.pose.x + vx * time_since_last
            pred_y = p1.pose.y + vy * time_since_last
            pred_z = p1.pose.z + vz * time_since_last
            
            # Orientation extrapolation using angular velocity
            q0 = p0.pose.quaternion
            q1 = p1.pose.quaternion
            
            # Compute angular velocity as rotation vector
            q_delta = tvm.quat_delta(q0, q1, frame="base")
            omega = tvm.quat_to_rotvec(q_delta)
            
            # Scale angular velocity by time ratio
            scale = time_since_last / dt_samples
            omega_extrapolated = (omega[0] * scale, omega[1] * scale, omega[2] * scale)
            
            # Apply extrapolated rotation to p1's orientation
            q_extra = tvm.rotvec_to_quat(omega_extrapolated)
            pred_q = tvm.quat_multiply(q_extra, q1)
            pred_q = tvm.quat_normalize(pred_q)
        
        # Build extrapolated pose event (same format as real events)
        return {
            "type": "pose",
            "data": {
                "absolute_input": {
                    "movement_start": False,  # Extrapolated poses are never movement starts
                    "x": pred_x,
                    "y": pred_y,
                    "z": pred_z,
                    "qx": pred_q[0],
                    "qy": pred_q[1],
                    "qz": pred_q[2],
                    "qw": pred_q[3],
                }
            }
        }
    
    def _get_expected_input_interval_unlocked(self) -> float:
        """Get expected input interval without acquiring the lock.
        
        Must be called while holding _buffer_lock.
        """
        if not self._input_intervals:
            return 1.0 / 30.0  # Default to 30 Hz (BLE worst case)
        return sum(self._input_intervals) / len(self._input_intervals)
    
    @property
    def is_running(self) -> bool:
        """Whether the resampler is currently running."""
        return self._running
