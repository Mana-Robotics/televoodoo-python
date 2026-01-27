"""BLE peripheral implementation for macOS using CoreBluetooth."""

import json
import threading
import time
from typing import Any, Callable, Dict, Optional

import objc
from Foundation import NSObject, NSData, NSRunLoop

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

# Service and characteristic UUIDs (as per Multi-transport-spec.md)
SERVICE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF61"
CHAR_CONTROL_UUID = "1C8FD138-FC18-4846-954D-E509366AEF62"
CHAR_AUTH_UUID = "1C8FD138-FC18-4846-954D-E509366AEF63"
CHAR_POSE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF64"
CHAR_HEARTBEAT_UUID = "1C8FD138-FC18-4846-954D-E509366AEF65"
CHAR_COMMAND_UUID = "1C8FD138-FC18-4846-954D-E509366AEF66"
CHAR_HAPTIC_UUID = "1C8FD138-FC18-4846-954D-E509366AEF67"
CHAR_CONFIG_UUID = "1C8FD138-FC18-4846-954D-E509366AEF68"

# Heartbeat rate: 2 Hz for 3-second timeout detection
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
        self._haptic_char = None
        self._config_char = None
        self._cb = None
        self._haptic_sender_cb = None
        self._initial_config: Dict[str, Any] = {}
        self._current_config: bytes = b""
        return self

    def setup_(self, code, cb=None, haptic_sender_cb=None, initial_config=None):
        self.auth_code = code
        self._cb = cb
        self._haptic_sender_cb = haptic_sender_cb
        self._initial_config = initial_config or {}
        # Pre-pack the config for reads
        if self._initial_config:
            self._current_config = protocol.pack_config(self._initial_config)
        else:
            self._current_config = protocol.pack_config({})
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

    def peripheralManagerDidUpdateState_(self, peripheralManager):
        state = peripheralManager.state()
        if state == 5:  # PoweredOn
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

        # Haptic (Read + Notify)
        haptic_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_HAPTIC_UUID),
            CBCharacteristicPropertyRead | CBCharacteristicPropertyNotify,
            None,
            CBAttributePermissionsReadable,
        )
        self._haptic_char = haptic_char

        # Config (Read + Notify) - as per Multi-transport-spec.md
        config_char = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CBUUID.UUIDWithString_(CHAR_CONFIG_UUID),
            CBCharacteristicPropertyRead | CBCharacteristicPropertyNotify,
            None,
            CBAttributePermissionsReadable,
        )
        self._config_char = config_char

        service = CBMutableService.alloc().initWithType_primary_(
            CBUUID.UUIDWithString_(SERVICE_UUID), True
        )
        service.setCharacteristics_([
            ctrl_char, auth_char, pose_char, heartbeat_char, 
            cmd_char, haptic_char, config_char
        ])
        self.pm.addService_(service)

        # Start advertising
        self.pm.startAdvertising_({
            CBAdvertisementDataLocalNameKey: self._local_name(),
            CBAdvertisementDataServiceUUIDsKey: [CBUUID.UUIDWithString_(SERVICE_UUID)],
        })
        self.emitEvent_({"type": "ble_advertising", "name": self._local_name()})
        
        # Start heartbeat thread (2 Hz)
        self._start_time = time.monotonic()
        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_thread.start()

        # Register haptic sender with outer layer
        if self._haptic_sender_cb and self._haptic_char is not None:
            def _send_haptic(intensity: float) -> bool:
                try:
                    b = protocol.pack_haptic(intensity)
                    val = NSData.dataWithBytes_length_(b, len(b))
                    self.pm.updateValue_forCharacteristic_onSubscribedCentrals_(val, self._haptic_char, None)
                    return True
                except Exception:
                    return False

            try:
                self._haptic_sender_cb(_send_haptic)
            except Exception:
                pass

    def update_config(self, config: Dict[str, Any]) -> bool:
        """Update and notify config to connected centrals."""
        try:
            self._current_config = protocol.pack_config(config)
            if self._config_char is not None:
                val = NSData.dataWithBytes_length_(self._current_config, len(self._current_config))
                self.pm.updateValue_forCharacteristic_onSubscribedCentrals_(val, self._config_char, None)
            return True
        except Exception:
            return False

    def _hb_loop(self):
        """Heartbeat loop - 2 Hz with binary format."""
        while True:
            self.heartbeat_counter = (self.heartbeat_counter + 1) & 0xFFFFFFFF
            uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
            
            try:
                if self._hb_char is not None:
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
        """Handle binary pose data."""
        pose = protocol.parse_pose(data)
        if pose:
            self.emitEvent_(protocol.pose_to_event(pose))
        else:
            self.emitEvent_({"type": "error", "message": "Invalid POSE packet"})

    def _handle_command_write(self, data: bytes):
        """Handle binary command data."""
        cmd = protocol.parse_cmd(data)
        if cmd:
            self.emitEvent_(protocol.cmd_to_event(cmd))
        else:
            self.emitEvent_({"type": "error", "message": "Invalid CMD packet"})

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

    def peripheralManager_central_didSubscribeToCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            self.emitEvent_({"type": "ble_subscribe", "char": uuid})
            
            # Send initial config when client subscribes to config characteristic
            if uuid == CHAR_CONFIG_UUID and self._config_char is not None and self._current_config:
                val = NSData.dataWithBytes_length_(self._current_config, len(self._current_config))
                self.pm.updateValue_forCharacteristic_onSubscribedCentrals_(val, self._config_char, None)
        except Exception as e:
            self.emitEvent_({"type": "error", "message": str(e)})

    def peripheralManager_central_didUnsubscribeFromCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            self.emitEvent_({"type": "ble_unsubscribe", "char": uuid})
        except Exception:
            pass

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

    def peripheralManager_didReceiveReadRequest_(self, peripheral, request):
        uuid = request.characteristic().UUID().UUIDString()
        if uuid == CHAR_HEARTBEAT_UUID:
            uptime_ms = int((time.monotonic() - self._start_time) * 1000) & 0xFFFFFFFF
            b = protocol.pack_heartbeat(self.heartbeat_counter, uptime_ms)
            request.setValue_(NSData.dataWithBytes_length_(b, len(b)))
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)
            if not QUIET_HIGH_FREQUENCY:
                self.emitEvent_({"type": "heartbeat"})
        elif uuid == CHAR_CONFIG_UUID:
            request.setValue_(NSData.dataWithBytes_length_(self._current_config, len(self._current_config)))
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)
        else:
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)


def run_macos_peripheral(
    name: str, 
    expected_code: str, 
    callback: Optional[Callable[[Dict[str, Any]], None]] = None, 
    haptic_sender_cb: Optional[Callable[[Callable[[float], bool]], None]] = None,
    initial_config: Optional[Dict[str, Any]] = None,
):
    import signal
    
    delegate = PeripheralDelegate.alloc().init().setup_(
        expected_code, callback, haptic_sender_cb, initial_config
    )
    delegate.local_name = name
    
    def handle_sigterm(signum, frame):
        try:
            from PyObjCTools import AppHelper
            AppHelper.stopEventLoop()
        except Exception:
            pass
        raise SystemExit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    try:
        from PyObjCTools import AppHelper
        AppHelper.runConsoleEventLoop(installInterrupt=True)
    except Exception:
        NSRunLoop.mainRunLoop().run()
