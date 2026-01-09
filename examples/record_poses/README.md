# Record Poses

Demonstrates command-driven pose recording.

## Run

```bash
python examples/record_poses/record_poses.py  
```

## Commands

Send these commands from the Televoodoo App:

| Command | Value | Effect |
|---------|-------|--------|
| `recording` | `true` | Start recording poses |
| `recording` | `false` | Stop recording, wait for decision |
| `keep_recording` | `true` | Save recorded poses to JSON file |
| `keep_recording` | `false` | Discard recorded poses |

## Output

Recordings are saved to this directory as `recording_YYYYMMDD_HHMMSS.json`.
