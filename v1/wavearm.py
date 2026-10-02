import json
from pathlib import Path

import cadquery as cq
from shapely.affinity import scale, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).parent
OUT = HERE / "out"

# MG90S micro servo. measure yours with calipers and fix these first
S_L = 22.8          # body length
S_W = 12.4          # body width
S_TAB = 16.0        # bottom of body to underside of tabs
S_TAB_T = 2.5
S_TOP = 22.5        # bottom of body to top face of body
S_H = 31.5          # bottom of body to top of the output spline
S_TAB_LEN = 32.5    # tab tip to tab tip
S_OFF = 6.0         # body end to centre of output shaft
S_HOLES = 27.8      # distance between the two tab screw holes
FIT = 0.4

# double arm horn that comes with the servo
HORN_LEN = 31.0
HORN_W = 6.4
HORN_DEPTH = 2.0
HORN_SEAT = S_H - 1.2   # where the part touching the horn starts, measured like S_H

# Raspberry Pi 5, check against yours. board 85 x 56, ports on the right short edge,
# usb-c + 2 micro hdmi on the bottom long edge, mounting holes 58 x 49 (M2.5)
PI_L, PI_W, PI_T = 85.0, 56.0, 1.6
PI_HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]  # from the left short edge / bottom long edge
PI_USBC_U = 11.2            # usb-c centre from the left short edge
PI_HDMI_U = (25.8, 39.2)
PI_PORT_H = 16.5            # tallest port stack above the board (ethernet / usb-a)
PI_STANDOFF = 4.0

PLINTH = 112.0
PLINTH_H = 30.0             # the tray the pi lives in
PLINTH_R = 24.0
LID_T = 4.0                 # drum floor, also the tray lid
DECK = PLINTH_H + LID_T
DRUM_R = 48.0
WALL = 3.5
TRAY_WALL = 3.0
TRAY_FLOOR = 2.4
PLATTER_T = 8.0
TOWER_R = 15.0      # shoulder tower: half width and top radius
LINK_LEN = 88.0     # pivot to tip
LINK_R0, LINK_R1 = 15.0, 12.0
PLATE_T = 5.0
CAP_D, CAP_T = 20.0, 1.6
LOGO_W, LOGO_H = 14.0, 0.6
M3_CLEAR, M3_PILOT, M2_PILOT = 3.4, 2.6, 1.8

# heights, all derived
SERVO1_Z = DECK + 6.0                 # servo 1 bottom, hangs by its tabs
RAIL_TOP = SERVO1_Z + HORN_SEAT       # platter sits here
DRUM_TOP = RAIL_TOP - 0.8             # leaves a shadow gap under the platter
PLATTER_TOP = RAIL_TOP + PLATTER_T
PIVOT_Z = PLATTER_TOP + 24.5          # shoulder axis height
S2_BOTTOM_Y = 12.0                    # servo 2 bottom face (it points forward, -Y)


def sy(s):
    """Distance along servo 2 (0 = its bottom, S_H = spline top) to world y."""
    return S2_BOTTOM_Y - s


Y_TOWER_FRONT = sy(S_TOP)
Y_COVER_BACK = sy(-3.0)
Y_BOSS_BACK = sy(-5.0)
Y_LINK_FRONT_IN = sy(HORN_SEAT)
Y_LINK_FRONT_OUT = Y_LINK_FRONT_IN - PLATE_T
Y_LINK_BACK_IN = Y_BOSS_BACK + 0.5
Y_LINK_BACK_OUT = Y_LINK_BACK_IN + PLATE_T


def slab(sketch, y1, y2, ch=0.0):
    """Extrude a sketch drawn in (x, z) between world y1 < y2."""
    s = cq.Workplane("XY").workplane(offset=-y2).placeSketch(sketch).extrude(y2 - y1)
    if ch:
        s = s.faces(">Z").chamfer(ch).faces("<Z").chamfer(ch)
    return s.rotate((0, 0, 0), (1, 0, 0), 90)


def ycyl(x, z, r, y1, y2):
    return cq.Workplane("XZ", origin=(0, y2, 0)).center(x, z).circle(r).extrude(y2 - y1)


def zcyl(x, y, r, z1, z2):
    return cq.Workplane("XY", origin=(0, 0, z1)).center(x, y).circle(r).extrude(z2 - z1)


def cube(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def rounded_polys(polys, r):
    sk = cq.Sketch()
    for p in polys:
        sk = sk.push([(0, 0)]).polygon(list(p.exterior.coords)).reset()
    return sk.vertices().fillet(r).reset()


def logo_shape(width):
    data = json.loads((HERE / "logo.json").read_text())
    g = unary_union([Polygon(p).buffer(0) for p in data["polys"]]
                    + [Point(x, y).buffer(r, 32) for x, y, r in data["circles"]])
    minx, miny, maxx, maxy = g.bounds
    k = width / (maxx - minx)
    g = scale(g, k, -k, origin=(0, 0))  # svg y points down
    minx, miny, maxx, maxy = g.bounds
    return translate(g, -(minx + maxx) / 2, -(miny + maxy) / 2)


def extrude_geom(geom, h, z0=0.0):
    out = None
    for p in getattr(geom, "geoms", [geom]):
        solid = cq.Workplane("XY").workplane(offset=z0).polyline(list(p.exterior.coords)[:-1]).close().extrude(h)
        for hole in p.interiors:
            solid = solid.cut(cq.Workplane("XY").workplane(offset=z0 - 1).polyline(list(hole.coords)[:-1]).close().extrude(h + 2))
        out = solid if out is None else out.union(solid)
    return out


# tray: the pi lives in here. ports out the back and side, vents, screws from underneath
s1_cx = -(S_L / 2 - S_OFF)             # servo 1 body centre (shaft on the origin)
ledge = SERVO1_Z + S_TAB
tab_half = S_TAB_LEN / 2
plinth_sk = cq.Sketch().rect(PLINTH, PLINTH).vertices().fillet(PLINTH_R)
inner_sk = cq.Sketch().rect(PLINTH - 2 * TRAY_WALL, PLINTH - 2 * TRAY_WALL).vertices().fillet(PLINTH_R - TRAY_WALL)
tray = (cq.Workplane("XY").placeSketch(plinth_sk).extrude(PLINTH_H)
        .faces(">Z").chamfer(0.8).faces("<Z").chamfer(0.6))
tray = tray.cut(cq.Workplane("XY", origin=(0, 0, TRAY_FLOOR)).placeSketch(inner_sk).extrude(PLINTH_H))
corner = PLINTH / 2 - 9.0
corners = [(sx * corner, sy_ * corner) for sx in (-1, 1) for sy_ in (-1, 1)]
for cx, cy in corners:
    boss = zcyl(cx, cy, 4.2, 0, PLINTH_H).union(cube(cx - 5 if cx < 0 else cx, cx if cx < 0 else cx + 5, cy - 5 if cy < 0 else cy,
                                                     cy if cy < 0 else cy + 5, 0, PLINTH_H)).intersect(
        cq.Workplane("XY").placeSketch(plinth_sk).extrude(PLINTH_H))
    tray = tray.union(boss)
    tray = tray.cut(zcyl(cx, cy, M3_CLEAR / 2, -1, PLINTH_H + 1)).cut(zcyl(cx, cy, 3.0, -1, PLINTH_H - 5))

# pi placement: usb/ethernet edge at the back wall, usb-c edge at the right wall
pi_x1 = 38.5                                  # usb-c long edge, pulled in so the board clears the rounded corner
pi_x0 = pi_x1 - PI_W
pi_y1 = PLINTH / 2 - TRAY_WALL - 3.2          # usb / ethernet short edge, ports stick out ~2mm
pi_y0 = pi_y1 - PI_L
pi_z0 = TRAY_FLOOR + PI_STANDOFF
pi_top = pi_z0 + PI_T


def pi_xy(u, v):
    """Board coords (u from the left short edge, v from the usb-c edge) to world."""
    return pi_x1 - v, pi_y0 + u


for u, v in PI_HOLES:
    hx, hy = pi_xy(u, v)
    tray = tray.union(zcyl(hx, hy, 3.0, TRAY_FLOOR - 0.5, pi_z0)).cut(zcyl(hx, hy, 1.1, TRAY_FLOOR, pi_z0 + 1))
# back: one opening for the usb-a and ethernet stacks
tray = tray.cut(cq.Workplane("XZ", origin=(0, PLINTH / 2 + 1, 0)).center((pi_x0 + pi_x1) / 2, pi_top + PI_PORT_H / 2 - 0.5)
                .rect(PI_W - 2, PI_PORT_H + 1.5).extrude(TRAY_WALL + 2).edges("|Y").fillet(2.5))
# right side: usb-c power + both micro hdmi in one slot
u0, u1 = PI_USBC_U - 6, PI_HDMI_U[1] + 5
tray = tray.cut(cq.Workplane("YZ", origin=(PLINTH / 2 - TRAY_WALL - 1, 0, 0)).center(pi_y0 + (u0 + u1) / 2, pi_top + 1.6)
                .slot2D(u1 - u0, 8.0).extrude(TRAY_WALL + 2))
# vents: holes on the left and front walls, slots in the floor under the pi
for wall_y, plane, origin, span in (("left", "YZ", (-PLINTH / 2 - 1, 0, 0), 60), ("front", "XZ", (0, -PLINTH / 2 + TRAY_WALL + 1, 0), 60)):
    pts = [(c, z) for c in [-span / 2 + i * 6 for i in range(int(span / 6) + 1)] for z in (10, 16, 22)]
    pts = [(c + (3 if z == 16 else 0), z) for c, z in pts if abs(c + (3 if z == 16 else 0)) <= span / 2]
    tray = tray.cut(cq.Workplane(plane, origin=origin).pushPoints(pts).circle(1.6).extrude(TRAY_WALL + 2))
for i in range(7):
    vx = pi_x0 + 8 + i * 6.5
    tray = tray.cut(cq.Workplane("XY", origin=(0, 0, -1)).center(vx, (pi_y0 + pi_y1) / 2).slot2D(50, 2.6, angle=90).extrude(TRAY_FLOOR + 2))
for fx in (-1, 1):
    for fy in (-1, 1):
        tray = tray.cut(zcyl(fx * 38, fy * 38, 5.2, -1, 1.0))  # rubber feet

# drum: sits on the tray as its lid, servo 1 hangs by its tabs in a cradle
lid = (cq.Workplane("XY", origin=(0, 0, PLINTH_H)).placeSketch(plinth_sk).extrude(LID_T)
       .faces(">Z").chamfer(1.2).faces("<Z").chamfer(0.8))
drum = zcyl(0, 0, DRUM_R, DECK - 1, DRUM_TOP).faces(">Z").chamfer(1.0)
base = lid.union(drum)
base = base.cut(zcyl(0, 0, DRUM_R - WALL, DECK, 400))
base = base.cut(zcyl(0, 0, DRUM_R + 1, DECK, DECK + 0.8).cut(zcyl(0, 0, DRUM_R - 1.0, DECK, DECK + 0.8)))  # shadow gap
base = base.union(zcyl(0, 0, DRUM_R - 0.8, DRUM_TOP - 1, RAIL_TOP).cut(zcyl(0, 0, DRUM_R - 2.6, DRUM_TOP - 2, RAIL_TOP + 1)))  # thrust rail
cradle = cube(s1_cx - tab_half - 3, s1_cx + tab_half + 3, -S_W / 2 - 3, S_W / 2 + 3, DECK - 0.5, ledge)
cradle = cradle.cut(cube(s1_cx - S_L / 2 - FIT / 2, s1_cx + S_L / 2 + FIT / 2, -S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, DECK, 400))
cradle = cradle.cut(cube(s1_cx - tab_half - 4, s1_cx - S_L / 2, -3, 3, DECK, ledge + 1))  # cable exit
for hx in (s1_cx - S_HOLES / 2, s1_cx + S_HOLES / 2):
    cradle = cradle.cut(zcyl(hx, 0, M2_PILOT / 2, ledge - 8, ledge + 1))
base = base.union(cradle)
WIRE_HOLE = (pi_x0 - 6.0, 22.0)
base = base.cut(zcyl(*WIRE_HOLE, 6.0, PLINTH_H - 1, DECK + 1))  # servo wires down to the gpio header
for cx, cy in corners:
    base = base.cut(zcyl(cx, cy, M3_PILOT / 2, PLINTH_H - 1, DECK - 0.8))

# platter + shoulder tower, one print
platter = zcyl(0, 0, DRUM_R, RAIL_TOP, PLATTER_TOP).faces(">Z").chamfer(1.2).faces("<Z").chamfer(0.5)
horn1 = cq.Workplane("XY", origin=(0, 0, RAIL_TOP - 1)).slot2D(HORN_LEN + 0.6, HORN_W + 0.4).extrude(HORN_DEPTH + 1)
platter = platter.cut(horn1)
platter = platter.cut(zcyl(0, 0, 4.0, RAIL_TOP - 1, RAIL_TOP + HORN_DEPTH + 3.5))  # horn hub + screw head
tower_h = PIVOT_Z - PLATTER_TOP
tower_sk = (cq.Sketch().push([(0, PLATTER_TOP + tower_h / 2)]).rect(2 * TOWER_R, tower_h)
            .reset().push([(0, PIVOT_Z)]).circle(TOWER_R).reset())
tower = slab(tower_sk, Y_TOWER_FRONT, S2_BOTTOM_Y, ch=0.8)
tower = tower.union(ycyl(0, PIVOT_Z, 9.0, sy(S_TOP + 4.5), Y_TOWER_FRONT + 0.5).faces("<Y").chamfer(0.6))  # shoulder boss
s2_cz = PIVOT_Z - (S_L / 2 - S_OFF)
tower = tower.cut(cube(-S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, sy(S_TAB + S_TAB_T + 0.1), S2_BOTTOM_Y + 1,
                       s2_cz - tab_half - FIT, s2_cz + tab_half + FIT))
tower = tower.cut(cube(-S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, sy(S_TOP + 10), S2_BOTTOM_Y,
                       s2_cz - S_L / 2 - FIT / 2, s2_cz + S_L / 2 + FIT / 2))
tower = tower.cut(ycyl(0, PIVOT_Z, 6.3, sy(S_TOP + 10), sy(S_TOP - 1)))
cover_screws = [(sx * 11.0, PIVOT_Z - 14.0) for sx in (-1, 1)]
for cx, cz in cover_screws:
    tower = tower.cut(ycyl(cx, cz, M3_PILOT / 2, S2_BOTTOM_Y - 10, S2_BOTTOM_Y + 1))
shoulder = platter.union(tower)
shoulder = shoulder.cut(zcyl(0, 0, 2.1, RAIL_TOP - 1, PIVOT_Z + TOWER_R + 1))  # screwdriver for servo 1's horn screw
shoulder = shoulder.cut(cube(-3.5, 3.5, sy(7.5), sy(2.0), RAIL_TOP - 1, s2_cz - tab_half))  # servo 2 cable down
for hx in (-HORN_LEN / 2 + 3, HORN_LEN / 2 - 3):
    shoulder = shoulder.cut(zcyl(hx, 0, 0.75, RAIL_TOP, RAIL_TOP + HORN_DEPTH + 3))

# back cover: clamps servo 2 in place, carries the rear pivot boss
cover = slab(tower_sk, S2_BOTTOM_Y, Y_COVER_BACK, ch=0.6)
cover = cover.union(ycyl(0, PIVOT_Z, 5.0, Y_COVER_BACK - 0.5, Y_BOSS_BACK))
cover = cover.cut(ycyl(0, PIVOT_Z, M3_PILOT / 2, S2_BOTTOM_Y + 0.6, Y_BOSS_BACK + 1))
for cx, cz in cover_screws:
    cover = cover.cut(ycyl(cx, cz, M3_CLEAR / 2, S2_BOTTOM_Y - 1, Y_COVER_BACK + 1))
    cover = cover.cut(ycyl(cx, cz, 3.1, Y_COVER_BACK - 1.8, Y_COVER_BACK + 1))
cover = cover.cut(cube(-3.5, 3.5, S2_BOTTOM_Y - 1, Y_COVER_BACK + 1, PLATTER_TOP - 1, PLATTER_TOP + 2.5))  # cable

# link: two plates around the tower, joined by a bridge at the tip
link_sk = cq.Sketch().arc((0, PIVOT_Z), LINK_R0, 0, 360).arc((0, PIVOT_Z + LINK_LEN), LINK_R1, 0, 360).hull()
a, v0, v1 = 7.5, PIVOT_Z + 21, PIVOT_Z + 70
truss = box(-a, v0, a, v1).difference(LineString([(-a, v0), (a, v1)]).buffer(2.6, cap_style=2))
windows = rounded_polys(sorted(getattr(truss, "geoms", [truss]), key=lambda g: g.area)[-2:], 2.2)
bridge_sk = (cq.Sketch().push([(0, PIVOT_Z + LINK_LEN - 8)]).rect(2 * LINK_R1 - 1, 16).reset().vertices().fillet(3)
             .reset().push([(0, PIVOT_Z + LINK_LEN)]).circle(LINK_R1).reset())
bridge_screws = [(sx * 5.0, PIVOT_Z + LINK_LEN - 5) for sx in (-1, 1)]

front = slab(link_sk, Y_LINK_FRONT_OUT, Y_LINK_FRONT_IN, ch=0.8)
front = front.union(slab(bridge_sk, Y_LINK_FRONT_IN - 0.5, Y_LINK_BACK_IN))
front = front.cut(slab(windows, Y_LINK_FRONT_OUT - 1, Y_LINK_FRONT_IN + 1))
horn2 = (cq.Workplane("XZ", origin=(0, Y_LINK_FRONT_IN + 1, 0)).center(0, PIVOT_Z)
         .slot2D(HORN_LEN + 0.6, HORN_W + 0.4, angle=90).extrude(HORN_DEPTH + 1))  # horn along the link
front = front.cut(horn2).cut(ycyl(0, PIVOT_Z, 2.6, Y_LINK_FRONT_OUT - 1, Y_LINK_FRONT_IN + 1))
front = front.cut(ycyl(0, PIVOT_Z, CAP_D / 2 + 0.15, Y_LINK_FRONT_OUT - 1, Y_LINK_FRONT_OUT + CAP_T))
for hx in (-HORN_LEN / 2 + 3, HORN_LEN / 2 - 3):
    front = front.cut(ycyl(0, PIVOT_Z + hx, 0.75, Y_LINK_FRONT_IN - HORN_DEPTH - 2.5, Y_LINK_FRONT_IN))
for bx, bz in bridge_screws:
    front = front.cut(ycyl(bx, bz, M3_PILOT / 2, Y_LINK_BACK_IN - 10, Y_LINK_BACK_IN + 1))

back = slab(link_sk, Y_LINK_BACK_IN, Y_LINK_BACK_OUT, ch=0.8)
back = back.cut(slab(windows, Y_LINK_BACK_IN - 1, Y_LINK_BACK_OUT + 1))
back = back.cut(ycyl(0, PIVOT_Z, M3_CLEAR / 2, Y_LINK_BACK_IN - 1, Y_LINK_BACK_OUT + 1))
back = back.cut(ycyl(0, PIVOT_Z, 3.2, Y_LINK_BACK_OUT - 2.2, Y_LINK_BACK_OUT + 1))
for bx, bz in bridge_screws:
    back = back.cut(ycyl(bx, bz, M3_CLEAR / 2, Y_LINK_BACK_IN - 1, Y_LINK_BACK_OUT + 1))
    back = back.cut(ycyl(bx, bz, 3.2, Y_LINK_BACK_OUT - 2.2, Y_LINK_BACK_OUT + 1))

# hub cap with the logo, presses into the front of the pivot and hides the horn screw
cap_flat = cq.Workplane("XY").circle(CAP_D / 2).extrude(CAP_T).faces(">Z").chamfer(0.4)
logo_flat = extrude_geom(logo_shape(LOGO_W), LOGO_H, CAP_T)


def cap_to_world(part):
    return part.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, Y_LINK_FRONT_OUT + CAP_T, PIVOT_Z))


cap, logo = cap_to_world(cap_flat), cap_to_world(logo_flat)


def servo_dummy():
    body = cube(-S_L / 2, S_L / 2, -S_W / 2, S_W / 2, 0, S_TOP)
    tabs = cube(-S_TAB_LEN / 2, S_TAB_LEN / 2, -S_W / 2, S_W / 2, S_TAB, S_TAB + S_TAB_T)
    dome = zcyl(S_L / 2 - S_OFF, 0, 5.8, S_TOP, S_TOP + 4)
    spline = zcyl(S_L / 2 - S_OFF, 0, 2.4, S_TOP + 4, S_H)
    horn = cq.Workplane("XY", origin=(0, 0, HORN_SEAT + 0.1)).center(S_L / 2 - S_OFF, 0).slot2D(HORN_LEN, HORN_W).extrude(1.6)
    return body.union(tabs).union(dome).union(spline).union(horn).translate((-(S_L / 2 - S_OFF), 0, 0))


servo1 = servo_dummy().translate((0, 0, SERVO1_Z))
servo2 = (servo_dummy().rotate((0, 0, 0), (0, 0, 1), 90).rotate((0, 0, 0), (1, 0, 0), 90)
          .translate((0, S2_BOTTOM_Y, PIVOT_Z)))
pi = cube(pi_x0, pi_x1, pi_y0, pi_y1, pi_z0, pi_top)
pi = pi.union(cube(pi_x0 + 1, pi_x1 - 1, pi_y1 - 21, pi_y1 + 2, pi_top, pi_top + PI_PORT_H))  # usb + ethernet stacks
pi = pi.union(cube(pi_x0 + 12, pi_x0 + 42, pi_y0 + 22, pi_y0 + 60, pi_top, pi_top + 12))     # active cooler
pi = pi.union(cube(pi_x1 - 7, pi_x1 + 1, pi_y0 + PI_USBC_U - 4.5, pi_y0 + PI_HDMI_U[1] + 4, pi_top, pi_top + 3.3))
pi = pi.union(cube(pi_x0, pi_x0 + 5, pi_y0 + 7, pi_y0 + 58, pi_top, pi_top + 8.5))         # gpio header

PARTS = {"tray": tray, "base": base, "shoulder": shoulder, "cover": cover, "link_front": front, "link_back": back, "cap": cap, "cap_logo": logo}
MOVING = {"link_front", "link_back", "cap", "cap_logo"}


def posed(name, angle):
    part = PARTS[name]
    return part.rotate((0, 0, PIVOT_Z), (0, 1, PIVOT_Z), angle) if name in MOVING else part


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*"):
        f.unlink()
    grey, dark = cq.Color(0.86, 0.86, 0.84), cq.Color(0.12, 0.12, 0.13)
    assy = cq.Assembly(name="wave_arm")
    for name, part in PARTS.items():
        assy.add(part, name=name, color=dark if name == "cap_logo" else grey)
        cq.exporters.export(part, str(OUT / f"{name}.step"))
    assy.add(servo1, name="servo_base", color=cq.Color(0.15, 0.25, 0.55))
    assy.add(servo2, name="servo_shoulder", color=cq.Color(0.15, 0.25, 0.55))
    assy.add(pi, name="raspberry_pi_5", color=cq.Color(0.1, 0.35, 0.15))
    assy.export(str(OUT / "wave_arm_assembly.step"))

    # print orientation: rotating +90 about x puts the lowest-y face on the bed
    printable = {
        "tray": tray,
        "base": base,
        "shoulder": shoulder,
        "cover": cover.rotate((0, 0, 0), (1, 0, 0), 90),
        "link_front": front.rotate((0, 0, 0), (1, 0, 0), 90),
        "link_back": back.rotate((0, 0, 0), (1, 0, 0), 90),
        "cap": cap_flat,
        "cap_logo": logo_flat,
        "cap_onepiece": cap_flat.union(logo_flat),
    }
    for name, part in printable.items():
        bb = part.val().BoundingBox()
        part = part.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(part, str(OUT / f"{name}.stl"), tolerance=0.02, angularTolerance=0.1)
    print(f"pivot {PIVOT_Z:.1f} mm, tip {PIVOT_Z + LINK_LEN + LINK_R1:.1f} mm, platter top {PLATTER_TOP:.1f} mm")
