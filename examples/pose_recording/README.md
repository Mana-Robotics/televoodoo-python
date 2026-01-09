### Pose Recording Example (using Televoodoo)

This example demonstrates how to use `televoodoo` to record poses based on BLE commands. It subscribes to both pose and command streams, allowing remote control of recording sessions.

#### Features

- **Pose Logging**: All incoming poses are logged to stdout with their transformed values
- **Recording Control**: Start/stop recording via BLE command characteristic
- **Recording Persistence**: Save or discard recordings via BLE command characteristic
- **Timestamped Output**: Each recorded pose includes an ISO timestamp
- **Session-based Filenames**: Output files are named using the session name and recording start time

#### Install and Run

Install the local package into your active venv (from the `python/televoodoo` directory):

```bash
pip install -e .
```

Then run the example (BLE peripheral mode by default):

```bash
python examples/pose_recording/pose_recording.py
```

With custom output directory:

```bash
python examples/pose_recording/pose_recording.py --output-dir ./recordings
```

With a JSON config for pose transformation:

```bash
python examples/pose_recording/pose_recording.py --config examples/output_poller/voodoo_settings.json
```

Use static BLE credentials for testing or automation:

```bash
python examples/pose_recording/pose_recording.py --name mydevice --code ABC123
```

#### BLE Peripheral Mode (macOS/Ubuntu)

Start a BLE peripheral that advertises the Voodoo Control service. The program will:

1. Print a session name and QR code for connection
2. Listen for pose data on the pose characteristic
3. Listen for commands on the command characteristic
4. Log all poses to stdout
5. Record poses when commanded

```bash
python examples/pose_recording/pose_recording.py --output-dir ./recordings
```

#### Simulation Mode

For testing without BLE hardware, use simulation mode. This generates synthetic poses and demonstrates the recording flow automatically:

```bash
python examples/pose_recording/pose_recording.py --sim --duration 30
```

In simulation mode, the demo will:
- Generate poses continuously
- Auto-start recording after 10 poses
- Auto-stop recording after 20 poses
- Auto-save the recording after 25 poses

#### BLE Command API

Send commands to the Command Data Characteristic (UUID: `1C8FD138-FC18-4846-954D-E509366AEF66`):

| Command | Payload | Description |
|---------|---------|-------------|
| Start Recording | `{"recording":true}` | Begin capturing poses |
| Stop Recording | `{"recording":false}` | Stop capturing poses |
| Keep Recording | `{"keep_recording":true}` | Save recorded poses to file |
| Discard Recording | `{"keep_recording":false}` | Discard recorded poses |

#### Recording Workflow

1. **Connect** to the BLE peripheral and authenticate
2. **Send poses** to the pose characteristic - all are logged
3. **Start recording**: Send `{"recording":true}` to command characteristic
4. **Continue sending poses** - these are now being recorded
5. **Stop recording**: Send `{"recording":false}` to command characteristic
6. **Keep or discard**:
   - Send `{"keep_recording":true}` to save to file
   - Send `{"keep_recording":false}` to discard

#### Output File Format

Saved recordings are stored as JSON files with the following structure:

```json
{
  "session_name": "voodooXY",
  "recording_start": "2025-01-07T14:30:00.123456",
  "recording_end": "2025-01-07T14:31:30.654321",
  "pose_count": 450,
  "poses": [
    {
      "timestamp": "2025-01-07T14:30:00.150000",
      "pose": {
        "absolute_input": {
          "movement_start": true,
          "x": 0.1,
          "y": 0.2,
          "z": 0.05,
          ...
        },
        "absolute_transformed": {
          ...
        }
      }
    },
    ...
  ]
}
```

#### Output Filename Format

Files are named using the pattern: `{session_name}_{YYYYMMDD_HHMMSS}.json`

Example: `voodooXY_20250107_143000.json`

#### Console Output Events

The program emits JSON events to stdout:

| Event Type | Description |
|------------|-------------|
| `pose_logged` | A pose was received and logged (includes recording status) |
| `recording_started` | Recording has begun |
| `recording_stopped` | Recording has stopped (includes pose count) |
| `recording_saved` | Recording was saved to file (includes filename) |
| `recording_discarded` | Recording was discarded |

Example console output:

```json
{"type": "recording_started", "time": "2025-01-07T14:30:00.123456"}
{"type": "pose_logged", "recording": true, "recorded_count": 1, "pose": {...}}
{"type": "pose_logged", "recording": true, "recorded_count": 2, "pose": {...}}
{"type": "recording_stopped", "pose_count": 450}
{"type": "recording_saved", "filename": "./recordings/voodooXY_20250107_143000.json", "pose_count": 450}
```

#### Command-Line Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to JSON OutputConfig for pose transformation |
| `--output-dir DIR` | Directory to save recordings (default: current directory) |
| `--sim` | Use simulation mode instead of BLE |
| `--duration N` | Auto-exit after N seconds |
| `--name NAME` | Static BLE peripheral name (default: randomly generated) |
| `--code CODE` | Static authentication code (default: randomly generated) |

#### Integration Example

```python
from televoodoo import Pose, PoseProvider, load_config
from pose_recording import PoseRecorder

# Create pose provider and recorder
cfg = load_config("config.json")
pose_provider = PoseProvider(cfg)
recorder = PoseRecorder(pose_provider, output_dir="./recordings")

# Set session name
recorder.set_session_name("my_session")

# Handle incoming pose
def on_pose(pose: Pose):
    out = recorder.handle_pose(pose)
    print(out)

# Handle commands
def on_command(name: str, value: bool):
    if name == "recording":
        if value:
            recorder.start_recording()
        else:
            recorder.stop_recording()
    elif name == "keep_recording":
        recorder.keep_recording(value)
```

