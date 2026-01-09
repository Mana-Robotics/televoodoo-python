"""Print pose deltas from Televoodoo — ideal for robot teleoperation."""

from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

def on_delta(evt):
    delta = pose_provider.get_delta(evt)
    if delta is None:
        return
    
    print(f"dx={delta['dx']:.3f} dy={delta['dy']:.3f} dz={delta['dz']:.3f} | "
          f"rx={delta['rx']:.3f} ry={delta['ry']:.3f} rz={delta['rz']:.3f}")

start_televoodoo(callback=on_delta, quiet=True)

