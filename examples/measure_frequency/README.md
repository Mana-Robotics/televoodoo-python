# Measure Frequency

Measure the pose input frequency. Can also verify upsampled frequency from `PoseResampler`.

## Run

```bash
# Measure raw input frequency (saves CSV and plot by default)
python examples/measure_frequency/measure_frequency.py --samples 100

# Measure upsampled frequency (verify PoseResampler output)
python examples/measure_frequency/measure_frequency.py --samples 500 --upsample-hz 200

# Connect via USB (lowest latency)
python examples/measure_frequency/measure_frequency.py --connection usb

# Connect via BLE
python examples/measure_frequency/measure_frequency.py --connection ble

# Disable plot generation (CSV only)
python examples/measure_frequency/measure_frequency.py --samples 100 --no-plot
```

## Output

```
Collecting... 100/100
100 samples (raw): mean=16.7ms (~60.0 Hz)
Saved frequency data to frequency_20260116_171726.csv
Saved frequency plot to frequency_20260116_171726.png
```

With upsampling:
```
Upsampling enabled: target 200.0 Hz
Collecting... 500/500
500 samples (upsampled to 200.0 Hz): mean=5.0ms (~200.0 Hz)
```

## Pose Deltas

Calculate euclidean distances between consecutive pose samples:

```bash
# Measure frequency and pose deltas (using get_absolute)
python examples/measure_frequency/measure_frequency.py --samples 100 --pose-deltas

# Use get_delta instead (dx/dy/dz from movement origin)
python examples/measure_frequency/measure_frequency.py --samples 100 --pose-deltas --use-delta

# With upsampling
python examples/measure_frequency/measure_frequency.py --samples 500 --upsample-hz 200 --pose-deltas
```

Output:
```
100 samples (raw): mean=16.7ms (~60.0 Hz)
Pose deltas [get_absolute]: mean=0.0012, max=0.0089
Saved frequency data to frequency_20260116_171726.csv
Saved frequency plot to frequency_20260116_171726.png
Saved pose deltas data to pose_deltas_20260116_171726.csv
Saved pose deltas plot to pose_deltas_20260116_171726.png
```

The `--use-delta` flag uses `PoseProvider.get_delta()` which returns position deltas (dx/dy/dz) relative to the movement origin, instead of absolute positions.

## Plot Variants

Generate pose delta comparisons for raw vs upsampled data from a single recording:

```bash
# Record raw poses and generate variants: raw, up60hz, up100hz
python examples/measure_frequency/measure_frequency.py --samples 100 --plot-variants

# With get_delta mode
python examples/measure_frequency/measure_frequency.py --samples 100 --plot-variants --use-delta
```

This records raw poses and then applies offline linear interpolation to generate:
- `pose_deltas_{timestamp}_raw.csv/png` - Original raw data
- `pose_deltas_{timestamp}_up60hz.csv/png` - Upsampled to 60Hz
- `pose_deltas_{timestamp}_up100hz.csv/png` - Upsampled to 100Hz

Output:
```
100 samples (raw): mean=16.7ms (~60.0 Hz)

Generating pose delta variants from 100 raw samples:

  [raw] 100 samples, mean=0.0023, max=0.0089
  Saved pose_deltas_20260119_132250_raw.csv
  Saved pose_deltas_20260119_132250_raw.png

  [up60hz] 102 samples, mean=0.0022, max=0.0067
  Saved pose_deltas_20260119_132250_up60hz.csv
  Saved pose_deltas_20260119_132250_up60hz.png

  [up100hz] 170 samples, mean=0.0013, max=0.0040
  Saved pose_deltas_20260119_132250_up100hz.csv
  Saved pose_deltas_20260119_132250_up100hz.png
```

Plots are saved by default (requires `matplotlib`). Use `--no-plot` to disable.
