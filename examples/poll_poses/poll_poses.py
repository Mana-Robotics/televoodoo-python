"""Poll latest pose at a fixed rate."""

import argparse
import threading
import time
from televoodoo import start_televoodoo, PoseProvider, load_config

parser = argparse.ArgumentParser()
parser.add_argument("--hz", type=float, default=10.0, help="Polling rate in Hz")
args = parser.parse_args()

config = load_config()
pose_provider = PoseProvider(config)

latest_pose = None
lock = threading.Lock()

def on_pose(evt):
    global latest_pose
    pose = pose_provider.get_absolute(evt)
    if pose is None:
        return
    with lock:
        latest_pose = pose

def poller():
    while True:
        time.sleep(1.0 / args.hz)
        with lock:
            if latest_pose:
                print(f"x={latest_pose['x']:.3f} y={latest_pose['y']:.3f} z={latest_pose['z']:.3f}")

threading.Thread(target=poller, daemon=True).start()
start_televoodoo(callback=on_pose, quiet=True)

