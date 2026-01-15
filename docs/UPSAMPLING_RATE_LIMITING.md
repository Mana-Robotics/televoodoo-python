# Upsampling & Rate Limiting

Robot arm controllers often require higher frequency input (100–200 Hz) than the phone can provide (30–60 Hz). Televoodoo can upsample pose data using linear extrapolation, or rate-limit output to a maximum frequency.

## Overview

| Feature | Purpose | Use Case |
|---------|---------|----------|
| **Upsampling** | Increase output frequency | Robot controllers requiring 100–200 Hz |
| **Rate Limiting** | Cap output frequency | Reduce processing load, match controller rate |

## Upsampling

Upsampling fills gaps between phone poses using velocity-based linear extrapolation.

### Via CLI

```bash
televoodoo --upsample-hz 200          # Upsample to 200 Hz
```

### Via Python

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config("my_robot_config.json")
pose_provider = PoseProvider(config)

def robot_handler(evt):
    """Called at ~200 Hz with real or extrapolated poses."""
    delta = pose_provider.get_delta(evt)
    if delta:
        robot.send_delta(delta['dx'], delta['dy'], delta['dz'])

start_televoodoo(callback=robot_handler, upsample_to_hz=200.0, quiet=True)
```

### Via Config File

```json
{
  "upsample_to_frequency_hz": 200.0
}
```

Then load and pass the config:

```python
config = load_config("my_robot_config.json")
start_televoodoo(callback=handler, config=config)
```

### How Upsampling Works

1. **Real poses** are forwarded immediately (zero added latency)
2. **Extrapolated poses** fill gaps using velocity-based prediction
3. **Safety**: Extrapolation stops if no new pose arrives within the expected interval (prevents runaway motion if phone disconnects)

### Regulated Mode

By default, upsampling uses **regulated mode** for consistent timing:
- Outputs at fixed intervals (e.g., every 5ms for 200 Hz)
- ~5ms maximum latency
- Ideal for robot controllers expecting consistent timing

To disable regulated mode (zero latency, irregular timing):

```bash
televoodoo --upsample-hz 200 --no-regulated
```

## Rate Limiting

Rate limiting caps the output frequency by dropping excess poses.

### Via CLI

```bash
televoodoo --rate-limit-hz 30         # Cap output at 30 Hz
```

### Via Python

```python
start_televoodoo(callback=handler, rate_limit_hz=30.0)
```

### Via Config File

```json
{
  "rate_limit_frequency_hz": 30.0
}
```

### When to Use Rate Limiting

- Your application can't process poses fast enough
- You want to reduce CPU load
- Your robot controller only accepts updates at a specific rate

## Combining Upsampling and Rate Limiting

You can use both options together, but typically you'd choose one:

```json
{
  "upsample_to_frequency_hz": 200.0,
  "rate_limit_frequency_hz": null
}
```

Or:

```json
{
  "upsample_to_frequency_hz": null,
  "rate_limit_frequency_hz": 30.0
}
```

## Configuration Reference

| Config Key | CLI Flag | Type | Description |
|------------|----------|------|-------------|
| `upsample_to_frequency_hz` | `--upsample-hz` | float or null | Target upsampling frequency (Hz) |
| `rate_limit_frequency_hz` | `--rate-limit-hz` | float or null | Maximum output frequency (Hz) |

## Example: High-Frequency Robot Control

```python
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config("robot_config.json")
pose_provider = PoseProvider(config)

def control_loop(evt):
    """Called at 200 Hz for smooth robot control."""
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    # Send to robot at 200 Hz
    robot.send_incremental_command(
        dx=delta['dx'],
        dy=delta['dy'],
        dz=delta['dz'],
        rx=delta['rx'],
        ry=delta['ry'],
        rz=delta['rz']
    )

# Upsample to 200 Hz, suppress logging
start_televoodoo(
    callback=control_loop,
    config=config,
    upsample_to_hz=200.0,
    quiet=True
)
```

## Frequency Guidelines

| Phone Output | Upsampling Target | Notes |
|--------------|-------------------|-------|
| ~60 Hz (WiFi) | 100–200 Hz | Good for most robots |
| ~30 Hz (BLE) | 60–100 Hz | Conservative upsampling |
| ~60 Hz (USB) | 100–200 Hz | Best source for upsampling |

## Safety Considerations

- **Extrapolation timeout**: If no new pose arrives within 2× the expected interval, extrapolation stops to prevent runaway motion
- **Test thoroughly**: Always test upsampling behavior with your specific robot and safety limits
- **Start conservative**: Begin with lower upsampling rates and increase as needed

## See Also

- **[Configuration](CONFIGURATION.md)** — Complete config file reference
- **[Usage](USAGE.md)** — CLI and Python options
- **[examples/data_upsampling/](../examples/data_upsampling/)** — Complete upsampling example
- **[examples/data_rate_limiting/](../examples/data_rate_limiting/)** — Rate limiting example
