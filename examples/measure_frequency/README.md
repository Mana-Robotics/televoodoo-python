# Measure Frequency

Measure the pose input frequency. Can also verify upsampled frequency from `PoseResampler`.

## Run

```bash
# Measure raw input frequency
python examples/measure_frequency/measure_frequency.py --samples 100

# Measure upsampled frequency (verify PoseResampler output)
python examples/measure_frequency/measure_frequency.py --samples 500 --upsample-hz 200

# Connect via BLE
python examples/measure_frequency/measure_frequency.py --connection ble
```

## Output

```
Collecting... 100/100
100 samples (raw): mean=16.7ms (~60.0 Hz)
```

With upsampling:
```
Upsampling enabled: target 200.0 Hz
Collecting... 500/500
500 samples (upsampled to 200.0 Hz): mean=5.0ms (~200.0 Hz)
```

## Save Plot

```bash
python examples/measure_frequency/measure_frequency.py --samples 100 --plot
python examples/measure_frequency/measure_frequency.py --samples 500 --upsample-hz 200 --plot
```

Saves a Δt plot to the example directory (requires `matplotlib`).

