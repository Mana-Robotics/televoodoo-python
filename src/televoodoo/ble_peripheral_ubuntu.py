"""BLE peripheral implementation for Ubuntu using BlueZ (via bluezero)."""

import json
import threading
import time
from typing import Any, Callable, Dict, Optional
import os
import sys
import signal
import termios
import tty

from bluezero import adapter, peripheral  # type: ignore

from . import protocol

SERVICE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF61"
CHAR_CONTROL_UUID = "1C8FD138-FC18-4846-954D-E509366AEF62"
CHAR_AUTH_UUID = "1C8FD138-FC18-4846-954D-E509366AEF63"
CHAR_POSE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF64"
CHAR_HEARTBEAT_UUID = "1C8FD138-FC18-4846-954D-E509366AEF65"
CHAR_COMMAND_UUID = "1C8FD138-FC18-4846-954D-E509366AEF66"

# Heartbeat rate: 2 Hz for 3-second timeout detection
HEARTBEAT_INTERVAL = 0.5

_evt_cb: Optional[Callable[[Dict[str, Any]], None]] = None
QUIET_HIGH_FREQUENCY = False


def emit_event(evt: Dict[str, Any]) -> None:
    """Emit event to callback and optionally print."""
    kind = evt.get("type")
    if QUIET_HIGH_FREQUENCY and kind in {"pose", "heartbeat"}:
        pass
    else:
        print(json.dumps(evt), flush=True)
    
    cb = _evt_cb
    if cb is not None:
        try:
            cb(evt)
        except Exception:
            pass


class UbuntuPeripheral:
    def __init__(self, name: str, expected_code: str):
        self.name = name
        self.expected_code = expected_code
        self.heartbeat_counter = 0
        self._start_time = time.monotonic()
        self._hb_thread: Optional[threading.Thread] = None

        # Adapter
        adpts = list(adapter.Adapter.available())
        if not adpts:
            raise RuntimeError("No Bluetooth adapter found")
        first = adpts[0]
        addr = getattr(first, 'address', first)
        self.adapter = adapter.Adapter(addr)
        if not self.adapter.powered:
            emit_event({"type": "warn", "message": "Bluetooth adapter is off. Run 'bluetoothctl power on' and retry."})

        # Bluezero Peripheral
        self.ble = peripheral.Peripheral(self.adapter.address, local_name=self.name)

        # Create service and characteristics
        self.srv_id = 1
        self.hb_id = 1
        self.auth_id = 2
        self.ctrl_id = 3
        self.pose_id = 4
        self.cmd_id = 5

        self.ble.add_service(srv_id=self.srv_id, uuid=SERVICE_UUID, primary=True)

        # Heartbeat (read/notify)
        self.ble.add_characteristic(
            srv_id=self.srv_id,
            chr_id=self.hb_id,
            uuid=CHAR_HEARTBEAT_UUID,
            value=[],
            notifying=False,
            flags=['read', 'notify'],
            read_callback=self._hb_read,
            notify_callback=self._hb_notify,
        )

        # Auth (write)
        self.ble.add_characteristic(
            srv_id=self.srv_id,
            chr_id=self.auth_id,
            uuid=CHAR_AUTH_UUID,
            value=[],
            notifying=False,
            flags=['write', 'write-without-response'],
            write_callback=self._auth_write,
        )

        # Control (write)
        self.ble.add_characteristic(
            srv_id=self.srv_id,
            chr_id=self.ctrl_id,
            uuid=CHAR_CONTROL_UUID,
            value=[],
            notifying=False,
            flags=['write', 'write-without-response'],
            write_callback=self._control_write,
        )

        # Pose (write)
        self.ble.add_characteristic(
            srv_id=self.srv_id,
            chr_id=self.pose_id,
            uuid=CHAR_POSE_UUID,
            value=[],
            notifying=False,
            flags=['write', 'write-without-response'],
            write_callback=self._pose_write,
        )

        # Command (write)
        self.ble.add_characteristic(
            srv_id=self.srv_id,
            chr_id=self.cmd_id,
            uuid=CHAR_COMMAND_UUID,
            value=[],
            notifying=False,
            flags=['write', 'write-without-response'],
            write_callback=self._command_write,
        )

    def _hb_read(self) -> list[int]:
        """Handle heartbeat read - binary format."""
        uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
        b = protocol.pack_heartbeat(self.heartbeat_counter, uptime_ms)
        emit_event({"type": "heartbeat"})
        return list(b)

    def _hb_notify(self) -> list[int]:
        """Handle heartbeat notify - binary format."""
        uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
        b = protocol.pack_heartbeat(self.heartbeat_counter, uptime_ms)
        return list(b)

    def _auth_write(self, value: Any, options: Optional[Dict[str, Any]] = None) -> None:
        try:
            buf = bytes(value) if not isinstance(value, (bytes, bytearray)) else value
            code = buf.decode('utf-8')
            if code == self.expected_code:
                emit_event({"type": "ble_auth_ok"})
            else:
                emit_event({"type": "ble_auth_failed"})
        except Exception as e:
            emit_event({"type": "error", "message": f"auth write: {e}"})

    def _control_write(self, value: Any, options: Optional[Dict[str, Any]] = None) -> None:
        try:
            buf = bytes(value) if not isinstance(value, (bytes, bytearray)) else value
            cmd = buf.decode('utf-8')
            emit_event({"type": "ble_control", "cmd": cmd})
        except Exception as e:
            emit_event({"type": "error", "message": f"control write: {e}"})

    def _pose_write(self, value: Any, options: Optional[Dict[str, Any]] = None) -> None:
        """Handle binary pose data."""
        try:
            buf = bytes(value) if not isinstance(value, (bytes, bytearray)) else value
            pose = protocol.parse_pose(buf)
            if pose:
                emit_event(protocol.pose_to_event(pose))
            else:
                emit_event({"type": "error", "message": "Invalid POSE packet"})
        except Exception as e:
            emit_event({"type": "error", "message": f"pose write: {e}"})

    def _command_write(self, value: Any, options: Optional[Dict[str, Any]] = None) -> None:
        """Handle binary command data."""
        try:
            buf = bytes(value) if not isinstance(value, (bytes, bytearray)) else value
            cmd = protocol.parse_cmd(buf)
            if cmd:
                emit_event(protocol.cmd_to_event(cmd))
            else:
                emit_event({"type": "error", "message": "Invalid CMD packet"})
        except Exception as e:
            emit_event({"type": "error", "message": f"command write: {e}"})

    def _hb_loop(self) -> None:
        """Heartbeat loop - 2 Hz."""
        while True:
            try:
                self.heartbeat_counter = (self.heartbeat_counter + 1) & 0xFFFFFFFF
                try:
                    self.ble.send_notify(self.srv_id, self.hb_id)
                except Exception:
                    pass
                time.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                emit_event({"type": "error", "message": f"hb_loop: {e}"})

    def start(self) -> None:
        # Advertise and publish GATT
        self.ble.publish()
        emit_event({"type": "ble_advertising", "name": self.name})
        emit_event({"type": "ble_advertising_started"})
        
        # Start heartbeat thread (2 Hz)
        self._start_time = time.monotonic()
        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_thread.start()
        
        # Signal handlers
        def _handle_sig(_sig: int, _frm: Any) -> None:
            try:
                self.ble.quit()
            except Exception:
                pass
        
        try:
            signal.signal(signal.SIGINT, _handle_sig)
            signal.signal(signal.SIGTERM, _handle_sig)
        except Exception:
            pass
        
        # Ctrl+X watcher
        def _watch_ctrl_x() -> None:
            if not sys.stdin or not sys.stdin.isatty():
                return
            fd = sys.stdin.fileno()
            try:
                old = termios.tcgetattr(fd)
            except Exception:
                old = None
            try:
                try:
                    tty.setcbreak(fd)
                except Exception:
                    return
                while True:
                    try:
                        ch = sys.stdin.read(1)
                    except Exception:
                        break
                    if not ch:
                        break
                    if ch == '\x18':  # Ctrl+X
                        emit_event({"type": "shutdown", "reason": "ctrl_x"})
                        try:
                            self.ble.quit()
                        except Exception:
                            pass
                        break
            finally:
                if old is not None:
                    try:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    except Exception:
                        pass
        
        threading.Thread(target=_watch_ctrl_x, daemon=True).start()
        
        # Block on main loop
        try:
            self.ble.run()
        except KeyboardInterrupt:
            pass


def run_ubuntu_peripheral(name: str, expected_code: str, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
    global _evt_cb
    _evt_cb = callback
    
    # Ensure we connect to the real system bus
    addr = os.environ.get('DBUS_SYSTEM_BUS_ADDRESS', '')
    if not addr or 'miniforge' in addr or 'conda' in addr:
        os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/var/run/dbus/system_bus_socket'
    
    periph = UbuntuPeripheral(name, expected_code)
    periph.start()
