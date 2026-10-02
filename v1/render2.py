import numpy as np, trimesh, matplotlib, cadquery as cq
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import wavearm as w

BG = "#f2f1ee"
tmp = w.OUT / "_view"; tmp.mkdir(exist_ok=True)
COL = {"cap_logo": "#1e1e20", "pi": "#2f6b3a", "servo1": "#2b3f7a", "servo2": "#2b3f7a"}

def mesh(name, part, tag):
    f = tmp / f"{name}_{tag}.stl"
    cq.exporters.export(part, str(f), tolerance=0.06, angularTolerance=0.12)
    return trimesh.load(f)

def scene(angle=0, explode=0.0, inner=False):
    lift = {"tray": 0, "base": 1, "shoulder": 2, "cover": 2.6, "link_back": 3.2, "link_front": 3.2, "cap": 3.2, "cap_logo": 3.2}
    out = []
    for n in w.PARTS:
        p = w.posed(n, angle)
        if explode:
            p = p.translate((0, (-25 if n in ("link_front", "cap", "cap_logo") else 25 if n in ("cover", "link_back") else 0) * (explode > 0),
                             lift[n] * explode))
        out.append((mesh(n, p, f"{angle}_{explode}"), COL.get(n, "#dcdad5")))
    if inner:
        for n, p, z in (("pi", w.pi, 0), ("servo1", w.servo1, 1), ("servo2", w.servo2, 2)):
            out.append((mesh(n, p.translate((0, 0, z * explode)), f"{explode}"), COL[n]))
    return out

def draw(ax, ms, elev, azim, zoom=1.0):
    L1 = np.array([-0.5, -0.8, 0.9]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.7, 0.3, 0.2]); L2 /= np.linalg.norm(L2)
    tris, cols = [], []
    for m, col in ms:
        n = m.face_normals
        sh = 0.42 + 0.48 * np.clip(n @ L1, 0, 1) + 0.12 * np.clip(n @ L2, 0, 1)
        tris.append(m.triangles); cols.append(np.clip(np.array(matplotlib.colors.to_rgb(col))[None] * sh[:, None], 0, 1))
    fc = np.vstack(cols)
    ax.add_collection3d(Poly3DCollection(np.vstack(tris), facecolors=fc, edgecolors=fc, linewidths=0.3))
    v = np.vstack([m.vertices for m, _ in ms]); c = (v.max(0) + v.min(0)) / 2; r = (v.max(0) - v.min(0)).max() / 2 * zoom
    ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_facecolor(BG)
    ax.set_proj_type("persp", focal_length=0.6)

views = [("hero", scene(25), 14, -125, 0.85), ("front", scene(0), 3, -90, 0.9), ("side", scene(0), 3, 0, 0.9),
         ("back", scene(0), 22, 50, 0.85), ("exploded", scene(0, 38, inner=True), 12, -120, 0.85)]
for name, ms, e, a, z in views:
    fig = plt.figure(figsize=(8, 8), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1], projection="3d"); draw(ax, ms, e, a, z)
    fig.savefig(w.OUT / f"render_{name}.png", dpi=110, facecolor=BG); plt.close(fig)
print("done")
