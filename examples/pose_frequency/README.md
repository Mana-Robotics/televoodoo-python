# Pose Frequency Example

Measure the time delta between incoming pose samples and save a plot.

## Dependencies

The core BLE dependencies are already specified in `requirements.txt` for platform-specific needs (`pyobjc` on macOS, BlueZ/dbus on Ubuntu). Ensure your environment satisfies those prerequisites.

Additionally `matplotlib` is required for plotting. Install it in your virtual environment:

```bash
# Activate your virtual environment first (if not already active)
source .venv/bin/activate

# Install matplotlib for this example
pip install matplotlib
```

## Usage

BLE input (default mode, macOS or Ubuntu; requires proper permissions and dependencies):

Capture 10 seconds of connection data:

```bash
python examples/pose_frequency/pose_frequency.py --duration 10
```

Simulated input (10 seconds):

```bash
python examples/pose_frequency/pose_frequency.py --sim --duration 10
```

By default, the plot is saved to this example directory with a timestamp, e.g. `pose_frequency_20260108_143025.png`.

Specify a custom output path (relative to the current working directory, NOT the example directory):

```bash
python examples/pose_frequency/pose_frequency.py --duration 10 --out my_plot.png
```


> ⚠️ If `--duration` is omitted and the script does not stop after the given duration: **Press Ctrl+C to stop** (graceful stop of CoreFoundation run loop on macOS). The result png will be saved on exiting.


