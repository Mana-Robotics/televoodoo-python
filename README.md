# Televoodoo Python module

**Televoodoo Python** enables your Python project to receive real-time **6DoF** pose data from any smartphone running the Televoodoo App — perfect for **Robot Teleoperation**, **3D object manipulation**, **VR motion control**, and more.


### The Televoodoo Ecosystem

- **[Televoodoo Python](https://github.com/Mana-Robotics/televoodoo-python)** (this project) — Create BLE peripherals for the Televoodoo App to connect to, with pose handling, coordinate transforms, and more
- **[Televoodoo App](mailto:hello@mana-robotics.com?subject=Televoodoo%20App%3A%20Request%20for%20Test%20Access)**
 (iOS, Android) — 6DoF tracking phone app that streams poses at low latency via BLE
- **[Televoodoo Viewer](https://github.com/Mana-Robotics/televoodoo-viewer)** — Cross-platform desktop app for visual testing and config file creation 

## Installation

### Option A: Installation using Python venv (tested)

From the `python/televoodoo/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .
```

Now `televoodoo` is importable in the venv and a console entry `televoodoo` is available.

### Option B: Installation using Conda

From the `python/televoodoo/` folder:

```bash
conda create -n televoodoo python=3.11 -y
conda activate televoodoo
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .
```

### General Notes on Installation:
- macOS pulls in PyObjC frameworks via `requirements.txt`.
- Ubuntu uses BlueZ via `bluezero`/`dbus`. If `dbus-python` fails to build, install system headers: `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev`.

## Usage

After either setup (conda or venv), simply source (activate) your python environment and then you can import `televoodoo` or run the `televoodoo` console entry.


Examples with corresponding usage instructions are available under `python/televoodoo/examples/`.


### BLE Credentials

By default, the BLE peripheral generates **random** credentials on each launch. Televoodoo also provides an option to set specify **static** credentials, which help in projects where you restart your python app and reconnect frequently:

```bash
# Using the console entry
televoodoo --name mydevice --code ABC123

# Or in examples
python examples/pose_logger/pose_logger.py --name mydevice --code ABC123
python examples/pose_recording/pose_recording.py --name mydevice --code ABC123
```

| Flag | Description |
|------|-------------|
| `--name` | Static BLE peripheral name (default: randomly generated `prsntrXX`) |
| `--code` | Static authentication code (default: randomly generated 6-char code) |

You can also use these programmatically:

```python
from televoodoo.ble import start_peripheral

# Use static credentials
start_peripheral(callback=my_handler, name="mydevice", code="ABC123")

# Or mix (e.g., static name, random code)
start_peripheral(callback=my_handler, name="mydevice")
```

## Maintainer

Developed with ❤️ for 🤖 by [Mana Robotics](https://www.mana-robotics.com).

## License

MIT License — see [LICENSE](LICENSE) for details.
