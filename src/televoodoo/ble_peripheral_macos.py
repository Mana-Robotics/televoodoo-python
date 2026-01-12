"""BLE peripheral implementation for macOS using CoreBluetooth.

Supports both v1 (JSON) and v2 (binary) protocols for backwards compatibility.
"""

import json
import struct
import threading
import time

import objc
from Foundation import NSObject, NSData, NSUUID, NSRunLoop

QUIET_HIGH_FREQUENCY = False

from CoreBluetooth import (
    CBPeripheralManager,
    CBMutableCharacteristic,
    CBMutableService,
    CBCharacteristicPropertyRead,
    CBCharacteristicPropertyNotify,
    CBCharacteristicPropertyWrite,
    CBCharacteristicPropertyWriteWithoutResponse,
    CBAttributePermissionsReadable,
    CBAttributePermissionsWriteable,
    CBUUID,
    CBATTErrorSuccess,
    CBAdvertisementDataLocalNameKey,
    CBAdvertisementDataServiceUUIDsKey,
)

from . import protocol

SERVICE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF61"
CHAR_CONTROL_UUID = "1C8FD138-FC18-4846-954D-E509366AEF62"
CHAR_AUTH_UUID = "1C8FD138-FC18-4846-954D-E509366AEF63"
CHAR_POSE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF64"
CHAR_HEARTBEAT_UUID = "1C8FD138-FC18-4846-954D-E509366AEF65"
CHAR_COMMAND_UUID = "1C8FD138-FC18-4846-954D-E509366AEF66"

# Heartbeat rate (v2 spec: 2 Hz for 3-second timeout detection)
HEARTBEAT_INTERVAL = 0.5


class PeripheralDelegate(NSObject):
    def init(self):
        self = objc.super(PeripheralDelegate, self).init()
        if self is None:
            return None
        self.pm = None
        self.auth_code = None
        self.local_name = "VoodooCtrl"
        self.authenticated_centrals = set()
        self.heartbeat_counter = 0
        self._start_time = time.monotonic()
        self._hb_thread = None
        self._hb_char = None
        self._cb = None  # optional callback to receive event dicts
        return self

    def setup_(self, code, cb=None):
        self.auth_code = code
        self._cb = cb
        self.pm = CBPeripheralManager.alloc().initWithDelegate_queue_options_(self, None, None)
        return self

    def emitEvent_(self, msg):
        """Emit event to callback and optionally print."""
        event_type = msg.get("type", "")
        is_high_freq = event_type in ("pose", "heartbeat")
        
        if not QUIET_HIGH_FREQUENCY or not is_high_freq:
            print(json.dumps(msg), flush=True)
        
        if self._cb:
            try:
                self._cb(msg)
            except Exception:
                pass

    # CBPeripheralManagerDelegate
    def peripheralManagerDidUpdateState_(self, peripheralManager):
        state = peripheralManager.state()
        # 5 is PoweredOn
        if state == 5:
            self._create_services()
        else:
            self.emitEvent_({"type": "ble_state", "state": int(state)})

    def _create_services(self):
        # Heartbeat characteristic (Read + Notify)
        heartbeat_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_HEARTBEAT_UUID),
            CBCharacteristicPropertyRead | CBCharacteristicPropertyNotify,
            None,
            CBAttributePermissionsReadable,
        )
        self._hb_char = heartbeat_char
        
        # Auth (Write/WriteWithoutResponse)
        auth_props = CBCharacteristicPropertyWrite | CBCharacteristicPropertyWriteWithoutResponse
        auth_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_AUTH_UUID),
            auth_props,
            None,
            CBAttributePermissionsWriteable,
        )
        
        # Control (Write)
        ctrl_props = CBCharacteristicPropertyWrite | CBCharacteristicPropertyWriteWithoutResponse
        ctrl_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_CONTROL_UUID),
            ctrl_props,
            None,
            CBAttributePermissionsWriteable,
        )
        
        # Pose (Write)
        pose_props = CBCharacteristicPropertyWrite | CBCharacteristicPropertyWriteWithoutResponse
        pose_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_POSE_UUID),
            pose_props,
            None,
            CBAttributePermissionsWriteable,
        )
        
        # Command (Write)
        cmd_props = CBCharacteristicPropertyWrite | CBCharacteristicPropertyWriteWithoutResponse
        cmd_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_COMMAND_UUID),
            cmd_props,
            None,
            CBAttributePermissionsWriteable,
        )

        service = CBMutableService.alloc().initWithType_primary_(
            CBUUID.UUIDWithString_(SERVICE_UUID), True
        )
        service.setCharacteristics_([ctrl_char, auth_char, pose_char, heartbeat_char, cmd_char])
        self.pm.addService_(service)

        # Start advertising
        self.pm.startAdvertising_({
            CBAdvertisementDataLocalNameKey: self._local_name(),
            CBAdvertisementDataServiceUUIDsKey: [CBUUID.UUIDWithString_(SERVICE_UUID)],
        })
        self.emitEvent_({"type": "ble_advertising", "name": self._local_name()})
        
        # Start heartbeat thread (v2: 2 Hz with binary format)
        self._start_time = time.monotonic()
        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_thread.start()

    def _hb_loop(self):
        """Heartbeat loop - v2 spec: 2 Hz with binary format."""
        while True:
            self.heartbeat_counter = (self.heartbeat_counter + 1) & 0xFFFFFFFF
            uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
            
            try:
                if self._hb_char is not None:
                    # v2 binary heartbeat format
                    b = protocol.pack_heartbeat(self.heartbeat_counter, uptime_ms)
                    val = NSData.dataWithBytes_length_(b, len(b))
                    self.pm.updateValue_forCharacteristic_onSubscribedCentrals_(val, self._hb_char, None)
            except Exception as e:
                if not QUIET_HIGH_FREQUENCY:
                    self.emitEvent_({"type": "error", "message": f"hb_notify: {e}"})
            
            time.sleep(HEARTBEAT_INTERVAL)

    def _local_name(self):
        return self.local_name

    def _handle_pose_write(self, data: bytes):
        """Handle pose data - supports both v1 (JSON) and v2 (binary)."""
        if protocol.is_binary_protocol(data):
            # v2 binary format
            pose = protocol.parse_pose(data)
            if pose:
                self.emitEvent_(protocol.pose_to_event(pose))
            else:
                self.emitEvent_({"type": "error", "message": "Invalid v2 POSE packet"})
        else:
            # v1 JSON format (backwards compatibility)
            try:
                js = data.decode("utf-8")
                raw = json.loads(js)
                self.emitEvent_({"type": "pose", "data": {"absolute_input": raw}})
            except Exception as e:
                self.emitEvent_({"type": "error", "message": f"pose json: {e}"})

    def _handle_command_write(self, data: bytes):
        """Handle command data - supports both v1 (JSON) and v2 (binary)."""
        if protocol.is_binary_protocol(data):
            # v2 binary format
            cmd = protocol.parse_cmd(data)
            if cmd:
                self.emitEvent_(protocol.cmd_to_event(cmd))
            else:
                self.emitEvent_({"type": "error", "message": "Invalid v2 CMD packet"})
        else:
            # v1 JSON format (backwards compatibility)
            try:
                js = data.decode("utf-8")
                cmd_data = json.loads(js)
                if "recording" in cmd_data:
                    self.emitEvent_({"type": "command", "name": "recording", "value": bool(cmd_data["recording"])})
                elif "keep_recording" in cmd_data:
                    self.emitEvent_({"type": "command", "name": "keep_recording", "value": bool(cmd_data["keep_recording"])})
                else:
                    self.emitEvent_({"type": "command", "data": cmd_data})
            except Exception as e:
                self.emitEvent_({"type": "error", "message": f"command json: {e}"})

    # Writes
    def peripheralManager_didReceiveWriteRequests_(self, peripheral, requests):
        for req in requests:
            uuid = req.characteristic().UUID().UUIDString()
            data: NSData = req.value()
            raw_bytes = bytes(data)
            
            try:
                if uuid == CHAR_AUTH_UUID:
                    code = raw_bytes.decode("utf-8")
                    if code == self.auth_code:
                        self.emitEvent_({"type": "ble_auth_ok"})
                    else:
                        self.emitEvent_({"type": "ble_auth_failed"})
                        
                elif uuid == CHAR_CONTROL_UUID:
                    cmd = raw_bytes.decode("utf-8")
                    self.emitEvent_({"type": "ble_control", "cmd": cmd})
                    
                elif uuid == CHAR_POSE_UUID:
                    self._handle_pose_write(raw_bytes)
                    
                elif uuid == CHAR_COMMAND_UUID:
                    self._handle_command_write(raw_bytes)
                    
            except Exception as e:
                self.emitEvent_({"type": "error", "message": str(e)})
                
        peripheral.respondToRequest_withResult_(requests[-1], CBATTErrorSuccess)

    # Subscriptions
    def peripheralManager_central_didSubscribeToCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            self.emitEvent_({"type": "ble_subscribe", "char": uuid})
        except Exception as e:
            self.emitEvent_({"type": "error", "message": str(e)})

    def peripheralManager_central_didUnsubscribeFromCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            self.emitEvent_({"type": "ble_unsubscribe", "char": uuid})
        except Exception:
            pass

    # Service add / advertising callbacks
    def peripheralManager_didAddService_error_(self, pm, service, error):
        msg = {"type": "ble_service_added", "uuid": service.UUID().UUIDString()}
        if error is not None:
            msg["error"] = str(error)
        self.emitEvent_(msg)

    def peripheralManagerDidStartAdvertising_error_(self, pm, error):
        msg = {"type": "ble_advertising_started"}
        if error is not None:
            msg["error"] = str(error)
        self.emitEvent_(msg)

    # Reads (heartbeat)
    def peripheralManager_didReceiveReadRequest_(self, peripheral, request):
        uuid = request.characteristic().UUID().UUIDString()
        if uuid == CHAR_HEARTBEAT_UUID:
            uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
            # v2 binary heartbeat format
            b = protocol.pack_heartbeat(self.heartbeat_counter, uptime_ms)
            request.setValue_(NSData.dataWithBytes_length_(b, len(b)))
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)
            if not QUIET_HIGH_FREQUENCY:
                self.emitEvent_({"type": "heartbeat"})
        else:
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)


def run_macos_peripheral(name: str, expected_code: str, callback=None):
    import signal
    
    delegate = PeripheralDelegate.alloc().init().setup_(expected_code, callback)
    delegate.local_name = name
    
    # Handle SIGTERM for graceful shutdown (sent by Tauri on app close)
    def handle_sigterm(signum, frame):
        try:
            from PyObjCTools import AppHelper
            AppHelper.stopEventLoop()
        except Exception:
            pass
        raise SystemExit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Prefer a console-friendly event loop that respects Ctrl+C; fallback to NSRunLoop
    try:
        from PyObjCTools import AppHelper  # type: ignore
        # installInterrupt=True makes Ctrl+C (SIGINT) stop the event loop
        AppHelper.runConsoleEventLoop(installInterrupt=True)
    except Exception:
        # Fallback if AppHelper is unavailable
        NSRunLoop.mainRunLoop().run()
