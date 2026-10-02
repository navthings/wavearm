from pathlib import Path

import trimesh

# lays the stls from arm3.py out on 180x180 bambu a1 mini plates
P = Path(__file__).parent / "print"


def place(name, x, y, z=0.0):
    m = trimesh.load(P / f"{name}.stl")
    b = m.bounds
    m.apply_translation([x - (b[0][0] + b[1][0]) / 2, y - (b[0][1] + b[1][1]) / 2, z - b[0][2]])
    return name, m


PLATES = {
    "plate0_servo_gauge": [("servo_gauge", 90, 90)],
    "plate1_tray": [("tray", 90, 90)],
    "plate1_tray_plus": [("tray", 90, 90), ("cover", 20, 22), ("cap_elbow", 162, 18)],
    "plate2_drum": [("drum", 90, 90)],
    "plate3_shoulder": [("shoulder", 90, 90)],
    "plate4_arm": [("up_front", 26, 90), ("up_back", 64, 90), ("fo_front", 100, 90), ("fo_back", 136, 90)],
    "plate5_small": [("ring", 90, 90), ("cover", 90, 105), ("cap_shoulder", 72, 72), ("cap_shoulder_logo", 72, 72, 1.6), ("cap_elbow", 108, 72)],
}

if __name__ == "__main__":
    (P / "a1mini").mkdir(exist_ok=True)
    for plate, parts in PLATES.items():
        scene = trimesh.Scene()
        for spec in parts:
            n, m = place(*spec)
            scene.add_geometry(m, node_name=n, geom_name=n)
        lo, hi = scene.bounds
        if lo[0] < 0 or lo[1] < 0 or hi[0] > 180 or hi[1] > 180:
            raise SystemExit(f"{plate} doesnt fit the a1 mini bed: {lo} {hi}")
        scene.export(P / "a1mini" / f"{plate}.3mf")
        print("wrote", plate)
