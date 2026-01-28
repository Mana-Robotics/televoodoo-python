"""TCP service for Televoodoo pose streaming.

This module provides a transport-agnostic TCP server with UDP beacon discovery.
It works for both WiFi and USB connections.

Key features:
- TCP server with low-latency tuning (TCP_NODELAY)
- UDP broadcast beacons for discovery (no mDNS dependency)
- Length-prefix framing for TCP messages
- Single-client exclusive session
- Binds to 0.0.0.0 (all interfaces)

See Multi-transport-spec.md for the full protocol specification.
"""

from __future__ import annotations

import json
import platform
import select
import socket
import signal
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from . import protocol

# Default ports
DEFAULT_TCP_PORT = protocol.TCP_DATA_PORT  # 50000
DEFAULT_BEACON_PORT = protocol.UDP_BEACON_PORT  # 50001

# Beacon interval (500ms as per spec)
BEACON_INTERVAL = 0.5

# HELLO timeout (5 seconds as per spec)
HELLO_TIMEOUT = 5.0

# Module-level reference to active server (for send_haptic access from other threads)
_active_server: "Optional[TcpServer]" = None
_server_lock = threading.Lock()


@dataclass
class Session:
    """Active client session."""
    conn: socket.socket
    addr: Tuple[str, int]
    session_id: int
    authenticated: bool = False
    config: Dict[str, Any] = field(default_factory=dict)


def _get_local_ip() -> str:
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_all_broadcast_addresses() -> list:
    """Get broadcast addresses for all network interfaces.
    
    This ensures beacons reach devices on all interfaces including:
    - WiFi (en0)
    - USB Internet Sharing (bridge100 on macOS)
    - USB Tethering (usb0 on Linux)
    - Ethernet (en1, eth0)
    
    Returns:
        List of broadcast address strings (e.g., ["192.168.1.255", "192.168.2.255"])
    """
    import netifaces
    
    broadcast_addrs = []
    for iface in netifaces.interfaces():
        try:
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    broadcast = addr_info.get('broadcast')
                    if broadcast and broadcast not in broadcast_addrs:
                        broadcast_addrs.append(broadcast)
        except Exception:
            pass
    
    return broadcast_addrs


def _configure_socket_low_latency(sock: socket.socket) -> None:
    """Configure socket for low-latency operation.
    
    Applies TCP_NODELAY and other tuning options critical for real-time
    pose streaming with minimal latency.
    """
    # TCP_NODELAY is critical - disables Nagle's algorithm
    # Without this, small packets (like 46-byte POSE) are buffered up to 200ms
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    
    # Enable keepalive for connection state detection
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    # Platform-specific TCP keepalive tuning
    system = platform.system().lower()
    if system == "linux":
        # Linux: faster keepalive detection
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)   # Start probes after 5s idle
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)  # Probe every 1s
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)    # 3 failed probes = dead
        except (AttributeError, OSError):
            pass
        
        # TCP_QUICKACK for even lower latency (Linux only)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        except (AttributeError, OSError):
            pass
    elif system == "darwin":
        # macOS: TCP_KEEPALIVE is the idle time (equivalent to TCP_KEEPIDLE)
        try:
            TCP_KEEPALIVE = 0x10  # macOS-specific
            sock.setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, 5)
        except (AttributeError, OSError):
            pass
    
    # Smaller buffers for lower latency (less buffering delay)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32768)
    except OSError:
        pass


class TcpServer:
    """TCP server for Televoodoo pose streaming with UDP beacon discovery.
    
    This server is transport-agnostic - it works for both WiFi and USB
    connections. It binds to all interfaces (0.0.0.0) and broadcasts
    UDP beacons for discovery.
    """
    
    def __init__(
        self,
        name: str,
        code: str,
        tcp_port: int = DEFAULT_TCP_PORT,
        beacon_port: int = DEFAULT_BEACON_PORT,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        quiet: bool = False,
        initial_config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.code = code
        self.tcp_port = tcp_port
        self.beacon_port = beacon_port
        self.callback = callback
        self.quiet = quiet
        self.initial_config = initial_config or {}
        
        self.server_sock: Optional[socket.socket] = None
        self.beacon_sock: Optional[socket.socket] = None
        self.session: Optional[Session] = None
        self.running = False
        self.local_ip = _get_local_ip()
        
        self._beacon_thread: Optional[threading.Thread] = None
        self._recv_buffer = b""
    
    def _emit(self, event: Dict[str, Any]) -> None:
        """Emit event to callback and optionally print."""
        event_type = event.get("type", "")
        is_high_freq = event_type in ("pose", "heartbeat")
        
        if not self.quiet or not is_high_freq:
            print(json.dumps(event), flush=True)
        
        if self.callback:
            try:
                self.callback(event)
            except Exception:
                pass
    
    def _start_beacon_broadcast(self) -> None:
        """Start UDP beacon broadcast thread."""
        try:
            self.beacon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.beacon_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.beacon_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Get all broadcast addresses for logging
            broadcast_addrs = _get_all_broadcast_addresses()
            
            self._beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True)
            self._beacon_thread.start()
            
            self._emit({
                "type": "beacon_started",
                "name": self.name,
                "beacon_port": self.beacon_port,
                "tcp_port": self.tcp_port,
                "broadcast_addresses": broadcast_addrs + ["255.255.255.255"],
            })
        except Exception as e:
            self._emit({"type": "error", "message": f"Beacon start failed: {e}"})
    
    def _stop_beacon_broadcast(self) -> None:
        """Stop UDP beacon broadcast."""
        if self.beacon_sock:
            try:
                self.beacon_sock.close()
            except Exception:
                pass
            self.beacon_sock = None
    
    def _beacon_loop(self) -> None:
        """Broadcast discovery beacons at 2 Hz (every 500ms).
        
        Broadcasts on ALL network interfaces to support:
        - WiFi (primary interface)
        - USB Internet Sharing (bridge100 on macOS)
        - USB Tethering (usb0 on Linux)
        """
        beacon_data = protocol.pack_beacon(self.name, self.tcp_port)
        
        while self.running and self.beacon_sock:
            try:
                # Get all broadcast addresses for all interfaces
                broadcast_addrs = _get_all_broadcast_addresses()
                
                for addr in broadcast_addrs:
                    try:
                        self.beacon_sock.sendto(beacon_data, (addr, self.beacon_port))
                    except Exception:
                        pass
                
                # Also send to limited broadcast as fallback
                try:
                    self.beacon_sock.sendto(beacon_data, ("255.255.255.255", self.beacon_port))
                except Exception:
                    pass
                    
            except Exception:
                pass
            
            time.sleep(BEACON_INTERVAL)
    
    def _recv_exact(self, conn: socket.socket, n: int, timeout: float = None) -> Optional[bytes]:
        """Receive exactly n bytes from socket.
        
        Returns None if connection closed or timeout.
        """
        data = b""
        deadline = time.monotonic() + timeout if timeout else None
        
        while len(data) < n:
            if deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                conn.settimeout(remaining)
            
            try:
                chunk = conn.recv(n - len(data))
                if not chunk:
                    return None  # Connection closed
                data += chunk
            except socket.timeout:
                return None
            except (OSError, ConnectionError):
                return None
        
        return data
    
    def _read_message(self, conn: socket.socket, timeout: float = None) -> Optional[bytes]:
        """Read a length-prefixed message from the socket.
        
        Returns None if connection closed or timeout.
        """
        # Read 2-byte length prefix
        length_bytes = self._recv_exact(conn, 2, timeout)
        if not length_bytes:
            return None
        
        length = protocol.read_frame_length(length_bytes)
        if length == 0:
            return b""
        
        # Read payload
        return self._recv_exact(conn, length, timeout)
    
    def _send_message(self, conn: socket.socket, payload: bytes) -> bool:
        """Send a length-prefixed message to the socket.
        
        Returns True if sent successfully.
        """
        try:
            framed = protocol.frame_message(payload)
            conn.sendall(framed)
            return True
        except (OSError, ConnectionError):
            return False
    
    def _handle_hello(self, conn: socket.socket, addr: Tuple[str, int], data: bytes) -> bool:
        """Handle HELLO message from client.
        
        Returns True if authentication successful and session created.
        """
        hello = protocol.parse_hello(data)
        if not hello:
            return False
        
        # Check version
        if not protocol.is_version_supported(hello.version):
            self._send_message(conn, protocol.pack_ack(protocol.AckStatus.VERSION_MISMATCH))
            self._emit({
                "type": "session_rejected",
                "client": f"{addr[0]}:{addr[1]}",
                "reason": "version_mismatch",
                "client_version": hello.version,
            })
            return False
        
        # Check if session already active
        if self.session is not None:
            self._send_message(conn, protocol.pack_ack(protocol.AckStatus.BUSY))
            self._emit({
                "type": "session_rejected",
                "client": f"{addr[0]}:{addr[1]}",
                "reason": "busy",
            })
            return False
        
        # Validate auth code
        if hello.code != self.code:
            self._send_message(conn, protocol.pack_ack(protocol.AckStatus.BAD_CODE))
            self._emit({
                "type": "session_rejected",
                "client": f"{addr[0]}:{addr[1]}",
                "reason": "bad_code",
            })
            return False
        
        # Create new session
        self.session = Session(
            conn=conn,
            addr=addr,
            session_id=hello.session_id,
            authenticated=True,
            config=self.initial_config.copy(),
        )
        
        # Send ACK OK
        ack_payload = protocol.pack_ack(protocol.AckStatus.OK)
        ack_framed = protocol.frame_message(ack_payload)
        self._emit({
            "type": "debug_ack_sent",
            "ack_payload_hex": ack_payload.hex(),
            "ack_payload_len": len(ack_payload),
            "ack_framed_hex": ack_framed.hex(),
            "ack_framed_len": len(ack_framed),
        })
        self._send_message(conn, ack_payload)
        
        # Send initial CONFIG
        if self.session.config:
            config_payload = protocol.pack_config(self.session.config)
            self._emit({
                "type": "debug_config_sent",
                "config_payload_hex": config_payload.hex(),
                "config_payload_len": len(config_payload),
            })
            self._send_message(conn, config_payload)
        
        self._emit({
            "type": "connected",
            "client": f"{addr[0]}:{addr[1]}",
            "session_id": hello.session_id,
        })
        
        return True
    
    def _handle_pose(self, data: bytes) -> None:
        """Handle POSE message from client."""
        pose = protocol.parse_pose(data)
        if not pose:
            return
        
        # Emit pose event
        self._emit(protocol.pose_to_event(pose))
    
    def _handle_cmd(self, data: bytes) -> None:
        """Handle CMD message from client."""
        cmd = protocol.parse_cmd(data)
        if not cmd:
            return
        
        # Emit command event
        self._emit(protocol.cmd_to_event(cmd))
    
    def _handle_bye(self, data: bytes) -> bool:
        """Handle BYE message from client.
        
        Returns True if session should be closed.
        """
        if self.session is None:
            return False
        
        bye = protocol.parse_bye(data)
        if not bye:
            return False
        
        # Verify session ID matches
        if bye.session_id == self.session.session_id:
            return True
        
        return False
    
    def _handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        """Handle a client connection."""
        client_str = f"{addr[0]}:{addr[1]}"
        
        try:
            # Configure for low latency
            _configure_socket_low_latency(conn)
            
            # Wait for HELLO with timeout
            hello_data = self._read_message(conn, timeout=HELLO_TIMEOUT)
            if not hello_data:
                self._emit({
                    "type": "session_rejected",
                    "client": client_str,
                    "reason": "hello_timeout",
                })
                return
            
            # Validate HELLO
            header = protocol.parse_header(hello_data)
            if not header or not header.is_valid() or header.msg_type != protocol.MsgType.HELLO:
                self._emit({
                    "type": "session_rejected",
                    "client": client_str,
                    "reason": "invalid_hello",
                })
                return
            
            # Authenticate
            if not self._handle_hello(conn, addr, hello_data):
                return
            
            # Main receive loop
            conn.setblocking(False)
            
            while self.running and self.session is not None:
                # Use select for non-blocking receive with timeout
                try:
                    readable, _, _ = select.select([conn], [], [], 0.5)
                    if not readable:
                        continue
                except (ValueError, OSError):
                    break
                
                # Read message
                conn.setblocking(True)
                msg = self._read_message(conn, timeout=1.0)
                conn.setblocking(False)
                
                if msg is None:
                    # Connection closed
                    break
                
                if len(msg) < protocol.HEADER_SIZE:
                    continue
                
                # Parse header and route
                header = protocol.parse_header(msg)
                if not header or not header.is_valid():
                    continue
                
                if header.msg_type == protocol.MsgType.POSE:
                    self._handle_pose(msg)
                elif header.msg_type == protocol.MsgType.CMD:
                    self._handle_cmd(msg)
                elif header.msg_type == protocol.MsgType.BYE:
                    if self._handle_bye(msg):
                        break
        
        except Exception as e:
            self._emit({"type": "error", "message": f"Client handler error: {e}"})
        
        finally:
            # Clean up session
            if self.session is not None and self.session.conn is conn:
                self.session = None
                self._emit({
                    "type": "disconnected",
                    "client": client_str,
                    "reason": "connection_closed",
                })
            
            try:
                conn.close()
            except Exception:
                pass
    
    def send_haptic(self, intensity: float) -> bool:
        """Send haptic feedback to the connected phone.
        
        This method is thread-safe and can be called from any thread (e.g., a
        robot monitoring thread that reads force values).
        
        Args:
            intensity: Haptic intensity from 0.0 (off) to 1.0 (max).
                      Values are clamped to this range.
        
        Returns:
            True if the message was sent, False if no client is connected.
        """
        session = self.session
        if session is None or not session.authenticated:
            return False
        
        try:
            return self._send_message(session.conn, protocol.pack_haptic(intensity))
        except Exception:
            return False
    
    def send_config(self, config: Dict[str, Any]) -> bool:
        """Send configuration update to the connected phone.
        
        Args:
            config: Configuration dictionary to send
        
        Returns:
            True if the message was sent, False if no client is connected.
        """
        session = self.session
        if session is None or not session.authenticated:
            return False
        
        try:
            session.config.update(config)
            return self._send_message(session.conn, protocol.pack_config(session.config))
        except Exception:
            return False
    
    def start(self) -> None:
        """Start the TCP server."""
        global _active_server
        
        self._emit({
            "type": "server_starting",
            "name": self.name,
            "tcp_port": self.tcp_port,
            "beacon_port": self.beacon_port,
            "ip": self.local_ip,
        })
        
        # Register as active server for module-level send_haptic access
        with _server_lock:
            _active_server = self
        
        # Create TCP server socket
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("0.0.0.0", self.tcp_port))
        self.server_sock.listen(1)  # Single client
        self.server_sock.settimeout(1.0)  # Allow periodic check for shutdown
        
        self.running = True
        
        # Start beacon broadcast
        self._start_beacon_broadcast()
        
        self._emit({
            "type": "server_listening",
            "ip": self.local_ip,
            "tcp_port": self.tcp_port,
            "beacon_port": self.beacon_port,
            "code": self.code,
        })
        
        # Accept loop
        try:
            while self.running:
                try:
                    conn, addr = self.server_sock.accept()
                    self._emit({
                        "type": "connection_accepted",
                        "client": f"{addr[0]}:{addr[1]}",
                    })
                    
                    # Handle client (blocking - single client at a time)
                    self._handle_client(conn, addr)
                    
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        self._emit({"type": "error", "message": f"Accept error: {e}"})
        
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the TCP server."""
        global _active_server
        
        self.running = False
        
        # Unregister as active server
        with _server_lock:
            if _active_server is self:
                _active_server = None
        
        # Close session if active
        if self.session is not None:
            client_str = f"{self.session.addr[0]}:{self.session.addr[1]}"
            try:
                # Send BYE message to notify client before closing
                bye_payload = protocol.pack_bye(self.session.session_id)
                self._send_message(self.session.conn, bye_payload)
            except Exception:
                pass
            try:
                self.session.conn.close()
            except Exception:
                pass
            self.session = None
            self._emit({
                "type": "disconnected",
                "reason": "server_shutdown",
                "client": client_str,
            })
        
        # Stop beacon broadcast
        self._stop_beacon_broadcast()
        
        # Close server socket
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        
        self._emit({"type": "server_stopped"})


def run_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    tcp_port: int = DEFAULT_TCP_PORT,
    beacon_port: int = DEFAULT_BEACON_PORT,
    initial_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Run the Televoodoo TCP server.

    This starts a TCP server that the phone app can connect to
    over the local network. Works for both WiFi and USB connections.
    The phone discovers the server via UDP beacon broadcast.

    Args:
        name: Server name (for discovery/identification)
        code: Authentication code (phone must provide this in HELLO)
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging
        tcp_port: TCP port to listen on (default: 50000)
        beacon_port: UDP port for beacon broadcast (default: 50001)
        initial_config: Initial configuration to send to phone after auth

    Event format (same as BLE for compatibility):
    - {"type": "pose", "data": {"absolute_input": {...}}}
    - {"type": "command", "name": "...", "value": ...}
    - {"type": "connected", "client": "192.168.1.50:51234"}
    - {"type": "disconnected", "reason": "connection_closed"|"server_shutdown"}
    """
    server = TcpServer(
        name=name,
        code=code,
        tcp_port=tcp_port,
        beacon_port=beacon_port,
        callback=callback,
        quiet=quiet,
        initial_config=initial_config,
    )
    
    # Handle SIGINT/SIGTERM for graceful shutdown
    def handle_signal(signum, frame):
        server.stop()
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    server.start()


def get_server_url(tcp_port: int = DEFAULT_TCP_PORT) -> str:
    """Get the TCP endpoint info for the server.

    Args:
        tcp_port: Server port (default: 50000)

    Returns:
        TCP endpoint like "tcp://192.168.1.100:50000"
    """
    ip = _get_local_ip()
    return f"tcp://{ip}:{tcp_port}"


def send_haptic(value: float, min_value: float = 0.0, max_value: float = 1.0) -> bool:
    """Send haptic feedback to the connected phone.
    
    This function normalizes the input value to a 0.0-1.0 intensity range
    and sends it to the phone app, which generates haptic signals accordingly.
    
    This function is thread-safe and can be called from any thread, e.g.,
    from a robot monitoring loop that reads force sensor values.
    
    Args:
        value: The scalar value to send (e.g., force reading from robot).
        min_value: The minimum expected value (maps to intensity 0.0).
        max_value: The maximum expected value (maps to intensity 1.0).
    
    Returns:
        True if the message was sent successfully, False if no client
        is connected or if the server is not running.
    
    Example:
        >>> import threading
        >>> import time
        >>> from televoodoo import send_haptic
        >>> 
        >>> def force_monitor_loop():
        ...     '''Run in separate thread to monitor robot force values.'''
        ...     while True:
        ...         force = robot.get_force()  # e.g., 0-50 Newtons
        ...         send_haptic(force, min_value=0.0, max_value=50.0)
        ...         time.sleep(0.05)  # 20 Hz update
        >>> 
        >>> # Start monitoring thread before starting televoodoo
        >>> thread = threading.Thread(target=force_monitor_loop, daemon=True)
        >>> thread.start()
    """
    # Handle edge case where min == max
    if max_value == min_value:
        intensity = 0.5
    else:
        # Normalize value to 0.0-1.0 range
        intensity = (value - min_value) / (max_value - min_value)
        # Clamp to valid range
        intensity = max(0.0, min(1.0, intensity))
    
    # Get active TCP server (thread-safe)
    with _server_lock:
        server = _active_server
    
    if server is not None:
        return server.send_haptic(intensity)
    
    # Fallback to BLE haptic sender if available
    try:
        from . import ble
        return ble.send_haptic_ble(intensity)
    except Exception:
        return False


def send_config(config: Dict[str, Any]) -> bool:
    """Send configuration update to the connected phone.
    
    This function is thread-safe and can be called from any thread.
    
    Args:
        config: Configuration dictionary to send
    
    Returns:
        True if the message was sent successfully, False if no client
        is connected or if the server is not running.
    """
    with _server_lock:
        server = _active_server
    
    if server is not None:
        return server.send_config(config)
    
    return False


def stop_televoodoo() -> None:
    """Gracefully stop the Televoodoo server.
    
    This properly closes the connection and notifies the connected phone app
    that the session has ended. Use this instead of os._exit() for clean shutdown.
    
    This function is thread-safe and can be called from any thread.
    """
    with _server_lock:
        server = _active_server
    
    if server is not None:
        server.stop()
