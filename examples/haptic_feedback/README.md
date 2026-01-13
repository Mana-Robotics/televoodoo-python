# Haptic Feedback

Demonstrates sending haptic feedback to the iOS app using simulated sensor values.

This example uses a sine wave (3-second period) to simulate changing sensor values, such as force feedback from a robot gripper or collision detection.

## Run

```bash
# Default (WiFi connection)
python examples/haptic_feedback/haptic_feedback.py

# Use BLE connection
python examples/haptic_feedback/haptic_feedback.py --connection ble
```

## Output

```
Haptic Feedback Example
================================================================================
Simulating sine wave with 3.0s period
Update rate: 20 Hz

✓ = haptic sent, ○ = no client connected

✓ Haptic: [██████████░░░░░░░░░░] 0.50
  Pose: x=+0.152 y=+0.203 z=-0.081 | qw=+0.812 qx=+0.012 qy=-0.568 qz=+0.123
```

The display shows:
- **Haptic bar**: Current intensity (0.0 to 1.0) with send status
  - `✓` = haptic was sent to a connected iOS client
  - `○` = no client connected (server running but waiting)
- **Pose line**: Latest 6DoF pose received from the phone (position + quaternion)

## How It Works

1. A background thread generates a sine wave value every 50ms (20 Hz)
2. The value is normalized to 0.0–1.0 and sent via `send_haptic()`
3. The iOS app receives the value and generates proportional haptic vibrations
4. Meanwhile, the main thread runs televoodoo to receive pose data

## Customization

Modify these constants in the script:

```python
PERIOD_SECONDS = 3.0  # Sine wave period
UPDATE_RATE_HZ = 20   # Haptic update frequency
```

## Real-World Usage

In a real robot application, replace the sine wave simulation with actual sensor readings:

```python
def force_monitor_loop():
    while True:
        force = robot.get_gripper_force()  # e.g., 0-50 Newtons
        send_haptic(force, min_value=0.0, max_value=50.0)
        time.sleep(0.05)
```
