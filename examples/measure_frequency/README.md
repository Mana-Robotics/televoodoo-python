# Measure Frequency

Measure the pose input frequency.

## Run

```bash
python examples/measure_frequency/measure_frequency.py --samples 100
```

## Output

```
Collecting... 100/100
100 samples: mean=16.7ms (~60.0 Hz)
```

## Save Plot

```bash
python examples/measure_frequency/measure_frequency.py --samples 100 --plot
```

Saves a Δt plot to the example directory (requires `matplotlib`).

