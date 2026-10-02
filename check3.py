import arm3 as a

def vol(x, y):
    i = x.intersect(y)
    return round(i.val().Volume(), 2) if i.vals() else 0.0

static = [("tray_nopegs", a.tray, "pi", a.pi), ("drum", a.drum, "pi", a.pi), ("tray", a.tray, "drum", a.drum),
          ("drum", a.drum, "servo1", a.servo1), ("shoulder", a.shoulder, "servo1", a.servo1), ("ring", a.ring, "drum", a.drum),
          ("ring", a.ring, "shoulder", a.shoulder), ("shoulder", a.shoulder, "servo2", a.servo2), ("cover", a.cover, "servo2", a.servo2),
          ("up_front", a.up_front, "servo3", a.servo3), ("up_back", a.up_back, "servo3", a.servo3), ("up_front", a.up_front, "servo2", a.servo2),
          ("up_back", a.up_back, "cover", a.cover), ("up_front", a.up_front, "shoulder", a.shoulder), ("fo_front", a.fo_front, "up_front", a.up_front),
          ("fo_back", a.fo_back, "up_back", a.up_back), ("fo_front", a.fo_front, "servo3", a.servo3)]
for n1, p1, n2, p2 in static:
    v = vol(p1, p2)
    print(f"{n1:>9} x {n2:<9} {v}" + ("   <-- clash" if v > 0.5 else ""))

fixed = a.shoulder.union(a.cover).union(a.drum).union(a.ring)
for sh in (-90, -60, -30, 0, 30, 60, 90):
    upper = a.up_front.union(a.up_back)
    upper_p = upper.rotate((0, 0, a.PZ), (0, 1, a.PZ), -sh)
    row = [f"sh {sh:+4d}: upper~base {vol(upper_p, fixed)}"]
    fore = a.fo_front.union(a.fo_back)
    for el in (-135, -90, -45, 0, 45, 90, 135):
        f = fore.rotate((0, 0, a.EZ), (0, 1, a.EZ), -el).rotate((0, 0, a.PZ), (0, 1, a.PZ), -sh)
        row.append(f"{el:+d}:{'ok' if vol(f, fixed.union(upper_p)) < 0.5 else 'X'}")
    print("  ".join(row))
