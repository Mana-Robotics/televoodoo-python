"""Connection management for Televoodoo.

This module provides the main entry point for starting Televoodoo with
different connection backends (BLE, WIFI, etc.).
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Literal, Optional, TYPE_CHECKING

from .session import generate_credentials, print_session_qr
from .wifi import DEFAULT_PORT as WIFI_DEFAULT_PORT

if TYPE_CHECKING:
    from .config import OutputConfig


ConnectionType = Literal["auto", "ble", "wifi", "usb"]


def start_televoodoo(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    name: Optional[str] = None,
    code: Optional[str] = None,
    connection: ConnectionType = "auto",
    wifi_port: int = WIFI_DEFAULT_PORT,
    upsample_to_hz: Optional[float] = None,
    rate_limit_hz: Optional[float] = None,
    regulated: Optional[bool] = None,
    config: Optional["OutputConfig"] = None,
) -> None:
    """Start Televoodoo and wait for phone app connection.

    Generates a session with QR code for the phone app to scan, then starts
    the connection backend and calls the callback for each teleoperation event.

    Args:
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging (pose, heartbeat)
        name: Static peripheral/server name (default: random)
        code: Static auth code (default: random)
        connection: Connection type - "auto" (default), "ble", "wifi", or "usb"
        wifi_port: UDP port for WIFI/USB server (default: 50000)
        upsample_to_hz: Upsample poses to target frequency using linear extrapolation.
            Useful for robot controllers requiring higher frequency input (100-200 Hz).
        rate_limit_hz: Limit output to maximum frequency (drops excess poses).
        regulated: Controls timing when upsampling. Default (None) enables regulated
            mode when upsampling for consistent timing (~5ms max latency). Set to
            False for zero latency with irregular timing.
        config: Optional OutputConfig. If provided and upsample_to_hz/rate_limit_hz
            are not set, values will be read from config.upsample_to_frequency_hz
            and config.rate_limit_frequency_hz.

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

    # Print session/QR with transport info so phone app knows how to connect
    # For USB, we use "wifi" transport in QR code for backward compatibility
    # (the protocol is identical - just UDP to an IP address)
    qr_transport = "wifi" if resolved_connection == "usb" else resolved_connection
    
    # For USB, we must explicitly pass the USB interface IP
    qr_wifi_ip = None
    if resolved_connection == "usb":
        from . import usb
        qr_wifi_ip = usb.get_usb_ip()
    
    print_session_qr(
        name=name,
        code=code,
        transport=qr_transport,
        wifi_port=wifi_port if resolved_connection in ("wifi", "usb") else None,
        wifi_ip=qr_wifi_ip,  # Pass USB IP when using USB
    )

    # Resolve resampling settings from config if not provided directly
    effective_upsample_hz = upsample_to_hz
    effective_rate_limit_hz = rate_limit_hz
    
    if config is not None:
        if effective_upsample_hz is None:
            effective_upsample_hz = getattr(config, 'upsample_to_frequency_hz', None)
        if effective_rate_limit_hz is None:
            effective_rate_limit_hz = getattr(config, 'rate_limit_frequency_hz', None)

    # Set up resampling if enabled
    effective_callback = callback
    resampler = None
    
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
        
        def feed_resampler(evt: Dict[str, Any]) -> None:
            resampler.feed(evt)
        
        effective_callback = feed_resampler
        
        if effective_upsample_hz:
            print(json.dumps({
                "type": "resampling_enabled",
                "upsample_to_hz": effective_upsample_hz,
                "rate_limit_hz": effective_rate_limit_hz,
                "regulated": effective_regulated,
            }), flush=True)

    try:
        if resolved_connection == "ble":
            _start_ble(name, code, effective_callback, quiet)
        elif resolved_connection == "wifi":
            _start_wifi(name, code, effective_callback, quiet, wifi_port)
        elif resolved_connection == "usb":
            _start_usb(name, code, effective_callback, quiet, wifi_port)
        else:
            raise RuntimeError(f"Unknown connection type: {resolved_connection}")
    except Exception as e:
        print(
            json.dumps({"type": "error", "message": f"Connection failed: {e}"}),
            flush=True,
        )
        raise
    finally:
        # Clean up resampler if it was created
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
) -> None:
    """Start BLE peripheral backend."""
    from . import ble

    ble.run_peripheral(name, code, callback, quiet)


def _start_wifi(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    port: int,
) -> None:
    """Start WIFI server backend."""
    from . import wifi

    wifi.run_server(name, code, callback, quiet, port)


def _start_usb(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    port: int,
) -> None:
    """Start USB tethering server backend."""
    from . import usb

    usb.run_server(name, code, callback, quiet, port)
