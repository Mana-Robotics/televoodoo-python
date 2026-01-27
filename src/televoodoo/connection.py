"""Connection management for Televoodoo.

This module provides the main entry point for starting Televoodoo with
different connection backends (BLE, WiFi, USB).

WiFi and USB use the same TCP server with UDP beacon discovery - the phone app
discovers the service via UDP beacons regardless of which network interface
(WiFi or USB tethering) is being used.
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Literal, Optional, TYPE_CHECKING

from .session import generate_credentials, print_session_qr
from .tcp_service import DEFAULT_TCP_PORT, DEFAULT_BEACON_PORT

if TYPE_CHECKING:
    from .config import OutputConfig


ConnectionType = Literal["auto", "ble", "wifi", "usb"]


def _print_usb_setup_info() -> None:
    """Print USB setup requirements for iOS and Android."""
    print(json.dumps({
        "type": "usb_setup_info",
        "message": "USB connection requires different setup for iOS vs Android",
        "ios_setup": {
            "description": "iOS uses TCP tunneling via MobileDevice framework",
            "mac": "No setup needed (built-in)",
            "linux": "Install: sudo apt install libimobiledevice6 usbmuxd",
            "windows": "Install iTunes (provides drivers)",
        },
        "android_setup": {
            "description": "Android uses USB Tethering (creates network interface)",
            "steps": "Enable USB Tethering in Android settings",
        },
    }), flush=True)


def start_televoodoo(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    name: Optional[str] = None,
    code: Optional[str] = None,
    connection: ConnectionType = "auto",
    tcp_port: int = DEFAULT_TCP_PORT,
    beacon_port: int = DEFAULT_BEACON_PORT,
    upsample_to_hz: Optional[float] = None,
    rate_limit_hz: Optional[float] = None,
    regulated: Optional[bool] = None,
    vel_limit: Optional[float] = None,
    acc_limit: Optional[float] = None,
    config: Optional["OutputConfig"] = None,
    initial_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Start Televoodoo and wait for phone app connection.

    Generates a session with QR code for the phone app to scan, then starts
    the connection backend and calls the callback for each teleoperation event.

    For WiFi and USB, the server uses UDP beacon broadcast for discovery.
    The phone app discovers the service via beacons - no IP address needed in QR code.

    Args:
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging (pose, heartbeat)
        name: Static peripheral/server name (default: random)
        code: Static auth code (default: random)
        connection: Connection type - "auto" (default), "ble", "wifi", or "usb"
        tcp_port: TCP port for data (default: 50000)
        beacon_port: UDP port for beacon broadcast (default: 50001)
        upsample_to_hz: Upsample poses to target frequency using linear extrapolation.
            Useful for robot controllers requiring higher frequency input (100-200 Hz).
        rate_limit_hz: Limit output to maximum frequency (drops excess poses).
        regulated: Controls timing when upsampling. Default (None) enables regulated
            mode when upsampling for consistent timing (~5ms max latency). Set to
            False for zero latency with irregular timing.
        vel_limit: Maximum velocity in m/s. Poses exceeding this limit are clamped.
        acc_limit: Maximum acceleration in m/s². Symmetric (applies to deceleration).
        config: Optional OutputConfig. If provided and parameters are not set directly,
            values will be read from config (upsample_to_frequency_hz, 
            rate_limit_frequency_hz, vel_limit, acc_limit).
        initial_config: Optional initial configuration to send to phone after auth.

    Raises:
        RuntimeError: If the requested connection type is not supported on this platform.
    """
    # Use provided credentials or generate random ones
    if name is None or code is None:
        gen_name, gen_code = generate_credentials()
        name = name or gen_name
        code = code or gen_code

    # Determine connection backend
    resolved_connection = connection
    if resolved_connection == "auto":
        resolved_connection = _detect_best_connection()

    # Print USB setup requirements if USB connection selected
    if resolved_connection == "usb":
        _print_usb_setup_info()

    # Print session/QR with transport info
    # Phone app uses UDP beacons to discover the service
    print_session_qr(
        name=name,
        code=code,
        transport=resolved_connection,
    )

    # Resolve settings from config if not provided directly
    effective_upsample_hz = upsample_to_hz
    effective_rate_limit_hz = rate_limit_hz
    effective_vel_limit = vel_limit
    effective_acc_limit = acc_limit
    
    if config is not None:
        if effective_upsample_hz is None:
            effective_upsample_hz = getattr(config, 'upsample_to_frequency_hz', None)
        if effective_rate_limit_hz is None:
            effective_rate_limit_hz = getattr(config, 'rate_limit_frequency_hz', None)
        if effective_vel_limit is None:
            effective_vel_limit = getattr(config, 'vel_limit', None)
        if effective_acc_limit is None:
            effective_acc_limit = getattr(config, 'acc_limit', None)

    # Set up processing chain: raw -> motion_limiter -> resampler -> callback
    effective_callback = callback
    resampler = None
    motion_limiter = None
    
    # Set up motion limiting if enabled
    if effective_vel_limit is not None or effective_acc_limit is not None:
        from .motion_limiter import MotionLimiter
        
        motion_limiter = MotionLimiter(
            vel_limit=effective_vel_limit,
            acc_limit=effective_acc_limit,
            quiet=quiet,
        )
        
        print(json.dumps({
            "type": "motion_limiting_enabled",
            "vel_limit": effective_vel_limit,
            "acc_limit": effective_acc_limit,
        }), flush=True)
    
    if effective_upsample_hz is not None or effective_rate_limit_hz is not None:
        from .resampler import PoseResampler
        
        # Default to regulated=True when upsampling (consistent timing, ~5ms max latency)
        effective_regulated = regulated if regulated is not None else (effective_upsample_hz is not None)
        
        resampler = PoseResampler(
            upsample_to_hz=effective_upsample_hz,
            rate_limit_hz=effective_rate_limit_hz,
            regulated=effective_regulated,
        )
        
        if callback is not None:
            resampler.start(callback=callback)
        
        if effective_upsample_hz:
            print(json.dumps({
                "type": "resampling_enabled",
                "upsample_to_hz": effective_upsample_hz,
                "rate_limit_hz": effective_rate_limit_hz,
                "regulated": effective_regulated,
            }), flush=True)

    # Build the processing chain: raw -> motion_limiter -> resampler -> callback
    # Chain is built from the end backwards
    if resampler is not None:
        # Resampler feeds to user callback (already started above)
        def feed_resampler(evt: Dict[str, Any]) -> None:
            resampler.feed(evt)
        effective_callback = feed_resampler
    
    if motion_limiter is not None:
        # Motion limiter feeds to resampler (or callback if no resampler)
        next_callback = effective_callback
        if next_callback is not None:
            motion_limiter.start(callback=next_callback)
        
        def feed_limiter(evt: Dict[str, Any]) -> None:
            motion_limiter.feed(evt)
        effective_callback = feed_limiter

    try:
        if resolved_connection == "ble":
            _start_ble(name, code, effective_callback, quiet, initial_config)
        elif resolved_connection in ("wifi", "usb"):
            # WiFi and USB use the same TCP server - beacons advertise on all interfaces
            # The phone discovers via UDP beacons regardless of which interface it's on
            _start_tcp_server(name, code, effective_callback, quiet, tcp_port, beacon_port, initial_config)
        else:
            raise RuntimeError(f"Unknown connection type: {resolved_connection}")
    except Exception as e:
        print(
            json.dumps({"type": "error", "message": f"Connection failed: {e}"}),
            flush=True,
        )
        raise
    finally:
        # Clean up motion limiter and resampler if they were created
        if motion_limiter is not None:
            motion_limiter.stop()
        if resampler is not None:
            resampler.stop()


def _detect_best_connection() -> Literal["ble", "wifi"]:
    """Detect the best available connection type for this platform.

    Defaults to WiFi for better latency and cross-platform compatibility.
    """
    # WiFi is the recommended default:
    # - Lower latency (~16ms consistent vs BLE batching)
    # - Works on all platforms with network access
    # - No platform-specific BLE dependencies
    return "wifi"


def _start_ble(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    initial_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Start BLE peripheral backend."""
    from . import ble

    ble.run_peripheral(name, code, callback, quiet, initial_config)


def _start_tcp_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    tcp_port: int,
    beacon_port: int,
    initial_config: Optional[Dict[str, Any]],
) -> None:
    """Start TCP server backend.
    
    This server works for both WiFi and USB connections:
    - Binds to 0.0.0.0 (all interfaces)
    - Broadcasts UDP beacons on all interfaces
    - Phone discovers via UDP beacons regardless of connection type
    """
    from . import tcp_service

    tcp_service.run_server(
        name=name,
        code=code,
        callback=callback,
        quiet=quiet,
        tcp_port=tcp_port,
        beacon_port=beacon_port,
        initial_config=initial_config,
    )
