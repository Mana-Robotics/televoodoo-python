"""Print absolute poses from Televoodoo."""

from televoodoo import start_televoodoo, PoseProvider, load_config

config = load_config()
pose_provider = PoseProvider(config)

def on_pose(evt):
    pose = pose_provider.get_absolute(evt)
    if pose is None:
        return
    
    print(f"x={pose['x']:.3f} y={pose['y']:.3f} z={pose['z']:.3f} | "
          f"qx={pose['qx']:.3f} qy={pose['qy']:.3f} qz={pose['qz']:.3f} qw={pose['qw']:.3f}")

start_televoodoo(callback=on_pose, quiet=True)

