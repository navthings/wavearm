from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

# packs the stls from arm3.py / gauge.py onto 180x180 bambu a1 mini plates, as many parts per plate as fit
P = Path(__file__).parent / "print"
BED, GAP = 180.0, 2.0

# (part, centre x, centre y, turn degrees, z offset)
PLATES = {
    # nothing here depends on your servo sizes and theres no colour pause, so its safe to leave running
    "plate1_now": [("tray", 59, 59, 0), ("gauge_width", 144, 62, 90), ("gauge_length", 53.5, 144, 0),
                   ("cover", 140, 150, 0), ("cap_elbow", 167, 140, 0)],
    # logo cap: pause at 1.6mm to swap colour
    "plate2_ring_logo": [("ring", 90, 90, 0), ("cap_shoulder", 75, 90, 0), ("cap_shoulder_logo", 75, 90, 0, 1.6)],
    # these have servo pockets, print after the gauge test
    "plate3_drum_arm": [("drum", 59, 59, 0), ("up_front", 137, 66, 0), ("fo_back", 57.5, 137, 90)],
    "plate4_shoulder_arm": [("shoulder", 59, 59, 0), ("up_back", 137, 66, 0), ("fo_front", 57.5, 137, 90)],
}


def footprint(m):
    """Top-down shadow of a mesh, used to keep parts apart on the plate."""
    tris = m.triangles[:, :, :2]
    a, b = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    keep = np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) > 1e-6
    return unary_union([Polygon(t) for t in tris[keep]]).buffer(0.01)


def placed(name, x, y, turn=0, z=0.0):
    m = trimesh.load(P / f"{name}.stl")
    if turn:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(turn), [0, 0, 1]))
    b = m.bounds
    m.apply_translation([x - (b[0][0] + b[1][0]) / 2, y - (b[0][1] + b[1][1]) / 2, z - b[0][2]])
    return m


if __name__ == "__main__":
    out = P / "a1mini"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.3mf"):
        f.unlink()
    bed = box(1, 1, BED - 1, BED - 1)
    for plate, parts in PLATES.items():
        scene, shapes = trimesh.Scene(), []
        for spec in parts:
            m = placed(*spec)
            scene.add_geometry(m, node_name=spec[0], geom_name=spec[0])
            shape = footprint(m)
            if not bed.contains(shape):
                raise SystemExit(f"{plate}: {spec[0]} hangs off the bed")
            for other, s in shapes:
                if spec[0].startswith("cap_shoulder") and other.startswith("cap_shoulder"):
                    continue  # the logo sits on top of its cap on purpose
                if shape.distance(s) < GAP:
                    raise SystemExit(f"{plate}: {spec[0]} is too close to {other}")
            shapes.append((spec[0], shape))
        scene.export(out / f"{plate}.3mf")
        print(f"{plate}: {', '.join(p[0] for p in parts)}")
