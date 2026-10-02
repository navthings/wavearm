import sys, numpy as np, trimesh, matplotlib, cadquery as cq
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import wavearm as w

GREY, DARK, SERVO = "#dcdad5", "#202022", "#2b3f7a"
tmp = w.OUT / "_view"; tmp.mkdir(exist_ok=True)

def meshes(angle):
    out = []
    items = [(n, w.posed(n, angle), DARK if n == "cap_logo" else GREY) for n in w.PARTS]
    for n, part, col in items:
        f = tmp / f"{n}_{angle}.stl"
        cq.exporters.export(part, str(f), tolerance=0.08, angularTolerance=0.15)
        out.append((trimesh.load(f), col))
    return out

def draw(ax, ms, elev, azim):
    tris, cols = [], []
    L1 = np.array([-0.5, -0.8, 0.9]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.7, 0.3, 0.2]); L2 /= np.linalg.norm(L2)
    for m, col in ms:
        n = m.face_normals
        sh = 0.42 + 0.48 * np.clip(n @ L1, 0, 1) + 0.12 * np.clip(n @ L2, 0, 1)
        c = np.array(matplotlib.colors.to_rgb(col))
        tris.append(m.triangles); cols.append(np.clip(c[None] * sh[:, None], 0, 1))
    fc = np.vstack(cols); pc = Poly3DCollection(np.vstack(tris), facecolors=fc, edgecolors=fc, linewidths=0.3)
    ax.add_collection3d(pc)
    v = np.vstack([m.vertices for m, _ in ms]); c = (v.max(0) + v.min(0)) / 2; r = (v.max(0) - v.min(0)).max() / 2 * 0.9
    ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off()
    ax.set_proj_type("persp", focal_length=0.6)

hero = meshes(25)
upright = meshes(0)
fig = plt.figure(figsize=(16, 9), facecolor="#f4f3f0")
ax = fig.add_axes([0.0, 0.0, 0.5, 1.0], projection="3d"); ax.set_facecolor("#f4f3f0"); draw(ax, hero, 14, -125)
for i, (e, a, ms) in enumerate([(4, -90, upright), (4, 0, upright), (25, 50, upright), (8, -90, meshes(-35))]):
    ax = fig.add_axes([0.5 + (i % 2) * 0.25, 0.5 - (i // 2) * 0.5, 0.25, 0.5], projection="3d"); ax.set_facecolor("#f4f3f0")
    draw(ax, ms, e, a)
plt.savefig(w.OUT / "preview.png", dpi=100, facecolor="#f4f3f0")
