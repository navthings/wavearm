import wavearm as w

def clash(a, b):
    return a.intersect(b).val().Volume() if a.intersect(b).vals() else 0.0

static = {"tray": w.tray, "base": w.base, "shoulder": w.shoulder, "cover": w.cover, "servo1": w.servo1, "servo2": w.servo2, "pi": w.pi}
pairs = [("base", "shoulder"), ("base", "servo1"), ("shoulder", "servo1"), ("shoulder", "servo2"), ("cover", "servo2"),
         ("shoulder", "cover"), ("tray", "pi"), ("base", "pi"), ("tray", "base")]
for a, b in pairs:
    print(f"{a:>10} x {b:<10} {clash(static[a], static[b]):8.2f} mm3")
for ang in (-90, -60, -30, 0, 30, 60, 90):
    moving = w.posed("link_front", ang).union(w.posed("link_back", ang)).union(w.posed("cap", ang))
    hits = {k: round(clash(moving, v), 2) for k, v in static.items() if k not in ("servo2",)}
    hits["servo2"] = round(clash(w.posed("link_back", ang).union(w.posed("cap", ang)), w.servo2), 2)
    print(ang, hits)
print("front vs servo2 horn at 0:", round(clash(w.front, w.servo2), 2))
