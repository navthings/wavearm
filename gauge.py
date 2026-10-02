import cadquery as cq

# push a servo body into each slot. the tightest one it still slides into is its size.
# two strips so they pack around the big round parts on a plate
WIDTHS = [12.0, 12.2, 12.4, 12.6, 12.8, 13.0]      # slots 26 long, tests the servo's width
LENGTHS = [22.4, 22.8, 23.2, 23.6, 24.0]           # slots 14 wide, tests the servo's length
T = 4.0
PITCH = 19.0


def strip(sizes, slot, label):
    n = len(sizes)
    body = cq.Workplane("XY").box(n * PITCH + 6, 46, T, centered=(False, False, False)).edges("|Z").fillet(4)
    for i, s in enumerate(sizes):
        cx = 3 + PITCH * i + PITCH / 2
        w, l = slot(s)
        body = body.cut(cq.Workplane("XY").center(cx, 18).rect(w, l).extrude(T + 1).translate((0, 0, -0.5)))
        body = body.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(cx, 39).text(f"{s:.1f}", 4.0, 1, combine=False, halign="center", valign="center"))
    return body.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(n * PITCH + 1, 4).text(label, 4, 1, combine=False, halign="right", valign="bottom"))


if __name__ == "__main__":
    cq.exporters.export(strip(WIDTHS, lambda s: (s, 26.0), "W"), "print/gauge_width.stl", tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(strip(LENGTHS, lambda s: (min(14.0, PITCH - 4), s), "L"), "print/gauge_length.stl", tolerance=0.02, angularTolerance=0.1)
    print("wrote gauge_width.stl, gauge_length.stl")
