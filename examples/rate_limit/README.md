# Rate Limiting Example

This example demonstrates how to cap the frequency of pose data from the phone.

## Use Case

Some robot controllers or simulations can only handle a limited update rate. Rate limiting drops excess poses while keeping the latest values, ensuring your downstream consumer isn't overwhelmed.

## Usage

Run from the `televoodoo/` directory:

```bash
# Limit to 30 Hz (default)
python examples/rate_limit/rate_limit.py

# Limit to 10 Hz for slow consumers
python examples/rate_limit/rate_limit.py --hz 10

# Use specific connection
python examples/rate_limit/rate_limit.py --connection wifi
python examples/rate_limit/rate_limit.py --connection ble
```

## How It Works

- Input poses arrive at phone rate (60 Hz WiFi, ~30 Hz BLE)
- Rate limiter drops excess poses to stay at or below target frequency
- Latest pose is always used when output is allowed
- No added latency - poses are forwarded immediately when the rate allows

## Rate Limiting vs Upsampling

| Feature | Rate Limiting | Upsampling |
|---------|---------------|------------|
| Purpose | Cap frequency | Increase frequency |
| Output rate | ≤ target Hz | = target Hz |
| Latency | Zero | ~5ms (regulated) |
| Use case | Slow consumers | Fast robot control |
