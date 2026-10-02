import json
import math
from pathlib import Path

import cadquery as cq
from shapely.affinity import scale, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).parent
OUT = HERE / "print"

# MG90S micro servo. measure yours with calipers and fix these first
S_L, S_W = 22.8, 12.4    # body length, width
S_TAB = 16.0             # bottom of body to underside of tabs
S_TAB_T = 2.5
S_TOP = 22.5             # bottom of body to top face of body
S_H = 31.5               # bottom of body to top of the output spline
S_TAB_LEN = 32.5
S_OFF = 6.0              # body end to centre of output shaft
S_HOLES = 27.8
FIT = 0.4
HORN_LEN, HORN_W, HORN_DEPTH = 31.0, 6.4, 2.0
HORN_SEAT = S_H - 1.2

# Raspberry Pi 5
PI_L, PI_W, PI_T = 85.0, 56.0, 1.6
PI_HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
PI_USBC_U, PI_HDMI_U = 11.2, (25.8, 39.2)
PI_PORT_H = 16.5
PI_STANDOFF = 4.0

R = 57.0                 # base radius, every band
WALL = 3.0
TRAY_H, TRAY_FLOOR = 30.0, 2.4
LID_T = 4.0
PLATTER_T = 6.0
TOWER_R = 15.0
L1, L2 = 95.0, 85.0      # shoulder to elbow, elbow to tip
PLATE_T = 5.0
CAP_D, CAP_T = 20.0, 1.6
LOGO_W, LOGO_H = 14.0, 0.6
M3_CLEAR, M3_PILOT, M2_PILOT = 3.4, 2.6, 1.8

DECK = TRAY_H + LID_T
SERVO1_Z = DECK + 0.5                  # servo 1 stands on the drum floor
RAIL_TOP = SERVO1_Z + HORN_SEAT        # platter rides on the light ring here
DRUM_TOP = RAIL_TOP - 0.8              # the glowing gap
PLATTER_TOP = RAIL_TOP + PLATTER_T
PZ = PLATTER_TOP + 24.5                # shoulder axis height
EZ = PZ + L1                           # elbow axis height (arm straight up)

# the arm is drawn with its joint axes along y (servo splines point to -y), then turned 90 degrees
# so the axes run along x and the joints tilt forward/back
Y_S2 = 12.0                            # shoulder servo bottom
Y_UFI = Y_S2 - HORN_SEAT               # upper arm front plate, inner face
Y_UFO = Y_UFI - PLATE_T
Y_COVER = Y_S2 + 5.0                  # thick enough that every screw can be M3x10
Y_BOSS = Y_S2 + 7.0
Y_UBI = Y_BOSS + 0.5                   # upper arm back plate
Y_UBO = Y_UBI + PLATE_T
Y_S3 = Y_UFO + HORN_SEAT               # elbow servo bottom, its horn sits on the upper front plate
Y_FFI = Y_UFO - 0.5                    # forearm front plate
Y_FFO = Y_FFI - PLATE_T
Y_FBI = Y_UBO + 0.5                    # forearm back plate
Y_FBO = Y_FBI + PLATE_T


def ycyl(x, z, r, y1, y2):
    return cq.Workplane("XZ", origin=(0, y2, 0)).center(x, z).circle(r).extrude(y2 - y1)


def zcyl(x, y, r, z1, z2):
    return cq.Workplane("XY", origin=(0, 0, z1)).center(x, y).circle(r).extrude(z2 - z1)


def cube(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def slab(sketch, y1, y2, ch=0.0):
    """Extrude a sketch drawn in (x, z) between y1 < y2."""
    s = cq.Workplane("XY").workplane(offset=-y2).placeSketch(sketch).extrude(y2 - y1)
    if ch:
        s = s.faces(">Z").chamfer(ch).faces("<Z").chamfer(ch)
    return s.rotate((0, 0, 0), (1, 0, 0), 90)


def poly_sketch(polys, r):
    sk = cq.Sketch()
    for p in polys:
        sk = sk.push([(0, 0)]).polygon(list(p.exterior.coords)).reset()
    return sk.vertices().fillet(r).reset()


def extrude_geom(geom, h, z0=0.0):
    out = None
    for p in getattr(geom, "geoms", [geom]):
        solid = cq.Workplane("XY").workplane(offset=z0).polyline(list(p.exterior.coords)[:-1]).close().extrude(h)
        for hole in p.interiors:
            solid = solid.cut(cq.Workplane("XY").workplane(offset=z0 - 1).polyline(list(hole.coords)[:-1]).close().extrude(h + 2))
        out = solid if out is None else out.union(solid)
    return out


def logo_shape(width):
    data = json.loads((HERE / "logo.json").read_text())
    g = unary_union([Polygon(p).buffer(0) for p in data["polys"]] + [Point(x, y).buffer(r, 32) for x, y, r in data["circles"]])
    minx, miny, maxx, maxy = g.bounds
    k = width / (maxx - minx)
    g = scale(g, k, -k, origin=(0, 0))
    minx, miny, maxx, maxy = g.bounds
    return translate(g, -(minx + maxx) / 2, -(miny + maxy) / 2)


def truss(z0, z1, a, strut=2.6):
    t = box(-a, z0, a, z1).difference(LineString([(-a, z0), (a, z1)]).buffer(strut, cap_style=2))
    return sorted(getattr(t, "geoms", [t]), key=lambda g: g.area)[-2:]


def servo_pocket(part, cz_spline, y_bottom, open_back=True, dome_depth=4.2):
    """Cut a pocket for a servo whose spline points to -y at height cz_spline, bottom face at y_bottom."""
    cz = cz_spline - (S_L / 2 - S_OFF)
    th = S_TAB_LEN / 2
    back = y_bottom + (30 if open_back else 0)
    part = part.cut(cube(-S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, y_bottom - S_TAB - S_TAB_T - 0.1, back, cz - th - FIT, cz + th + FIT))
    part = part.cut(cube(-S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, y_bottom - S_TOP - 0.2, y_bottom, cz - S_L / 2 - FIT / 2, cz + S_L / 2 + FIT / 2))
    part = part.cut(ycyl(0, cz_spline, 6.3, y_bottom - S_TOP - dome_depth, y_bottom - S_TOP + 1))  # gear dome + spline
    return part


# ---- base: three bands of one round column
tray = zcyl(0, 0, R, 0, TRAY_H).faces(">Z").chamfer(0.8).faces("<Z").chamfer(0.6)
tray = tray.cut(zcyl(0, 0, R - WALL, TRAY_FLOOR, TRAY_H + 1))
boss_pts = [((R - 7) * math.cos(math.radians(a)), (R - 7) * math.sin(math.radians(a))) for a in (45, 135, 225, 315)]
for bx, by in boss_pts:
    tray = tray.union(zcyl(bx, by, 4.2, 0, TRAY_H).union(
        cube(bx - 1, bx + 1, by - 1, by + 1, 0, TRAY_H).translate((math.copysign(3, bx), math.copysign(3, by), 0))))
    tray = tray.cut(zcyl(bx, by, M3_CLEAR / 2, -1, TRAY_H + 1)).cut(zcyl(bx, by, 3.0, -1, TRAY_H - 6.5))
tray = tray.intersect(zcyl(0, 0, R, -1, TRAY_H + 1).faces(">Z").chamfer(0.8).faces("<Z").chamfer(0.6))

# pi lies with its long side along x. usb-c faces the back (+y) so the only cable leaves out the back,
# the usb-a / ethernet / hdmi ports stay hidden inside (it runs over wifi)
pi_x0, pi_x1 = -44.5, -44.5 + PI_L
pi_y1, pi_y0 = 29.0, 29.0 - PI_W
pi_z0 = TRAY_FLOOR + PI_STANDOFF
pi_top = pi_z0 + PI_T
for u, v in PI_HOLES:
    hx, hy = pi_x0 + u, pi_y1 - v
    tray = tray.union(zcyl(hx, hy, 3.0, TRAY_FLOOR - 0.5, pi_z0)).union(zcyl(hx, hy, 1.15, pi_z0, pi_z0 + PI_T + 1.2))  # pi drops onto pegs, no screws
usbc_x, usbc_z = pi_x0 + PI_USBC_U, pi_top + 1.6
tray = tray.cut(cq.Workplane("XZ", origin=(0, R + 2, 0)).center(usbc_x, usbc_z).slot2D(13.0, 7.0).extrude(R))  # the one port
holes = None
for row, z in enumerate((9.0, 15.0, 21.0)):
    for i in range(52):
        a = i * 360 / 52 + (360 / 104 if row == 1 else 0)
        a_n = (a + 180) % 360 - 180
        if 112 < a_n < 142 or any(abs((a_n - b + 180) % 360 - 180) < 7 for b in (45, 135, -135, -45)):
            continue
        d = cq.Vector(math.cos(math.radians(a)), math.sin(math.radians(a)), 0)
        hole = cq.Solid.makeCylinder(1.5, 8, cq.Vector(0, 0, z) + d * (R - WALL - 2), d)
        holes = hole if holes is None else holes.fuse(hole)
tray = tray.cut(cq.Workplane().add(holes))
for i in range(7):
    tray = tray.cut(cq.Workplane("XY", origin=(0, 0, -1)).center(pi_x0 + 20 + i * 6.5, (pi_y0 + pi_y1) / 2).slot2D(40, 2.6, angle=90).extrude(TRAY_FLOOR + 2))
for a in (0, 90, 180, 270):
    tray = tray.cut(zcyl(44 * math.cos(math.radians(a)), 44 * math.sin(math.radians(a)), 5.2, -1, 1.0))

# drum: lid of the tray, holds servo 1, its top edge carries the light ring
drum = zcyl(0, 0, R, TRAY_H, DRUM_TOP).faces(">Z").chamfer(0.8).faces("<Z").chamfer(0.8)
drum = drum.cut(zcyl(0, 0, R - WALL, DECK, 400))
drum = drum.cut(zcyl(0, 0, R - 1.4, DRUM_TOP - 2.5, 400))  # rabbet for the ring, open to the inside so an led can light it
drum = drum.cut(zcyl(0, 0, R + 1, DECK + 1, DECK + 1.8).cut(zcyl(0, 0, R - 0.9, DECK + 1, DECK + 1.8)))  # shadow line
s1_cx = -(S_L / 2 - S_OFF)
ledge = SERVO1_Z + S_TAB
th = S_TAB_LEN / 2
cradle = cube(s1_cx - th - 3, s1_cx + th + 3, -S_W / 2 - 3, S_W / 2 + 3, DECK - 0.5, ledge)
cradle = cradle.cut(cube(s1_cx - S_L / 2 - FIT / 2, s1_cx + S_L / 2 + FIT / 2, -S_W / 2 - FIT / 2, S_W / 2 + FIT / 2, DECK, 400))
cradle = cradle.cut(cube(s1_cx - th - 4, s1_cx - S_L / 2, -3, 3, DECK, ledge + 1))
for hx in (s1_cx - S_HOLES / 2, s1_cx + S_HOLES / 2):
    cradle = cradle.cut(zcyl(hx, 0, M2_PILOT / 2, ledge - 8, ledge + 1))
drum = drum.union(cradle)
drum = drum.cut(zcyl(-20.0, -34.0, 6.0, TRAY_H - 1, DECK + 1))  # wires down to the gpio header
for bx, by in boss_pts:
    drum = drum.cut(zcyl(bx, by, M3_PILOT / 2, TRAY_H - 1, TRAY_H + 3.6))

ring = zcyl(0, 0, R - 1.6, DRUM_TOP - 2.4, RAIL_TOP).cut(zcyl(0, 0, R - WALL - 0.2, DRUM_TOP - 3, RAIL_TOP + 1))

# ---- shoulder: platter + tower, drawn in arm coordinates
platter = zcyl(0, 0, R, RAIL_TOP, PLATTER_TOP).faces(">Z").chamfer(1.2).faces("<Z").chamfer(0.5)
platter = platter.cut(cq.Workplane("XY", origin=(0, 0, RAIL_TOP - 1)).slot2D(HORN_LEN + 0.6, HORN_W + 0.4).extrude(HORN_DEPTH + 1))
platter = platter.cut(zcyl(0, 0, 4.0, RAIL_TOP - 1, RAIL_TOP + HORN_DEPTH + 2.5))
tower2d = unary_union([box(-TOWER_R, PLATTER_TOP - 1, TOWER_R, PZ), Point(0, PZ).buffer(TOWER_R, 64),
                       box(-TOWER_R - 6, PLATTER_TOP - 1, TOWER_R + 6, PLATTER_TOP)]).buffer(4, 32).buffer(-4, 32)
tower2d = tower2d.intersection(box(-50, PLATTER_TOP - 0.5, 50, 400))
tower = extrude_geom(tower2d, S_TOP, 0).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, Y_S2, 0))
tower = tower.union(ycyl(0, PZ, 9.0, Y_S2 - S_TOP - 4.5, Y_S2 - S_TOP + 0.5).faces("<Y").chamfer(0.6))
tower = servo_pocket(tower, PZ, Y_S2, dome_depth=10)
cover_screws = [(sx * 11.0, PZ - 14.0) for sx in (-1, 1)]
for cx, cz in cover_screws:
    tower = tower.cut(ycyl(cx, cz, M3_PILOT / 2, Y_S2 - 10, Y_S2 + 1))
shoulder = platter.union(tower)
shoulder = shoulder.cut(zcyl(0, 0, 2.1, RAIL_TOP - 1, PZ + TOWER_R + 1))  # screwdriver for servo 1's horn screw
s2_cz = PZ - (S_L / 2 - S_OFF)
shoulder = shoulder.cut(cube(-3.5, 3.5, Y_S2 - 7.5, Y_S2 - 2.0, RAIL_TOP - 1, s2_cz - th))   # shoulder servo cable
shoulder = shoulder.cut(cube(TOWER_R + 3, TOWER_R + 11, -3, 3, RAIL_TOP - 1, PLATTER_TOP + 1).edges("|Z").fillet(1.5))  # elbow servo cable
for hx in (-HORN_LEN / 2 + 3, HORN_LEN / 2 - 3):
    shoulder = shoulder.cut(zcyl(hx, 0, 0.75, RAIL_TOP, RAIL_TOP + HORN_DEPTH + 3))

tower_sk = cq.Sketch().push([(0, (PLATTER_TOP + PZ) / 2 + 2)]).rect(2 * TOWER_R, PZ - PLATTER_TOP - 4).reset().push([(0, PZ)]).circle(TOWER_R).reset()
cover = slab(tower_sk, Y_S2, Y_COVER, ch=0.6)
cover = cover.union(ycyl(0, PZ, 5.0, Y_COVER - 0.5, Y_BOSS))
cover = cover.cut(ycyl(0, PZ, M3_PILOT / 2, Y_S2 + 0.6, Y_BOSS + 1))
for cx, cz in cover_screws:
    cover = cover.cut(ycyl(cx, cz, M3_CLEAR / 2, Y_S2 - 1, Y_COVER + 1)).cut(ycyl(cx, cz, 3.1, Y_COVER - 1.8, Y_COVER + 1))

# ---- upper arm: two plates around the shoulder tower, elbow servo housed between them at the top
up_sk = cq.Sketch().arc((0, PZ), 16.0, 0, 360).arc((0, EZ), 15.0, 0, 360).hull()
up_win = poly_sketch(truss(PZ + 22, EZ - 36, 7.5), 2.2)
s3_cz = EZ - (S_L / 2 - S_OFF)
house_z0 = EZ - 33.0
house2d = unary_union([Point(0, EZ).buffer(15.0, 64), box(-14.0, house_z0, 14.0, EZ)])
elbow_screws = [(sx * 7.0, EZ - 28.0) for sx in (-1, 1)]

up_front = slab(up_sk, Y_UFO, Y_UFI, ch=0.8)
up_front = up_front.cut(slab(up_win, Y_UFO - 1, Y_UFI + 1))
housing = extrude_geom(house2d.buffer(-0.01), Y_UBI - (Y_UFI - 0.5), 0).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, Y_UBI, 0))
up_front = up_front.union(housing)
up_front = servo_pocket(up_front, EZ, Y_S3)
up_front = up_front.cut(ycyl(0, EZ, 2.8, Y_UFO - 1, Y_UFI + 1))                       # elbow spline through the plate
up_front = up_front.cut(cube(-3.5, 3.5, Y_S3 - 8, Y_S3 + 2.5, house_z0 - 1, s3_cz - S_TAB_LEN / 2))   # elbow servo cable
up_front = up_front.cut(cq.Workplane("XZ", origin=(0, Y_UFI + 1, 0)).center(0, PZ)
                        .slot2D(HORN_LEN + 0.6, HORN_W + 0.4, angle=90).extrude(HORN_DEPTH + 1))  # shoulder horn
up_front = up_front.cut(ycyl(0, PZ, 2.6, Y_UFO - 1, Y_UFI + 1))
up_front = up_front.cut(ycyl(0, PZ, CAP_D / 2 + 0.15, Y_UFO - 1, Y_UFO + CAP_T))
for hz in (-HORN_LEN / 2 + 3, HORN_LEN / 2 - 3):
    up_front = up_front.cut(ycyl(0, PZ + hz, 0.75, Y_UFI - HORN_DEPTH - 2.5, Y_UFI))
for ex, ez in elbow_screws:
    up_front = up_front.cut(ycyl(ex, ez, M3_PILOT / 2, Y_UBI - 10, Y_UBI + 1))

up_back = slab(up_sk, Y_UBI, Y_UBO, ch=0.8)
up_back = up_back.cut(slab(up_win, Y_UBI - 1, Y_UBO + 1))
up_back = up_back.union(cube(-5, 5, Y_S3 + 0.2, Y_UBI + 0.5, s3_cz - 8, s3_cz + 8))   # pad that clamps the elbow servo
up_back = up_back.cut(ycyl(0, PZ, M3_CLEAR / 2, Y_UBI - 1, Y_UBO + 1)).cut(ycyl(0, PZ, 3.2, Y_UBO - 2.2, Y_UBO + 1))
up_back = up_back.cut(ycyl(0, EZ, M3_PILOT / 2, Y_S3 + 1.5, Y_UBO + 1))             # elbow pivot screw threads in here
for ex, ez in elbow_screws:
    up_back = up_back.cut(ycyl(ex, ez, M3_CLEAR / 2, Y_UBI - 1, Y_UBO + 1)).cut(ycyl(ex, ez, 3.2, Y_UBO - 2.2, Y_UBO + 1))

# ---- forearm: two plates outside the upper arm, joined at the tip
TZ = EZ + L2
fo_sk = cq.Sketch().arc((0, EZ), 15.0, 0, 360).arc((0, TZ), 9.0, 0, 360).hull()
fo_win = poly_sketch(truss(EZ + 21, TZ - 22, 6.0, 2.3), 2.0)
tip2d = unary_union([Point(0, TZ).buffer(9.0, 64), box(-9.6, TZ - 14, 9.6, TZ)])
tip_screws = [(0, TZ - 8.0), (0, TZ + 1.5)]

fo_front = slab(fo_sk, Y_FFO, Y_FFI, ch=0.8)
fo_front = fo_front.cut(slab(fo_win, Y_FFO - 1, Y_FFI + 1))
fo_front = fo_front.union(extrude_geom(tip2d, Y_FBI - (Y_FFI - 0.5), 0).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, Y_FBI, 0)))
fo_front = fo_front.cut(cq.Workplane("XZ", origin=(0, Y_FFI + 1, 0)).center(0, EZ)
                        .slot2D(HORN_LEN + 0.6, HORN_W + 0.4, angle=90).extrude(HORN_DEPTH + 1))
fo_front = fo_front.cut(ycyl(0, EZ, 2.6, Y_FFO - 1, Y_FFI + 1))
fo_front = fo_front.cut(ycyl(0, EZ, CAP_D / 2 + 0.15, Y_FFO - 1, Y_FFO + CAP_T))
for hz in (-HORN_LEN / 2 + 3, HORN_LEN / 2 - 3):
    fo_front = fo_front.cut(ycyl(0, EZ + hz, 0.75, Y_FFI - HORN_DEPTH - 2.5, Y_FFI))
for tx, tz in tip_screws:
    fo_front = fo_front.cut(ycyl(tx, tz, M3_PILOT / 2, Y_FBI - 10, Y_FBI + 1))

fo_back = slab(fo_sk, Y_FBI, Y_FBO, ch=0.8)
fo_back = fo_back.cut(slab(fo_win, Y_FBI - 1, Y_FBO + 1))
fo_back = fo_back.cut(ycyl(0, EZ, M3_CLEAR / 2, Y_FBI - 1, Y_FBO + 1)).cut(ycyl(0, EZ, 3.2, Y_FBO - 2.2, Y_FBO + 1))
for tx, tz in tip_screws:
    fo_back = fo_back.cut(ycyl(tx, tz, M3_CLEAR / 2, Y_FBI - 1, Y_FBO + 1)).cut(ycyl(tx, tz, 3.2, Y_FBO - 2.2, Y_FBO + 1))

# ---- hub caps: logo on the shoulder, plain on the elbow
cap_flat = cq.Workplane("XY").circle(CAP_D / 2).extrude(CAP_T).faces(">Z").chamfer(0.4)
cap_flat = cap_flat.cut(cq.Workplane("XY", origin=(0, 0, CAP_T - 0.3)).circle(CAP_D / 2 - 1.6).circle(CAP_D / 2 - 2.2).extrude(1))
logo_flat = extrude_geom(logo_shape(LOGO_W), LOGO_H, CAP_T)


def cap_at(part, y_face, z):
    return part.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y_face + CAP_T, z))


cap_s, logo_s = cap_at(cap_flat, Y_UFO, PZ), cap_at(logo_flat, Y_UFO, PZ)
cap_e = cap_at(cap_flat, Y_FFO, EZ)


def servo_dummy():
    body = cube(-S_L / 2, S_L / 2, -S_W / 2, S_W / 2, 0, S_TOP)
    tabs = cube(-S_TAB_LEN / 2, S_TAB_LEN / 2, -S_W / 2, S_W / 2, S_TAB, S_TAB + S_TAB_T)
    dome = zcyl(S_L / 2 - S_OFF, 0, 5.8, S_TOP, S_TOP + 4)
    spline = zcyl(S_L / 2 - S_OFF, 0, 2.4, S_TOP + 4, S_H)
    horn = cq.Workplane("XY", origin=(0, 0, HORN_SEAT + 0.1)).center(S_L / 2 - S_OFF, 0).slot2D(HORN_LEN, HORN_W).extrude(1.6)
    return body.union(tabs).union(dome).union(spline).union(horn).translate((-(S_L / 2 - S_OFF), 0, 0))


def arm_servo(y_bottom, z_spline):
    return (servo_dummy().rotate((0, 0, 0), (0, 0, 1), 90).rotate((0, 0, 0), (1, 0, 0), 90)
            .rotate((0, 0, 0), (0, 1, 0), 0).translate((0, y_bottom, z_spline)))


servo1 = servo_dummy().translate((0, 0, SERVO1_Z))
servo2 = arm_servo(Y_S2, PZ)
servo3 = arm_servo(Y_S3, EZ)
pi = cube(pi_x0, pi_x1, pi_y0, pi_y1, pi_z0, pi_top)
pi = pi.union(cube(pi_x1 - 21, pi_x1 + 2.5, pi_y0 + 1, pi_y1 - 1, pi_top, pi_top + PI_PORT_H))   # usb + ethernet stacks
pi = pi.union(cube(pi_x0 + 22, pi_x0 + 60, pi_y0 + 12, pi_y0 + 42, pi_top, pi_top + 12))        # active cooler
pi = pi.union(cube(pi_x0 + PI_USBC_U - 4.5, pi_x0 + PI_HDMI_U[1] + 4, pi_y1 - 7, pi_y1 + 1, pi_top, pi_top + 3.3))
pi = pi.union(cube(pi_x0 + 7, pi_x0 + 58, pi_y0, pi_y0 + 5, pi_top, pi_top + 8.5))            # gpio header

# which parts move with which joint. arm parts are turned 90 degrees so the joints tilt forward/back
BASE = {"tray": tray, "drum": drum, "ring": ring}
ARM = {"shoulder": shoulder, "cover": cover, "up_front": up_front, "up_back": up_back, "cap_s": cap_s, "logo_s": logo_s,
       "fo_front": fo_front, "fo_back": fo_back, "cap_e": cap_e}
UPPER = {"up_front", "up_back", "cap_s", "logo_s", "servo3"}
FORE = {"fo_front", "fo_back", "cap_e"}
PARTS = {**BASE, **ARM}


def posed(name, part, yaw=0.0, shoulder_a=0.0, elbow_a=0.0):
    """Joint angles in degrees. shoulder/elbow positive = tilt forward, 0 = straight up."""
    if name in BASE or name in ("pi", "servo1"):
        return part
    if name in FORE:
        part = part.rotate((0, 0, EZ), (0, 1, EZ), -elbow_a)
    if name in FORE or name in UPPER:
        part = part.rotate((0, 0, PZ), (0, 1, PZ), -shoulder_a)
    return part.rotate((0, 0, 0), (0, 0, 1), 90 + yaw)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    grey, dark, glow = cq.Color(0.86, 0.86, 0.84), cq.Color(0.12, 0.12, 0.13), cq.Color(0.98, 0.97, 0.92)
    assy = cq.Assembly(name="arm3")
    for name, part in PARTS.items():
        p = posed(name, part)
        assy.add(p, name=name, color=dark if name == "logo_s" else glow if name == "ring" else grey)
        cq.exporters.export(p, str(OUT / f"{name}.step"))
    for name, part in (("servo_base", servo1), ("servo_shoulder", servo2), ("servo_elbow", servo3)):
        assy.add(posed("servo3" if name == "servo_elbow" else "pi" if name == "servo_base" else "up_front", part),
                 name=name, color=cq.Color(0.15, 0.25, 0.55))
    assy.add(pi, name="raspberry_pi_5", color=cq.Color(0.1, 0.35, 0.15))
    assy.export(str(OUT / "arm3_assembly.step"))

    flat = lambda p, a=90: p.rotate((0, 0, 0), (1, 0, 0), a)   # +90 puts the lowest-y face on the bed
    printable = {"tray": tray, "drum": drum, "ring": ring, "shoulder": shoulder, "cover": flat(cover),
                 "up_front": flat(up_front), "up_back": flat(up_back, -90), "fo_front": flat(fo_front), "fo_back": flat(fo_back),
                 "cap_shoulder": cap_flat, "cap_shoulder_logo": logo_flat, "cap_elbow": cap_flat}
    for name, part in printable.items():
        bb = part.val().BoundingBox()
        part = part.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(part, str(OUT / f"{name}.stl"), tolerance=0.02, angularTolerance=0.1)
    print(f"shoulder {PZ:.1f}  elbow {EZ:.1f}  tip {EZ + L2 + 9:.1f} mm (arm straight up), base {PLATTER_TOP:.1f} mm, dia {2 * R:.0f} mm")
