# Contributing to Televoodoo Python

Thank you for your interest in contributing to Televoodoo Python! This document covers the technical internals and development setup for contributors.

## Development Setup

### Prerequisites

- Python 3.8+
- Platform-specific Bluetooth stack (see below)
- Git

### Clone and Install (Development Mode)

```bash
git clone https://github.com/Mana-Robotics/televoodoo-python.git
cd televoodoo-python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .  # Editable install
```

### Platform-Specific Requirements

#### macOS
- Uses PyObjC and Core Bluetooth
- Dependencies: `pyobjc-core`, `pyobjc-framework-Cocoa`, `pyobjc-framework-CoreBluetooth`
- Automatically installed via `requirements.txt`
- First run may require Bluetooth permission approval

#### Ubuntu/Linux
- Uses BlueZ via `bluezero` and D-Bus
- System packages required:
  ```bash
  sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev
  ```
- Ensure BlueZ is running: `sudo systemctl start bluetooth`
- May require `sudo` depending on BlueZ configuration

---

## Architecture Overview

```
televoodoo/
├── ble.py                    # Main entry point, start_peripheral()
├── ble_peripheral_macos.py   # macOS Core Bluetooth implementation
├── ble_peripheral_ubuntu.py  # Linux BlueZ implementation
├── pose.py                   # Pose class and utilities
└── transform.py              # Coordinate transformations
```

### Key Components

1. **BLE Peripheral** (`ble.py`): Platform dispatcher, creates the appropriate peripheral
2. **Platform Implementations**: Handle native Bluetooth APIs
3. **Pose Handling**: Parse incoming JSON, provide convenient Pose class
4. **Transforms**: Apply coordinate system transformations

---

## BLE Service Specification

Televoodoo Python creates a BLE peripheral with the following GATT service:

### Service UUID
```
1C8FD138-FC18-4846-954D-E509366AEF61
```

### Characteristics

| Characteristic | UUID | Properties | Purpose |
|---------------|------|------------|---------|
| Authentication | `...AEF63` | Write | Receives 6-char access code |
| Pose Data | `...AEF64` | Write | Receives JSON pose data |
| Heartbeat | `...AEF65` | Read | Connection health (UInt32 counter) |
| Commands | `...AEF66` | Write | Receives command JSON |

#### Full UUIDs
```
Authentication: 1C8FD138-FC18-4846-954D-E509366AEF63
Pose Data:      1C8FD138-FC18-4846-954D-E509366AEF64
Heartbeat:      1C8FD138-FC18-4846-954D-E509366AEF65
Commands:       1C8FD138-FC18-4846-954D-E509366AEF66
```

### Authentication Flow

1. Televoodoo App connects to BLE peripheral
2. App writes 6-character code to Authentication characteristic
3. Peripheral validates code
4. If valid: connection authenticated, pose streaming enabled
5. If invalid: connection rejected

### Pose Data Format

JSON payload written to Pose Data characteristic:

```json
{
  "movement_start": true,
  "x": 0.0, "y": 0.0, "z": 0.0,
  "x_rot": 0.0, "y_rot": 0.0, "z_rot": 0.0,
  "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0
}
```

### Command Format

JSON payload written to Commands characteristic:

```json
{"recording": true}           // Start recording
{"recording": false}          // Stop recording
{"keep_recording": true}      // Keep last recording
{"keep_recording": false}     // Discard last recording
```

---

## QR Code Format

The QR code contains connection credentials as JSON:

```json
{
  "name": "voodooXX",
  "code": "ABC123"
}
```

- **name**: BLE peripheral advertised name
- **code**: 6-character authentication code (A-Z, 0-9)

---

## Platform Implementation Details

### macOS (`ble_peripheral_macos.py`)

Uses PyObjC to wrap Core Bluetooth:
- `CBPeripheralManager` for peripheral role
- `CBMutableService` and `CBMutableCharacteristic` for GATT
- Run loop integration for async events

Key classes:
- `BLEPeripheralDelegate`: Handles CB delegate callbacks
- Characteristic write handlers dispatch to user callbacks

### Ubuntu (`ble_peripheral_ubuntu.py`)

Uses `bluezero` library over D-Bus:
- `Peripheral` class for BLE peripheral role
- `Characteristic` for GATT characteristics
- GLib main loop for async events

Key considerations:
- BlueZ version compatibility (5.50+)
- D-Bus permissions may require root

---

## Adding New Features

### Adding a New Characteristic

1. Define UUID (follow existing pattern: `...AEF6X`)
2. Add to platform implementations:
   - macOS: Create `CBMutableCharacteristic`, add to service
   - Ubuntu: Create `Characteristic`, add to application
3. Implement write/read handlers
4. Update documentation

### Adding Platform Support

1. Create `ble_peripheral_<platform>.py`
2. Implement `start_peripheral()` with same signature
3. Add platform detection in `ble.py`
4. Update `requirements.txt` if new dependencies
5. Add to documentation

---

## Testing

### Manual Testing

```bash
# Start peripheral with known credentials
televoodoo --name test123 --code TEST99

# Connect with Televoodoo App and verify:
# - QR code displays correctly
# - App can connect and authenticate
# - Pose data flows to callback
```

### Example Test Cases

1. **Connection**: App connects, authenticates successfully
2. **Auth failure**: Wrong code rejected, connection dropped
3. **Pose streaming**: Callback receives valid pose data
4. **Reconnection**: Static credentials allow reconnect
5. **Platform**: Test on both macOS and Ubuntu

---

## Code Style

- Follow PEP 8
- Use type hints where practical
- Document public APIs with docstrings
- Keep platform code isolated in platform-specific files

---

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commits
4. Test on at least one platform
5. Update documentation if needed
6. Submit PR with description of changes

---

## Security Notes

### Access Code Limitations

- **Not cryptographic**: Simple authentication to prevent accidental connections
- **No encryption**: BLE data is not encrypted by Televoodoo
- **Session-based**: Codes valid only while peripheral is running

### For Contributors

- Don't add features that could enable unauthorized access
- Consider security implications of new characteristics
- Document any security-relevant changes

---

## Resources

- [Core Bluetooth Programming Guide](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/)
- [BlueZ Documentation](http://www.bluez.org/documentation/)
- [bluezero Library](https://github.com/ukBaz/python-bluezero)
- [PyObjC Documentation](https://pyobjc.readthedocs.io/)

---

## Questions?

- File an issue on [GitHub](https://github.com/Mana-Robotics/televoodoo-python)
- Contact: [hello@mana-robotics.com](mailto:hello@mana-robotics.com)

---

Thank you for contributing! 🤖

