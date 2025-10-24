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

Capture 10 seconds of connection data and save results to `pose_frequency.png`

```bash
python examples/pose_frequency/pose_frequency.py --duration 10 --out pose_frequency.png
```

Simulated input (10 seconds) and save to `pose_frequency.png`:

```bash
python examples/pose_frequency/pose_frequency.py --sim --duration 10 --out pose_frequency.png
```

If `--duration` is omitted:
- BLE (default): Ctrl+C to stop (graceful stop of CoreFoundation run loop on macOS)
- sim: Ctrl+C to stop

The resulting `pose_frequency.png` is stored in the current working directory.


