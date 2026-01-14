"""Connection management for Televoodoo.

This module provides the main entry point for starting Televoodoo with
different connection backends (BLE, WIFI, USB).

WiFi and USB use the same UDP server with mDNS discovery - the phone app
discovers the service via <name>._televoodoo._udp.local. regardless of
which network interface (WiFi or USB tethering) is being used.
"""

from __future__ import annotations

import json
import platform
from typing import Any, Callable, Dict, Literal, Optional, TYPE_CHECKING

from .session import generate_credentials, print_session_qr
from .udp_service import DEFAULT_PORT as UDP_DEFAULT_PORT

if TYPE_CHECKING:
    from .config import OutputConfig


ConnectionType = Literal["auto", "ble", "wifi", "usb"]


def _print_usb_setup_info() -> None:
    """Print USB setup requirements for iOS and Android."""
    print(json.dumps({
        "type": "usb_setup_info",
        "message": "USB connection requires different setup for iOS vs Android",
        "ios_setup": {
            "mac_internet_sharing": "ENABLED",
            "iphone_personal_hotspot": "DISABLED",
            "note": "Mac shares internet TO iPhone via USB",
        },
        "android_setup": {
            "mac_internet_sharing": "DISABLED",
            "android_usb_tethering": "ENABLED",
            "note": "Android shares internet TO Mac via USB",
        },
    }), flush=True)


def start_televoodoo(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    name: Optional[str] = None,
    code: Optional[str] = None,
    connection: ConnectionType = "auto",
    wifi_port: int = UDP_DEFAULT_PORT,
    upsample_to_hz: Optional[float] = None,
    rate_limit_hz: Optional[float] = None,
    regulated: Optional[bool] = None,
    config: Optional["OutputConfig"] = None,
) -> None:
    """Start Televoodoo and wait for phone app connection.

    Generates a session with QR code for the phone app to scan, then starts
    the connection backend and calls the callback for each teleoperation event.

    For WiFi and USB, the server uses mDNS to advertise on all network interfaces.
    The phone app discovers the service via mDNS - no IP address needed in QR code.

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

    # Print USB setup requirements if USB connection selected
    if resolved_connection == "usb":
        _print_usb_setup_info()

    # Print session/QR with transport info
    # Phone app uses mDNS to discover: <name>._televoodoo._udp.local.
    print_session_qr(
        name=name,
        code=code,
        transport=resolved_connection,
        wifi_port=wifi_port if resolved_connection in ("wifi", "usb") else None,
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
        elif resolved_connection in ("wifi", "usb"):
            # WiFi and USB use the same UDP server - mDNS advertises on all interfaces
            # The phone discovers via mDNS regardless of which interface it's on
            _start_udp_server(name, code, effective_callback, quiet, wifi_port)
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


def _start_udp_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]],
    quiet: bool,
    port: int,
) -> None:
    """Start UDP server backend.
    
    This server works for both WiFi and USB connections:
    - Binds to 0.0.0.0 (all interfaces)
    - Advertises via mDNS on all interfaces
    - Phone discovers via mDNS regardless of connection type
    """
    from . import udp_service

    udp_service.run_server(name, code, callback, quiet, port)
