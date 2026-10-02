import cadquery as cq

# push a servo body into each slot. the tightest one it still slides into without forcing is its size
WIDTHS = [12.0, 12.2, 12.4, 12.6, 12.8, 13.0]      # slots 26 long, tests the servo's width
LENGTHS = [22.4, 22.8, 23.2, 23.6, 24.0]           # slots 14 wide, tests the servo's length
T = 4.0
pitch_w, pitch_l = 19.0, 22.0
width = max(len(WIDTHS) * pitch_w, len(LENGTHS) * pitch_l) + 8

plate = cq.Workplane("XY").box(width, 92, T, centered=(False, False, False)).edges("|Z").fillet(4)
for i, w in enumerate(WIDTHS):
    cx = 4 + pitch_w * i + pitch_w / 2
    plate = plate.cut(cq.Workplane("XY").center(cx, 22).rect(w, 26).extrude(T + 1).translate((0, 0, -0.5)))
    plate = plate.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(cx, 39.5).text(f"{w:.1f}", 4.2, 1, combine=False, halign="center", valign="center"))
for i, l in enumerate(LENGTHS):
    cx = 4 + pitch_l * i + pitch_l / 2
    plate = plate.cut(cq.Workplane("XY").center(cx, 66).rect(14, l).extrude(T + 1).translate((0, 0, -0.5)))
    plate = plate.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(cx, 84).text(f"{l:.1f}", 4.2, 1, combine=False, halign="center", valign="center"))
plate = plate.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(width - 14, 47).text("W", 5, 1, combine=False))
plate = plate.cut(cq.Workplane("XY", origin=(0, 0, T - 0.6)).center(width - 14, 52).text("L", 5, 1, combine=False).translate((0, 30, 0)))
cq.exporters.export(plate, "print/servo_gauge.stl", tolerance=0.02, angularTolerance=0.1)
bb = plate.val().BoundingBox()
print(f"gauge {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm")
