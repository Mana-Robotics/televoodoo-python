"""WIFI connection backend for Televoodoo.

This module provides a WiFi/UDP-based connection alternative to BLE.
The phone app connects over the local network via mDNS discovery.

Implements the WIFI_API_v2.md specification:
- mDNS service advertisement (_televoodoo._udp.local.)
- UDP binary protocol (same as BLE v2)
- Single-client exclusive session
- Bidirectional liveness detection (3-second timeout)
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
import signal
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from . import protocol

# Default UDP port for Televoodoo WIFI server
DEFAULT_PORT = 50000

# Session timeout (bidirectional liveness detection)
SESSION_TIMEOUT = 3.0

# Suppress high-frequency event logging when True
QUIET_HIGH_FREQUENCY = False

# mDNS service type
SERVICE_TYPE = "_televoodoo._udp.local."


@dataclass
class Session:
    """Active client session."""
    client_addr: Tuple[str, int]  # (ip, port)
    session_id: int
    last_seen_ts: float
    authenticated: bool = False


def _get_local_ip() -> str:
    """Get the local IP address for mDNS advertisement."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_hostname() -> str:
    """Get the local hostname."""
    try:
        return socket.gethostname().split('.')[0]
    except Exception:
        return "televoodoo"


class WlanServer:
    """UDP server for Televoodoo pose streaming with mDNS discovery."""
    
    def __init__(
        self,
        name: str,
        code: str,
        port: int = DEFAULT_PORT,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        quiet: bool = False,
    ):
        self.name = name
        self.code = code
        self.port = port
        self.callback = callback
        self.quiet = quiet
        
        self.sock: Optional[socket.socket] = None
        self.session: Optional[Session] = None
        self.running = False
        self.local_ip = _get_local_ip()
        self.hostname = _get_hostname()
        
        self._zeroconf = None
        self._service_info = None
        self._timeout_thread: Optional[threading.Thread] = None
    
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
    
    def _start_mdns(self) -> None:
        """Start mDNS service advertisement."""
        try:
            from zeroconf import Zeroconf, ServiceInfo
            
            self._zeroconf = Zeroconf()
            
            # Service instance name
            instance_name = f"{self.name} @ {self.hostname}"
            
            # TXT records
            properties = {
                "v": "1",
                "port": str(self.port),
                "name": self.name,
            }
            
            self._service_info = ServiceInfo(
                SERVICE_TYPE,
                f"{instance_name}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(self.local_ip)],
                port=self.port,
                properties=properties,
            )
            
            self._zeroconf.register_service(self._service_info)
            self._emit({
                "type": "mdns_registered",
                "service": f"{instance_name}.{SERVICE_TYPE}",
                "ip": self.local_ip,
                "port": self.port,
            })
            
        except ImportError:
            self._emit({
                "type": "warn",
                "message": "zeroconf not installed. mDNS discovery disabled. Install with: pip install zeroconf"
            })
        except Exception as e:
            self._emit({"type": "error", "message": f"mDNS registration failed: {e}"})
    
    def _stop_mdns(self) -> None:
        """Stop mDNS service advertisement."""
        try:
            if self._service_info and self._zeroconf:
                self._zeroconf.unregister_service(self._service_info)
            if self._zeroconf:
                self._zeroconf.close()
        except Exception:
            pass
        self._zeroconf = None
        self._service_info = None
    
    def _handle_hello(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle HELLO message from client."""
        hello = protocol.parse_hello(data)
        if not hello:
            return
        
        now = time.monotonic()
        
        # Check if session already active
        if self.session is not None:
            if self.session.client_addr == addr:
                # Same client - refresh session (keepalive)
                self.session.last_seen_ts = now
                # Send ACK OK
                self._send_ack(addr, protocol.AckStatus.OK)
            else:
                # Different client - reject with BUSY
                self._send_ack(addr, protocol.AckStatus.BUSY)
                self._emit({
                    "type": "wifi_rejected",
                    "client": f"{addr[0]}:{addr[1]}",
                    "reason": "busy",
                })
            return
        
        # New session - validate code
        if hello.code != self.code:
            self._send_ack(addr, protocol.AckStatus.BAD_CODE)
            self._emit({
                "type": "wifi_rejected",
                "client": f"{addr[0]}:{addr[1]}",
                "reason": "bad_code",
            })
            return
        
        # Create new session
        self.session = Session(
            client_addr=addr,
            session_id=hello.session_id,
            last_seen_ts=now,
            authenticated=True,
        )
        
        self._send_ack(addr, protocol.AckStatus.OK)
        self._emit({
            "type": "wifi_connected",
            "client": f"{addr[0]}:{addr[1]}",
        })
    
    def _handle_pose(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle POSE message from client."""
        if self.session is None or self.session.client_addr != addr:
            return  # Ignore if not from active client
        
        pose = protocol.parse_pose(data)
        if not pose:
            return
        
        # Refresh session liveness
        self.session.last_seen_ts = time.monotonic()
        
        # Emit pose event
        self._emit(protocol.pose_to_event(pose))
    
    def _handle_cmd(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle CMD message from client."""
        if self.session is None or self.session.client_addr != addr:
            return
        
        cmd = protocol.parse_cmd(data)
        if not cmd:
            return
        
        # Refresh session liveness
        self.session.last_seen_ts = time.monotonic()
        
        # Emit command event
        self._emit(protocol.cmd_to_event(cmd))
    
    def _handle_bye(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle BYE message from client."""
        if self.session is None or self.session.client_addr != addr:
            return
        
        bye = protocol.parse_bye(data)
        if not bye:
            return
        
        # Verify session ID matches
        if bye.session_id == self.session.session_id:
            client_str = f"{self.session.client_addr[0]}:{self.session.client_addr[1]}"
            self.session = None
            self._emit({
                "type": "wifi_disconnected",
                "reason": "bye",
                "client": client_str,
            })
    
    def _send_ack(self, addr: Tuple[str, int], status: protocol.AckStatus) -> None:
        """Send ACK message to client."""
        if self.sock:
            try:
                ack_data = protocol.pack_ack(status)
                self.sock.sendto(ack_data, addr)
            except Exception:
                pass
    
    def _check_session_timeout(self) -> None:
        """Background thread to check session timeout."""
        while self.running:
            if self.session is not None:
                elapsed = time.monotonic() - self.session.last_seen_ts
                if elapsed > SESSION_TIMEOUT:
                    client_str = f"{self.session.client_addr[0]}:{self.session.client_addr[1]}"
                    self.session = None
                    self._emit({
                        "type": "wifi_disconnected",
                        "reason": "timeout",
                        "client": client_str,
                    })
            time.sleep(0.5)
    
    def _recv_loop(self) -> None:
        """Main receive loop for UDP packets."""
        while self.running:
            try:
                # Use select for timeout to allow clean shutdown
                self.sock.settimeout(0.5)
                try:
                    data, addr = self.sock.recvfrom(1024)
                except socket.timeout:
                    continue
                
                if len(data) < protocol.HEADER_SIZE:
                    continue
                
                # Parse header
                header = protocol.parse_header(data)
                if header is None or not header.is_valid():
                    continue
                
                # Route by message type
                if header.msg_type == protocol.MsgType.HELLO:
                    self._handle_hello(data, addr)
                elif header.msg_type == protocol.MsgType.POSE:
                    self._handle_pose(data, addr)
                elif header.msg_type == protocol.MsgType.CMD:
                    self._handle_cmd(data, addr)
                elif header.msg_type == protocol.MsgType.BYE:
                    self._handle_bye(data, addr)
                    
            except Exception as e:
                if self.running:
                    self._emit({"type": "error", "message": f"recv error: {e}"})
    
    def start(self) -> None:
        """Start the WIFI server."""
        self._emit({
            "type": "wifi_starting",
            "name": self.name,
            "port": self.port,
            "ip": self.local_ip,
        })
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        
        self.running = True
        
        # Start mDNS advertisement
        self._start_mdns()
        
        # Start timeout checker thread
        self._timeout_thread = threading.Thread(target=self._check_session_timeout, daemon=True)
        self._timeout_thread.start()
        
        self._emit({
            "type": "wifi_listening",
            "ip": self.local_ip,
            "port": self.port,
            "code": self.code,
        })
        
        # Run receive loop (blocking)
        try:
            self._recv_loop()
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the WIFI server."""
        self.running = False
        
        # Close session if active
        if self.session is not None:
            client_str = f"{self.session.client_addr[0]}:{self.session.client_addr[1]}"
            self.session = None
            self._emit({
                "type": "wifi_disconnected",
                "reason": "server_shutdown",
                "client": client_str,
            })
        
        # Stop mDNS
        self._stop_mdns()
        
        # Close socket
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        
        self._emit({"type": "wifi_stopped"})


def run_server(
    name: str,
    code: str,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    quiet: bool = False,
    port: int = DEFAULT_PORT,
) -> None:
    """Run the Televoodoo WIFI server.

    This starts a UDP server that the phone app can connect to
    over the local network. The phone and computer must be on the same
    WiFi network.

    Args:
        name: Server name (for mDNS discovery/identification)
        code: Authentication code (phone must provide this in HELLO)
        callback: Function called for each event (pose, connection status, etc.)
        quiet: Suppress high-frequency logging
        port: UDP port to listen on (default: 50000)

    Event format (same as BLE for compatibility):
    - {"type": "pose", "data": {"absolute_input": {...}}}
    - {"type": "command", "name": "...", "value": ...}
    - {"type": "wifi_connected", "client": "192.168.1.50:51234"}
    - {"type": "wifi_disconnected", "reason": "timeout"|"bye"|"server_shutdown"}
    """
    server = WlanServer(
        name=name,
        code=code,
        port=port,
        callback=callback,
        quiet=quiet,
    )
    
    # Handle SIGINT/SIGTERM for graceful shutdown
    def handle_signal(signum, frame):
        server.stop()
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    server.start()


def get_server_url(port: int = DEFAULT_PORT) -> str:
    """Get the UDP endpoint info for the WIFI server.

    Args:
        port: Server port (default: 50000)

    Returns:
        UDP endpoint like "udp://192.168.1.100:50000"
    """
    ip = _get_local_ip()
    return f"udp://{ip}:{port}"
