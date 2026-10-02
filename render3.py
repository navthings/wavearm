import sys, numpy as np, trimesh, matplotlib, cadquery as cq
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import arm3 as a

BG = "#efeeeb"
tmp = a.OUT / "_view"; tmp.mkdir(parents=True, exist_ok=True)
COL = {"logo_s": "#1e1e20", "ring": "#fbf7ea"}
GREY = "#d8d7d3"

def scene(yaw, sh, el, tag):
    out = []
    for n, p in a.PARTS.items():
        f = tmp / f"{n}_{tag}.stl"
        cq.exporters.export(a.posed(n, p, yaw, sh, el), str(f), tolerance=0.06, angularTolerance=0.12)
        out.append((trimesh.load(f), COL.get(n, GREY)))
    return out

def draw(ax, ms, elev, azim, zoom=1.0):
    L1 = np.array([-0.4, -0.8, 0.9]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.8, 0.2, 0.3]); L2 /= np.linalg.norm(L2)
    tris, cols = [], []
    for m, col in ms:
        n = m.face_normals
        sh = 0.40 + 0.50 * np.clip(n @ L1, 0, 1) + 0.14 * np.clip(n @ L2, 0, 1)
        tris.append(m.triangles); cols.append(np.clip(np.array(matplotlib.colors.to_rgb(col))[None] * sh[:, None], 0, 1))
    fc = np.vstack(cols)
    ax.add_collection3d(Poly3DCollection(np.vstack(tris), facecolors=fc, edgecolors=fc, linewidths=0.3))
    v = np.vstack([m.vertices for m, _ in ms]); c = (v.max(0) + v.min(0)) / 2; r = (v.max(0) - v.min(0)).max() / 2 * zoom
    ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_facecolor(BG)
    ax.set_proj_type("persp", focal_length=0.6)

poses = {"hero": (-25, 25, 75), "reach": (20, 50, 40), "up": (0, 0, 0), "back": (-25, 25, 75), "wave": (-90, -60, -80)}
name = sys.argv[1] if len(sys.argv) > 1 else "hero"
views = {"hero": [(12, -60)], "reach": [(15, -120)], "up": [(5, -90), (5, 0)], "back": [(18, 110)], "wave": [(8, -80)]}[name]
ms = scene(*poses[name], name)
fig = plt.figure(figsize=(7 * len(views), 7), facecolor=BG)
for i, (e, az) in enumerate(views):
    ax = fig.add_axes([i / len(views), 0, 1 / len(views), 1], projection="3d"); draw(ax, ms, e, az, 0.8)
fig.savefig(a.OUT / f"r_{name}.png", dpi=100, facecolor=BG)
