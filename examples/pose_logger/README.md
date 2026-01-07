### Pose Logger example (using Televoodoo)

This example shows how to use `televoodoo` as a Python module from a downstream project. It subscribes to a pose stream and prints the transformed output JSON to stdout.

The script uses the built-in simulator for convenience. In your project, replace the simulator with your own source that calls the provided callback with `Pose` samples.

#### Install and run

Install the local package into your active venv (from the repo root):

```bash
pip install -e .
```

Then run the example (from the repo root, BLE peripheral mode by default):

```bash
python examples/pose_logger/pose_logger.py
```

For simulation mode (simulated input -> prints transformed JSON):

```bash
python examples/pose_logger/pose_logger.py --sim
```

Optionally provide a JSON config (same format saved by the app):

```bash
python examples/pose_logger/pose_logger.py --config examples/output_poller/voodoo_settings.json
```

Use static BLE credentials for testing or automation:

```bash
python examples/pose_logger/pose_logger.py --name mydevice --code ABC123
```

#### BLE peripheral mode (macOS)

Start a BLE peripheral that advertises the Voodoo Control service. This prints a session name and code, runs a service heartbeat, and blocks in the CoreBluetooth run loop. Requires macOS and `pyobjc` (already listed in `python/requirements.txt`). This is the default mode.

```bash
python examples/pose_logger/pose_logger.py
```

After starting, the program prints an ASCII QR code that encodes a JSON payload like `{"name":"prsntrXX","code":"ABC123"}` (see `SPECS/QR_CODE_READING_GUIDE.md`). Scan this to obtain the current peripheral name and access code.

You can then connect from a central and write pose JSON to the pose characteristic (UUID `1C8FD138-FC18-4846-954D-E509366AEF64`). The program logs BLE events and raw pose frames.

#### Simulation mode

For testing and development, you can use simulation mode which generates synthetic pose data:

```bash
python examples/pose_logger/pose_logger.py --sim
```

#### Program structure

- `Pose` (dataclass): input pose sample fields, matching the app spec (`SPECS/INPUT_POSE_DATA_FORMAT.md`).
- `OutputConfig`: configuration for which data to include and how to transform axes/scale.
- `PoseTransformer`: transforms each `Pose` into an output JSON object based on `OutputConfig`.

Minimal use in code:

```python
from televoodoo import Pose, OutputConfig, PoseTransformer

config = OutputConfig(
    includeFormats={
        "absolute_input": True,
        "delta_input": False,
        "absolute_transformed": True,
        "delta_transformed": False,
    },
    includeOrientation={
        "quaternion": True,
        "euler_radian": False,
        "euler_degree": False,
    },
    scale=1.0,
    outputAxes={"x": 1.0, "y": 1.0, "z": 1.0},
)

transformer = PoseTransformer(config)

def on_pose(pose: Pose) -> None:
    print(transformer.transform(pose))
```

#### OutputConfig fields

- `includeFormats`
  - `absolute_input` (bool): include raw input pose data in output JSON.
  - `delta_input` (bool): include delta of input position since first `pose_start`.
  - `absolute_transformed` (bool): include scaled/axis-adjusted absolute values.
  - `delta_transformed` (bool): include scaled/axis-adjusted deltas.

- `includeOrientation`
  - `quaternion` (bool): include quaternion fields (`qx`, `qy`, `qz`, `qw`).
  - `euler_radian` (bool): include Euler rotation fields in radians (`x_rot`, `y_rot`, `z_rot`).
  - `euler_degree` (bool): include Euler rotation fields in degrees.

- `scale` (number): global multiplier applied to positions (and deltas) after axis mapping.

- `outputAxes` (object): per-axis multiplier to re-orient or flip axes, e.g. `{ "x": 1, "y": -1, "z": 1 }` to invert Y.

Notes:
- Deltas are computed relative to the first pose where `pose.pose_start` is `True`.
- Euler values are passed through from input when enabled; if both `euler_radian` and `euler_degree` are true, both sets will be included if present in the input.

#### JSON config format

The app's Save/Load in `Data Output Settings` writes a JSON with the same shape expected here. Example:

```json
{
  "includeFormats": {
    "absolute_input": true,
    "delta_input": false,
    "absolute_transformed": true,
    "delta_transformed": false
  },
  "includeOrientation": {
    "quaternion": true,
    "euler_radian": false,
    "euler_degree": false
  },
  "scale": 1.0,
  "outputAxes": { "x": 1, "y": 1, "z": 1 },
  "selectedOutputMode": "absolute_transformed"
}
```

`selectedOutputMode` is used by the app's visualization only; it does not affect the JSON transformation logic.

#### Replacing the simulator

The simulation mode uses:

```python
from televoodoo.ble import run_simulation
run_simulation(on_pose)
```

In your project, forward your incoming pose samples to the same `on_pose` callback, constructing `Pose` instances with fields from `SPECS/INPUT_POSE_DATA_FORMAT.md`.


