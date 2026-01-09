"""Demonstrate command-driven pose recording."""

import json
from datetime import datetime
from pathlib import Path
from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

# State
recording = False
poses = []
pending_save = False  # Waiting for keep_recording decision
idle_counter = 0  # Poses received while not recording

def on_event(evt):
    global recording, poses, pending_save, idle_counter
    
    if evt.get("type") == "pose":
        if recording:
            pose = pose_provider.get_absolute(evt)
            if pose:
                poses.append({"timestamp": datetime.now().isoformat(), "pose": pose})
                print(f"Recording... {len(poses)} poses", end="\r")
        else:
            idle_counter += 1
            print(f"Receiving {idle_counter} poses (NOT recording)", end="\r")
    
    elif evt.get("type") == "command":
        name = evt.get("name")
        value = evt.get("value")
        
        if name == "recording":
            if value and not recording:
                # Start recording
                recording = True
                poses = []
                pending_save = False
                idle_counter = 0
                print("\nRecording started")
            elif not value and recording:
                # Stop recording, wait for keep_recording
                recording = False
                pending_save = True
                print(f"\nRecording stopped ({len(poses)} poses). Waiting for keep_recording command...")
        
        elif name == "keep_recording" and pending_save:
            pending_save = False
            if value:
                # Save recording
                out_dir = Path(__file__).parent
                filename = out_dir / f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w") as f:
                    json.dump({"poses": poses}, f, indent=2)
                print(f"Saved {len(poses)} poses to {filename}")
            else:
                # Discard recording
                print(f"Discarded {len(poses)} poses")
            poses = []

print("Waiting for commands: recording (true/false), keep_recording (true/false)")
start_televoodoo(callback=on_event, quiet=True)
