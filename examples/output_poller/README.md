### Output Poller example (using Televoodoo)

This example starts the BLE peripheral (macOS or Ubuntu) and periodically prints the transformed output JSON at a fixed rate.

The peripheral session (name + access code) and an ASCII QR code are printed automatically via `televoodoo.start_peripheral()`.

#### Install and run

From the `python/` folder, install the package into your venv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Then run the example (from the `python/` folder):

```bash
python examples/output_poller/output_poller.py --config examples/output_poller/voodoo_settings.json --hz 1
```

#### Arguments

- `--config <path>`: Path to a Voodoo Control output-config JSON (two samples are included: `examples/output_poller/voodoo_settings.json`, `examples/output_poller/voodoo_settings2.json`).
- `--hz <number>`: Polling frequency in Hz (default: 5). The script prints `{ "polled_output": ... }` at this rate.

#### Notes

- The BLE session JSON and QR are printed automatically when the peripheral starts.
- Exit with Ctrl+C in the terminal.
- Platform support:
  - macOS uses CoreBluetooth.
  - Ubuntu uses BlueZ (via Bluezero); ensure Bluetooth is powered (`bluetoothctl power on`). Some systems may require bluetoothd with `--experimental` for GATT peripheral support.
- Dependencies for Linux are already declared (`dbus-next`, `dbus-python`, `bluezero`). If `dbus-python` fails to build, install system headers: `sudo apt-get install libdbus-1-dev libglib2.0-dev python3-dev`.
