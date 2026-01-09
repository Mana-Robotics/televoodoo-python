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


SERVICE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF61"
CHAR_CONTROL_UUID = "1C8FD138-FC18-4846-954D-E509366AEF62"
CHAR_AUTH_UUID = "1C8FD138-FC18-4846-954D-E509366AEF63"
CHAR_POSE_UUID = "1C8FD138-FC18-4846-954D-E509366AEF64"
CHAR_HEARTBEAT_UUID = "1C8FD138-FC18-4846-954D-E509366AEF65"
CHAR_COMMAND_UUID = "1C8FD138-FC18-4846-954D-E509366AEF66"


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
        self._hb_thread = None
        self._hb_char = None
        self._cb = None  # optional callback to receive event dicts
        return self

    def setup_(self, code, cb=None):
        self.auth_code = code
        self._cb = cb
        self.pm = CBPeripheralManager.alloc().initWithDelegate_queue_options_(self, None, None)
        return self

    # CBPeripheralManagerDelegate
    def peripheralManagerDidUpdateState_(self, peripheralManager):
        state = peripheralManager.state()
        # 5 is PoweredOn
        if state == 5:
            self._create_services()
        else:
            msg = {"type": "ble_state", "state": int(state)}
            print(json.dumps(msg), flush=True)
            if self._cb:
                try:
                    self._cb(msg)
                except Exception:
                    pass

    def _create_services(self):
        # Heartbeat characteristic (Read)
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
        msg = {"type": "ble_advertising", "name": self._local_name()}
        print(json.dumps(msg), flush=True)
        if self._cb:
            try:
                self._cb(msg)
            except Exception:
                pass
        
        # start heartbeat counting
        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_thread.start()

    def _hb_loop(self):
        while True:
            self.heartbeat_counter = (self.heartbeat_counter + 1) & 0xFFFFFFFF
            # push notify to subscribed centrals
            try:
                if self._hb_char is not None:
                    b = struct.pack('<I', self.heartbeat_counter)
                    val = NSData.dataWithBytes_length_(b, len(b))
                    self.pm.updateValue_forCharacteristic_onSubscribedCentrals_(val, self._hb_char, None)
            except Exception as e:
                if not QUIET_HIGH_FREQUENCY:
                    msg = {"type": "error", "message": f"hb_notify: {e}"}
                    print(json.dumps(msg), flush=True)
                    if self._cb:
                        try:
                            self._cb(msg)
                        except Exception:
                            pass
            time.sleep(1.0)

    def _local_name(self):
        # name from session
        return self.local_name

    # Writes
    def peripheralManager_didReceiveWriteRequests_(self, peripheral, requests):
        for req in requests:
            uuid = req.characteristic().UUID().UUIDString()
            data: NSData = req.value()
            try:
                if uuid == CHAR_AUTH_UUID:
                    code = bytes(data).decode("utf-8")
                    if code == self.auth_code:
                        msg = {"type": "ble_auth_ok"}
                        print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
                    else:
                        msg = {"type": "ble_auth_failed"}
                        print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
                elif uuid == CHAR_CONTROL_UUID:
                    cmd = bytes(data).decode("utf-8")
                    msg = {"type": "ble_control", "cmd": cmd}
                    print(json.dumps(msg), flush=True)
                    if self._cb:
                        try:
                            self._cb(msg)
                        except Exception:
                            pass
                elif uuid == CHAR_POSE_UUID:
                    js = bytes(data).decode("utf-8")
                    # Forward raw input under absolute_input for frontend; keep heartbeat marker
                    try:
                        raw = json.loads(js)
                        msg = {"type": "pose", "data": {"absolute_input": raw}}
                        if not QUIET_HIGH_FREQUENCY:
                            print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
                    except Exception as e:
                        msg = {"type": "error", "message": f"pose json: {e}"}
                        print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
                elif uuid == CHAR_COMMAND_UUID:
                    js = bytes(data).decode("utf-8")
                    try:
                        cmd_data = json.loads(js)
                        # Handle supported commands: recording, keep_recording
                        if "recording" in cmd_data:
                            msg = {"type": "command", "name": "recording", "value": bool(cmd_data["recording"])}
                        elif "keep_recording" in cmd_data:
                            msg = {"type": "command", "name": "keep_recording", "value": bool(cmd_data["keep_recording"])}
                        else:
                            msg = {"type": "command", "data": cmd_data}
                        print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
                    except Exception as e:
                        msg = {"type": "error", "message": f"command json: {e}"}
                        print(json.dumps(msg), flush=True)
                        if self._cb:
                            try:
                                self._cb(msg)
                            except Exception:
                                pass
            except Exception as e:
                msg = {"type": "error", "message": str(e)}
                print(json.dumps(msg), flush=True)
                if self._cb:
                    try:
                        self._cb(msg)
                    except Exception:
                        pass
        peripheral.respondToRequest_withResult_(requests[-1], CBATTErrorSuccess)

    # Subscriptions (notifies when a central subscribes to a notifying characteristic; we log anyway)
    def peripheralManager_central_didSubscribeToCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            msg = {"type": "ble_subscribe", "char": uuid}
            print(json.dumps(msg), flush=True)
            if self._cb:
                try:
                    self._cb(msg)
                except Exception:
                    pass
        except Exception as e:
            msg = {"type": "error", "message": str(e)}
            print(json.dumps(msg), flush=True)
            if self._cb:
                try:
                    self._cb(msg)
                except Exception:
                    pass

    def peripheralManager_central_didUnsubscribeFromCharacteristic_(self, pm, central, characteristic):
        try:
            uuid = characteristic.UUID().UUIDString()
            print(json.dumps({"type": "ble_unsubscribe", "char": uuid}), flush=True)
        except Exception as e:
            print(json.dumps({"type": "error", "message": str(e)}), flush=True)

    # Service add / advertising callbacks
    def peripheralManager_didAddService_error_(self, pm, service, error):
        msg = {"type": "ble_service_added", "uuid": service.UUID().UUIDString()}
        if error is not None:
            msg["error"] = str(error)
        print(json.dumps(msg), flush=True)
        if self._cb:
            try:
                self._cb(msg)
            except Exception:
                pass

    def peripheralManagerDidStartAdvertising_error_(self, pm, error):
        msg = {"type": "ble_advertising_started"}
        if error is not None:
            msg["error"] = str(error)
        print(json.dumps(msg), flush=True)
        if self._cb:
            try:
                self._cb(msg)
            except Exception:
                pass

    # Reads (heartbeat)
    def peripheralManager_didReceiveReadRequest_(self, peripheral, request):
        uuid = request.characteristic().UUID().UUIDString()
        if uuid == CHAR_HEARTBEAT_UUID:
            b = struct.pack('<I', self.heartbeat_counter)
            request.setValue_(NSData.dataWithBytes_length_(b, len(b)))
            peripheral.respondToRequest_withResult_(request, CBATTErrorSuccess)
            if not QUIET_HIGH_FREQUENCY:
                msg = {"type": "heartbeat"}
                print(json.dumps(msg), flush=True)
                if self._cb:
                    try:
                        self._cb(msg)
                    except Exception:
                        pass
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


