import argparse
import json
import sys
import threading
import time
from televoodoo.ble import run_simulation, start_peripheral
from televoodoo.transform import OutputConfig, PoseTransformer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="")
    args = parser.parse_args()

    # start BLE peripheral and print session + QR automatically
    start_peripheral()

    config = OutputConfig(
        includeFormats={
            "absolute_input": True,
            "delta_input": False,
            "absolute_transformed": True,
            "delta_transformed": False,
        },
        includeOrientation={
            "quaternion": True,
            "euler_radian": False,
            "euler_degree": False,
        },
        scale=1.0,
        outputAxes={"x": 1.0, "y": 1.0, "z": 1.0},
    )
    transformer = PoseTransformer(config)

    def on_pose(pose):
        out = transformer.transform(pose)
        print(json.dumps({"type": "pose", "data": out}), flush=True)

    # heartbeat thread
    def heartbeat():
        counter = 0
        while True:
            counter += 1
            # service heartbeat, not BLE connectivity
            print(json.dumps({"type": "service_heartbeat", "counter": counter}), flush=True)
            time.sleep(1.0)

    threading.Thread(target=heartbeat, daemon=True).start()

    # Note: start_peripheral blocks; simulation runs only with --simulate

    # do not simulate poses by default; enable with --simulate
    if args.config == "--simulate":
        run_simulation(on_pose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


