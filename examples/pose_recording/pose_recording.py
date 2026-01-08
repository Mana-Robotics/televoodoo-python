import argparse
import json
import os
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from televoodoo import Pose, PoseTransformer, load_config
from televoodoo.ble import run_simulation, start_peripheral


class PoseRecorder:
    """Records poses between recording start/stop commands and saves on keep_recording."""

    def __init__(self, transformer: PoseTransformer, output_dir: str = "."):
        self.transformer = transformer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._recorded_poses: List[Dict[str, Any]] = []
        self._recording_start_time: Optional[datetime] = None
        self._session_name: Optional[str] = None
        self._lock = threading.Lock()

    def set_session_name(self, name: str) -> None:
        """Set the session name (used in output filenames)."""
        with self._lock:
            self._session_name = name

    def handle_pose(self, pose: Pose) -> Dict[str, Any]:
        """Transform and optionally record a pose. Returns the transformed output."""
        out = self.transformer.transform(pose)

        with self._lock:
            if self._recording:
                # Add timestamp to recorded pose
                record = {
                    "timestamp": datetime.now().isoformat(),
                    "pose": out,
                }
                self._recorded_poses.append(record)

        return out

    def start_recording(self) -> None:
        """Start recording poses."""
        with self._lock:
            if not self._recording:
                self._recording = True
                self._recorded_poses = []
                self._recording_start_time = datetime.now()
                print(
                    json.dumps({
                        "type": "recording_started",
                        "time": self._recording_start_time.isoformat(),
                    }),
                    flush=True,
                )

    def stop_recording(self) -> int:
        """Stop recording poses. Returns the number of recorded poses."""
        with self._lock:
            if self._recording:
                self._recording = False
                count = len(self._recorded_poses)
                print(
                    json.dumps({
                        "type": "recording_stopped",
                        "pose_count": count,
                    }),
                    flush=True,
                )
                return count
            return 0

    def keep_recording(self, keep: bool) -> Optional[str]:
        """
        Keep or discard the recorded poses.
        If keep=True, saves to a file and returns the filename.
        If keep=False, discards the recording and returns None.
        """
        with self._lock:
            if keep and self._recorded_poses:
                # Generate filename from session name and datetime
                session = self._session_name or "session"
                timestamp = self._recording_start_time or datetime.now()
                filename = f"{session}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                filepath = self.output_dir / filename

                # Build recording data
                recording_data = {
                    "session_name": session,
                    "recording_start": timestamp.isoformat(),
                    "recording_end": datetime.now().isoformat(),
                    "pose_count": len(self._recorded_poses),
                    "poses": self._recorded_poses,
                }

                # Save to file
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(recording_data, f, indent=2)

                print(
                    json.dumps({
                        "type": "recording_saved",
                        "filename": str(filepath),
                        "pose_count": len(self._recorded_poses),
                    }),
                    flush=True,
                )

                # Clear recorded poses
                self._recorded_poses = []
                self._recording_start_time = None
                return str(filepath)
            else:
                # Discard
                count = len(self._recorded_poses)
                self._recorded_poses = []
                self._recording_start_time = None
                print(
                    json.dumps({
                        "type": "recording_discarded",
                        "pose_count": count,
                    }),
                    flush=True,
                )
                return None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @property
    def recorded_count(self) -> int:
        with self._lock:
            return len(self._recorded_poses)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record poses using Televoodoo with start/stop/keep commands"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON OutputConfig (same format the app saves)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save recordings (default: current directory)",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Use simulation mode instead of BLE peripheral",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Auto-exit after N seconds",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Static BLE peripheral name (default: randomly generated)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Static authentication code (default: randomly generated 6-char code)",
    )
    args = parser.parse_args()

    # Build transformer from config
    cfg = load_config(args.config)
    transformer = PoseTransformer(cfg)

    # Create recorder
    recorder = PoseRecorder(transformer, output_dir=args.output_dir)

    if not args.sim:  # Default to BLE mode
        # Graceful shutdown on Ctrl+C / SIGTERM
        try:
            import CoreFoundation as CF  # type: ignore
        except Exception:
            CF = None  # type: ignore

        def stop_run_loop(*_args: object) -> None:
            if CF is not None:
                try:
                    CF.CFRunLoopStop(CF.CFRunLoopGetMain())
                except Exception:
                    pass

        if CF is not None:
            signal.signal(signal.SIGINT, lambda *_: stop_run_loop())
            signal.signal(signal.SIGTERM, lambda *_: stop_run_loop())

        # Optional auto-exit timer
        if args.duration is not None and CF is not None:
            def timer_stop() -> None:
                time.sleep(max(0.0, float(args.duration)))
                stop_run_loop()
            threading.Thread(target=timer_stop, daemon=True).start()

        def on_ble_event(evt: Dict[str, Any]) -> None:
            evt_type = evt.get("type")

            # Capture session name for filenames
            if evt_type == "session":
                name = evt.get("name")
                if name:
                    recorder.set_session_name(name)

            # Handle pose events
            elif evt_type == "pose":
                ai = evt.get("data", {}).get("absolute_input", {})
                try:
                    pose = Pose(
                        movement_start=bool(ai.get("movement_start", False)),
                        x=float(ai.get("x", 0.0)),
                        y=float(ai.get("y", 0.0)),
                        z=float(ai.get("z", 0.0)),
                        x_rot=float(ai.get("x_rot", 0.0)),
                        y_rot=float(ai.get("y_rot", 0.0)),
                        z_rot=float(ai.get("z_rot", 0.0)),
                        qx=float(ai.get("qx", 0.0)),
                        qy=float(ai.get("qy", 0.0)),
                        qz=float(ai.get("qz", 0.0)),
                        qw=float(ai.get("qw", 1.0)),
                    )
                except Exception:
                    return
                out = recorder.handle_pose(pose)
                # Log pose (with recording status)
                log_entry = {
                    "type": "pose_logged",
                    "recording": recorder.is_recording,
                    "recorded_count": recorder.recorded_count,
                    "pose": out,
                }
                print(json.dumps(log_entry), flush=True)

            # Handle command events
            elif evt_type == "command":
                cmd_name = evt.get("name")
                cmd_value = evt.get("value")

                if cmd_name == "recording":
                    if cmd_value:
                        recorder.start_recording()
                    else:
                        recorder.stop_recording()

                elif cmd_name == "keep_recording":
                    recorder.keep_recording(bool(cmd_value))

        try:
            # CLI args override config file; config file overrides random
            ble_name = args.name or cfg.ble_name
            ble_code = args.code or cfg.ble_code
            start_peripheral(on_ble_event, quiet=True, name=ble_name, code=ble_code)
        except Exception as e:
            print(
                json.dumps({"type": "error", "message": f"BLE peripheral failed: {e}"}),
                flush=True,
            )
        return 0

    else:  # Simulation mode
        print(
            json.dumps({
                "type": "info",
                "message": "Simulation mode: poses will be generated. "
                           "Use Ctrl+C to stop, or --duration to auto-stop."
            }),
            flush=True,
        )

        # In sim mode, demonstrate recording with a simple timer
        recorder.set_session_name("simulation")

        pose_count = [0]

        def on_pose(pose: Pose) -> None:
            pose_count[0] += 1
            out = recorder.handle_pose(pose)
            log_entry = {
                "type": "pose_logged",
                "recording": recorder.is_recording,
                "recorded_count": recorder.recorded_count,
                "pose": out,
            }
            print(json.dumps(log_entry), flush=True)

            # Demo: auto-start recording after 10 poses, stop after 20, keep after 25
            if pose_count[0] == 10:
                print(json.dumps({"type": "info", "message": "Auto-starting recording (demo)"}), flush=True)
                recorder.start_recording()
            elif pose_count[0] == 20:
                print(json.dumps({"type": "info", "message": "Auto-stopping recording (demo)"}), flush=True)
                recorder.stop_recording()
            elif pose_count[0] == 25:
                print(json.dumps({"type": "info", "message": "Auto-keeping recording (demo)"}), flush=True)
                recorder.keep_recording(True)

        if args.duration is not None:
            t = threading.Thread(target=run_simulation, args=(on_pose,), daemon=True)
            t.start()
            time.sleep(max(0.0, float(args.duration)))
        else:
            try:
                run_simulation(on_pose)
            except KeyboardInterrupt:
                pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

