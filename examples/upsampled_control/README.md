# Upsampled Control Example

This example demonstrates high-frequency robot control using upsampling to convert phone poses (30-60 Hz) to a higher target frequency (e.g., 200 Hz).

## Why Upsample?

Robot arm controllers often require higher frequency control inputs (100-200 Hz) than the phone can provide:
- **WiFi**: ~60 Hz consistent
- **BLE**: ~30 Hz (due to connection interval batching)

Televoodoo uses **linear extrapolation** to predict poses between real samples, ensuring your robot receives smooth, high-frequency input.

## Key Features

- **Consistent timing** (regulated mode, default): Outputs at fixed intervals for reliable robot control
- **Forward-looking extrapolation**: Predicts where the pose will be based on velocity
- **Safety limit**: Extrapolation stops if no new pose arrives within expected interval (prevents runaway motion if phone disconnects)
- **~5ms max latency** at 200 Hz (one tick) for timing consistency

## Usage

Run from the `televoodoo/` directory:

```bash
# Default 200 Hz upsampling (WiFi)
python examples/upsampled_control/upsampled_control.py

# Custom frequency
python examples/upsampled_control/upsampled_control.py --hz 100

# Connect via BLE instead of WiFi
python examples/upsampled_control/upsampled_control.py --connection ble

# With config file
python examples/upsampled_control/upsampled_control.py --config my_robot_config.json
```

## CLI Alternative

You can also use the built-in CLI:

```bash
televoodoo --upsample-hz 200
```

## Configuration File

Add to your config JSON:

```json
{
  "upsample_to_frequency_hz": 200.0
}
```

## How It Works

```
Time:   0ms     16ms    21ms    26ms    32ms    ...
        ↓       ↓       ↓       ↓       ↓
Phone:  P0      -       -       P1      -       ...  (60 Hz input)
Output: P0      E1      E2      P1      E3      ...  (200 Hz output)
        ↑       ↑       ↑       ↑       ↑
       real   extrap  extrap   real   extrap
```

- `P0`, `P1`: Real poses from phone
- `E1`, `E2`, `E3`: Extrapolated poses (predictions based on velocity)
- All poses are emitted at fixed 5ms intervals (regulated mode)

### Extrapolation Math

**Position**: Linear extrapolation using velocity
```
velocity = (P1.position - P0.position) / dt_between_samples
predicted_position = P1.position + velocity * time_since_P1
```

**Orientation**: Angular velocity extrapolation
```
omega = rotation_from(P0.quaternion, P1.quaternion) / dt
predicted_quaternion = apply_rotation(P1.quaternion, omega * time_since_P1)
```

### Safety Limit

Extrapolation only continues for **one expected sample interval** beyond the last real pose. If no new pose arrives (phone disconnected, network issue), extrapolation stops to prevent the robot from continuing in a stale direction.
