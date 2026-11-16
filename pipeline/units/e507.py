"""507 E Green, 1 bedroom Plan C, rebuilt on the kit.
    blender -b --python e507.py -- <out-dir> [views]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import math

import bmesh
from mathutils import Matrix

from kit import bake, bath, core, fixtures, kitchen, lights, view
from kit import furniture as f
from kit.core import at, box, cyl, mat, tag
from kit.shell import Shell
from kit.openings import door, window

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
core.reset()

H, H_BATH, H_ALC, EXT, CORR, PART, PLUMB = 106.0, 104.0, 88.0, 8.0, 6.0, 4.5, 6.5
W, XB, XBE, XK, BATH_W = 211.5, 100.0, 104.5, 81.5, 75.0
YS, Y_BS, Y_BS2, Y_ALC_S, Y_BATH_N, Y_BATH_S = 362.5, 130.0, 134.5, 165.0, 169.5, 285.5
ALC_X0, CL_X1, BCL_Y, BCL_X1 = 41.5, 111.5, 102.0, 54.0

s = Shell(H, wall_rgb=(226, 222, 213), floor="floor_wood", plank="v")
s.wall("wall_N", -EXT, W + EXT, -EXT, 0)
s.wall("wall_E", W, W + EXT, 0, YS + CORR)
s.wall("wall_S", XK - PLUMB, W, YS, YS + CORR)
s.wall("wall_W", -EXT, 0, 0, Y_BATH_S)
s.wall("wall_bath_S", -EXT, XK - PLUMB, Y_BATH_S, Y_BATH_S + CORR)
s.wall("wall_W_lower", XK - PLUMB, XK, Y_BATH_S, YS)
s.wall("partition", XB, XBE, 0, Y_BS2)
s.wall("bed_S", 0, XB, Y_BS, Y_BS2)
s.wall("bcloset_front", 0, BCL_X1, BCL_Y, BCL_Y + PART)
s.wall("bcloset_stub", BCL_X1, BCL_X1 + PART, BCL_Y, Y_BS)
s.wall("chase", 0, 15, Y_ALC_S, Y_BATH_N + 30)
s.wall("chase_alcove", 0, ALC_X0, Y_BS2, Y_ALC_S)
s.wall("alcove_tub", 15, BATH_W, Y_ALC_S, Y_BATH_N)
s.wall("bath_E", BATH_W, XK, Y_ALC_S, Y_BATH_S)
s.wall("closet_N", XK, CL_X1, Y_BATH_S, Y_BATH_S + PART)
s.wall("closet_E", CL_X1 - PART, CL_X1, Y_BATH_S + PART, YS)
s.wall("knee", 168, W, 185, 199, z1=41)
s.wall("alcove_header", ALC_X0, XK, Y_BS2, Y_ALC_S, z0=H_ALC)

s.room("bedroom", 0, XB, 0, BCL_Y)
s.room("bedroom", BCL_X1 + PART, XB, BCL_Y, Y_BS)
s.room("bedroom closet", 0, BCL_X1, BCL_Y + PART, Y_BS)
s.room("living", XBE, W, 0, 185)
s.room("laundry", ALC_X0, XK, Y_BS2, Y_ALC_S, ceiling=H_ALC)
s.room("kitchen", XK, W, Y_BS2, Y_BATH_S)
s.room("kitchen", CL_X1, W, Y_BATH_S, YS)
s.room("bath", 15, BATH_W, Y_BATH_N, Y_BATH_S, ceiling=H_BATH, ceiling_key="ceiling_tile")
s.room("bath", 0, 15, Y_BATH_N + 30, Y_BATH_S, ceiling=H_BATH, ceiling_key="ceiling_tile")
s.room("entry closet", XK, CL_X1 - PART, Y_BATH_S + PART, YS)

door(s, "door_bedroom", 102, 112, 30, swing="W", hinge="right", angle=92, room="bedroom")
door(s, "door_bath", 78, 224, 30, swing="W", hinge="left", angle=95, room="bath")
door(s, "door_entry", 135, YS + 3, 36, swing="N", hinge="right", thick=1.75, deadbolt=True, peephole=True, threshold=True, room="kitchen")
door(s, "door_closet", CL_X1 - 2, 334.5, 48, kind="double", swing="E", room="kitchen")
door(s, "door_bcloset", 27, BCL_Y + 2, 48, kind="bypass", swing="N", casing=(True, False), room="bedroom")
wl = window(s, "win_living", 166, -4, 47, 31, 49.5, top="arch", room="living")
wb = window(s, "win_bedroom", 75, -4, 42, 35, 46, top="arch", room="bedroom")

# ------------------------------------------------------------------ parts the kit does not have
GOLD, BLACK = (200, 165, 95), (20, 20, 21)


def deco(room):
    return tag(group="D", coll="furniture", room=room)


def turned(name, size, material, turn, pos, pivot=(0, 0, 0)):
    """Box of `size` (u, v, z) whose centre is `pivot` away from the point it is turned about, moved to `pos`."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=pivot, verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=turn)
    bmesh.ops.translate(bm, vec=pos, verts=bm.verts)
    return core.emit(name, bm, material)


def accent_wall(x, y, facing, length, room):
    """Geometric batten pattern on a wall, from the stile at plan (x, y) `length` along the wall to the right."""
    m, bw, st, k = mat("trim_paint"), 2.25, 4.5, 1.15
    zm = lambda u: 10.0 + k * (u - st)   # the long rising board

    def diag(name, ua, za, ub, zb):
        turned(name, (math.hypot(ub - ua, zb - za), 0.6, bw), m, Matrix.Rotation(-math.atan2(zb - za, ub - ua), 3, "Y"),
               ((ua + ub) / 2, 0.3, (za + zb) / 2))

    with tag(group="B", coll="trim", room=room), at(x, y, facing):
        box("batten_stile", 0, st, 0, 0.6, 5.25, H, m)
        ut = min(length - 0.5, st + (H - 1.5 - 10.0) / k)
        diag("batten_main", st, 10.0, ut, zm(ut))
        for z in (48.0, 54.0, 68.0, 82.0, 95.0):
            box("batten_rail", st, st + (z - 10.0) / k - 0.8, 0, 0.6, z - bw / 2, z + bw / 2, m)
        for zt, zb in ((H - 1.5, 95.0), (93.0, 82.0), (80.0, 68.0), (66.0, 54.0)):
            diag("batten_feather", st, zt - bw / 2, st + 10.5, zb + bw / 2)
        for ua, zb in ((58.0, 36.0), (74.0, 68.0)):
            diag("batten_chevron", ua, zm(ua) - 1.0, length - 0.5, zb)
        diag("batten_low", 30.0, zm(30.0) - 1.0, 58.0, 8.0)


def chiller(name, x, y, facing, width, depth, rgb, room):
    """Under-counter beverage chiller between two cabinets; (x, y) is its left back corner, as for kitchen parts."""
    st = mat("stainless")
    with tag(group="C", coll="kitchen", room=room), at(x, y, facing):
        box(name + "_kick", 0, width, 0, depth - 3, 0, 4, mat("cabinet_paint", rgb))
        box(name + "_body", 0.1, width - 0.1, 1, depth - 0.2, 4.0, 34.6, mat("appliance_black", (25, 25, 27)))
        box(name + "_frame", 0.2, width - 0.2, depth - 0.2, depth + 0.6, 4.2, 34.4, st)
        box(name + "_glass", 1.6, width - 1.6, depth + 0.6, depth + 0.7, 5.6, 33.0, mat("black_glass", (30, 32, 34)))
        box(name + "_handle", width - 1.5, width - 0.9, depth + 0.7, depth + 1.5, 10.0, 30.0, st)
        box(name + "_label", 2.5, width - 6, depth + 0.7, depth + 0.75, 24.0, 28.0, mat("plastic"))
        core.footprint(name, 0, width, 0, depth, 34.6)


def sprinkler(name, x, y, z, room):
    with tag(group="C", coll="fixtures", room=room):
        cyl(name + "_escutcheon", (x, y), z - 0.3, z, 1.2, mat("plastic"))
        cyl(name, (x, y), z - 1.4, z - 0.3, 0.35, mat("nickel"), seg=12)


def ceiling_grid(x0, x1, y0, y1, z, xs, ys, room):
    """T-bars of a lay-in tile ceiling at height z: bars at plan xs and ys, and the angle round the walls."""
    m = mat("plastic")
    with tag(group="C", coll="ceiling", room=room):
        for x in xs:
            box("tbar", x - 0.45, x + 0.45, y0, y1, z - 0.15, z, m)
        for y in ys:
            box("tbar", x0, x1, y - 0.45, y + 0.45, z - 0.15, z, m)
        for a, b, c, d in ((x0, x0 + 0.8, y0, y1), (x1 - 0.8, x1, y0, y1), (x0, x1, y1 - 0.8, y1), (x0, x1, y0, y0 + 0.8)):
            box("tbar_wall_angle", a, b, c, d, z - 0.15, z, m)


def mech(room):
    """Air handler hung over the water heater, a hall device over the electrical panel."""
    with tag(group="C", coll="fixtures", room=room):
        box("air_handler", XK + 1, CL_X1 - PART - 1, Y_BATH_S + PART + 1, Y_BATH_S + PART + 22, 62.0, 96.0, mat("stainless", (110, 110, 110)))
    with tag(group="C", coll="fixtures", room="kitchen"):
        box("hall_device", XK, XK + 1.6, 179.0, 183.0, 72.0, 76.5, mat("plastic"))


def closet_rod(name, x0, y0, x1, y1, z, room):
    """Hanging rod where it is not under the front edge of its shelf."""
    with tag(group="C", coll="fixtures", room=room):
        core.tube(name, [(x0, y0, z), (x1, y1, z)], 0.5, mat("plastic"), seg=12)


def bin_(name, x0, x1, y0, y1, z, h, room, label=False):
    """Black fabric storage bin or hamper standing at height z."""
    with deco(room):
        box(name, x0, x1, y0, y1, z, z + h, mat("fabric", (22, 22, 23)))
        if label:
            box(name + "_label", (x0 + x1) / 2 - 2, (x0 + x1) / 2 + 2, y0 - 0.05, y0, z + h - 3.5, z + h - 2.0, mat("nickel"))


def frame(name, x, y, facing, z, w, h, frame_m, rgb, inner=None, tilt=10.0, border=1.0, room=""):
    """Framed picture standing on a surface at height z and leaning back; (x, y) is the foot of its back."""
    lean = Matrix.Rotation(math.radians(tilt), 3, "X")
    with deco(room), at(x, y, facing):
        turned(name + "_frame", (w, 0.7, h), frame_m, lean, (0, 0.35, z), (0, 0, h / 2))
        turned(name, (w - 2 * border, 0.06, h - 2 * border), mat("plastic", rgb), lean, (0, 0.35, z), (0, 0.38, h / 2))
        if inner:
            turned(name + "_image", (w * 0.62, 0.06, w * 0.62), mat("plastic", inner), lean, (0, 0.35, z), (0, 0.42, h * 0.56))


def bike(name, x, y, z, room):
    """Gold wire bicycle ornament, standing along y."""
    g = mat("brass", GOLD)
    with deco(room), at(x, y):
        for dy in (-3.2, 3.2):
            core.tube(name + "_wheel", [(0, dy + 2.2 * math.sin(a), z + 2.4 + 2.2 * math.cos(a)) for a in (i * math.pi / 12 for i in range(25))], 0.12, g, seg=6)
        core.tube(name + "_frame", [(0, -3.2, z + 2.4), (0, -0.5, z + 2.6), (0, 0.5, z + 5.2), (0, -1.6, z + 5.4), (0, -3.2, z + 2.4)], 0.15, g, seg=6)
        core.tube(name + "_fork", [(0, 3.2, z + 2.4), (0, 2.4, z + 6.0), (0, 1.6, z + 6.2)], 0.15, g, seg=6)
        core.tube(name + "_bar", [(-1.5, 2.2, z + 6.2), (1.5, 2.2, z + 6.2)], 0.15, g, seg=6)
        box(name + "_seat", -0.4, 0.4, -2.2, -0.8, z + 5.4, z + 5.8, mat("leather", (110, 60, 40)))


def place_setting(name, x, y, z, room):
    """Round placemat, plate, bowl and cutlery (on the right, looking north)."""
    with deco(room), at(x, y):
        cyl(name + "_placemat", (0, 0), z, z + 0.2, 7.6, mat("fabric", (24, 24, 24)), seg=48)
        cyl(name + "_plate", (0, 0), z + 0.2, z + 0.75, 3.8, mat("porcelain", (238, 236, 230)), seg=48, r1=5.3)
        cyl(name + "_bowl", (0, 0), z + 0.65, z + 3.35, 2.0, mat("porcelain", BLACK), seg=48, r1=3.45)
        for k, w in enumerate((0.5, 0.45, 0.7)):
            box(name + "_cutlery", 7.0 + k * 1.1 - w / 2, 7.0 + k * 1.1 + w / 2, -3.8, 3.8, z + 0.2, z + 0.32, mat("chrome", (200, 200, 200)))


def pump_bottle(name, x, y, z, toward, body, room, r=1.25, h=4.6):
    """Soap dispenser on a surface at height z, its nozzle pointing `toward`."""
    with deco(room), at(x, y, toward):
        cyl(name, (0, 0), z, z + h, r, body, seg=16)
        cyl(name + "_pump", (0, 0), z + h, z + h + 1.4, 0.3, mat("nickel"), seg=12)
        box(name + "_nozzle", -0.2, 0.2, 0, 1.2, z + h + 1.0, z + h + 1.4, mat("nickel"))


def smalls():
    """Table-top things: glasses, crock, shakers, candle, toothbrushes, a book."""
    white, glass = mat("porcelain", (238, 236, 230)), mat("glass")
    with deco("kitchen"):
        for x, y in ((172.5, 191.0), (190.0, 191.5)):
            cyl("tumbler", (x, y), BAR_Z, BAR_Z + 5.5, 1.5, glass, r1=1.6)
        cyl("utensil_crock", (205.5, 266.5), 36, 42, 2.3, white, r1=2.4)
        for dx, dy in ((-0.6, -0.8), (0.4, 0.6), (0.0, 0.0)):
            cyl("utensil_handle", (205.5 + dx, 266.5 + dy), 37, 45.5, 0.3, mat("plastic", BLACK), seg=8)
            box("utensil_head", 205.3 + dx, 205.7 + dx, 265.8 + dy, 267.2 + dy, 45.3, 47.9, mat("plastic", BLACK))
        for y in (304.0, 306.5):
            cyl("shaker", (207.5, y), 36, 39, 0.75, white, seg=16)
    with deco("bedroom"):
        cyl("candle_jar", (6.75, 62.5), 29.5, 32.5, 1.5, mat("brass", (200, 175, 110)), r1=1.6)
        cyl("candle_wax", (6.75, 62.5), 32.5, 32.55, 1.4, mat("plastic", (238, 232, 215)))
    with deco("bath"):
        box("toothbrush_holder", 2.75, 5.25, 223.25, 225.75, 33.75, 37.75, mat("porcelain", BLACK))
        for dy, c in ((-0.5, (235, 235, 235)), (0.5, (200, 210, 220))):
            cyl("toothbrush", (4.0, 224.5 + dy), 37.25, 40.95, 0.18, mat("plastic", c), seg=8)
    with deco("living"):
        box("side_table_book", 190, 202, 103, 115, 5.0, 6.1, mat("plastic", (110, 40, 30)))


# ------------------------------------------------------------------ kitchen
R, GREIGE, BAR_Z = "kitchen", (178, 172, 156), 42.25
kitchen.base_run("kitchen", W, 199, "W", [("dishwasher", 24), ("sink", 36), ("drawers", 12), ("range", 30), ("doors", 24), ("gap", 2.5), ("fridge", 33)],
                 rgb=GREIGE, backsplash=26, room=R)
kitchen.upper_run("kitchen_up", W, 196, "W", [("doors", 27, 36), ("doors", 36, 30), ("doors", 12, 36), ("microwave", 30), ("doors", 24, 42),
                                              ("gap", 2), ("doors", 34, 24)], rgb=GREIGE, room=R)
kitchen.counter("bar", 155.75, 175, "S", W - 155.75, depth=24.5, z=BAR_Z, round_end="left", room=R)
for i, x in enumerate((171.0, 194.0)):
    fixtures.pendant("pendant_%d" % i, x, 186.25, H, drop=40, room=R)
for i, x in enumerate((181.0, 201.0)):
    f.chair("stool_%d" % i, x, 155.75, "S", kind="stool", material="leather", rgb=(16, 16, 17), room=R)
for i, x in enumerate((180.0, 199.5)):
    place_setting("setting_%d" % i, x, 183, BAR_Z, R)
f.plant("counter_plant", 205, 204, height=9, z=36, pot_rgb=(238, 236, 230), room=R)
pump_bottle("dish_soap", 206.5, 258, 36, "W", mat("glass"), R, r=1.3, h=4.8)
fixtures.panel("panel", XK, 184.25, "E", z=21, room=R)
fixtures.thermostat("thermostat", XK, 247.5, "E", z=48.25, room=R)
mech("entry closet")

# ------------------------------------------------------------------ living
R, CONSOLE = "living", (150, 152, 149)
kitchen.cabinet("console_S", XBE, 86, "E", 19, depth=21.5, glass=True, rgb=CONSOLE, room=R)
chiller("chiller", XBE, 67, "E", 15, 21.5, CONSOLE, R)
kitchen.cabinet("console_N", XBE, 52, "E", 18, depth=21.5, glass=True, rgb=CONSOLE, room=R)
kitchen.counter("console_top", XBE, 86.5, "E", 53, depth=22.5, room=R)
f.tv("tv_living", XBE + 2.5, 61, "E", diagonal=50, z=36, room=R)
bike("bike", 120, 80, 36, R)
frame("console_photo", 108, 37.5, "E", 36, 5.5, 7, mat("nickel", (175, 175, 172)), (120, 130, 140), tilt=12, border=0.8, room=R)
accent_wall(XBE, 94.25, "E", 94.25, R)   # from the bedroom door's casing to the north wall
so = f.sofa("sofa", W, 48.75, "W", width=96.5, depth=35.75, seat_h=18, back_h=29, arm=6.5, arm_h=24, chaise="left", chaise_depth=44.75,
            rgb=(72, 66, 63), room=R)
f.pillow("pillow_skyline", 189, 12, so["top"], "S", size=18, lean=16, rgb=(220, 212, 200), room=R)
f.pillow("pillow_cream", 174, 13.5, so["top"], "S", size=16, lean=24, roll=-8, room=R)
f.pillow("pillow_boucle", 194, 62, so["top"], "W", size=20, lean=18, rgb=(150, 142, 134), room=R)
ot = f.ottoman("ottoman", 154.5, 6.25, "S", width=23, depth=29.5, height=18, rgb=(58, 52, 50), room=R)
f.throw("ottoman_throw", 153.25, 36.5, ot["top"], "S", width=19.5, on=29, drop=9, rgb=(120, 118, 114), room=R)
st = f.table("side_table", 207.75, 108.5, "W", width=21, depth=21, height=22, top="black_glass", rgb=(30, 32, 32), frame="black_metal",
             shelf=True, room=R)
f.plant("side_table_plant", 193, 107, height=11, z=st["top"], pot_rgb=GOLD, room=R)
frame("side_table_frame", 201.5, 111.8, "S", st["top"], 4.5, 5.5, mat("plastic", BLACK), (60, 60, 62), border=0.5, room=R)

# ------------------------------------------------------------------ bedroom and its closet
R = "bedroom"
bd = f.bed("bed", 0, 28.75, "E", size="full", height=22, headboard=0, frame="black_metal", duvet_rgb=(238, 238, 236),
           sheet_rgb=(236, 236, 234), room=R)
for i, y in enumerate((16.0, 40.0)):
    f.pillow("sham_%d" % i, 19, y, bd["top"], "E", size=19, lean=28, rgb=(40, 40, 40), room=R)
f.throw("bed_throw", 63.5, 56.75, bd["top"] + 0.3, "S", width=27, on=56, drop=12, rgb=(8, 8, 10), room=R)
dk = f.desk("desk", 0, 78, "E", width=40, depth=22, rgb=(56, 49, 45), room=R)
frame("print_chicago", 3.6, 86, "E", dk["top"], 16, 20, mat("plastic", BLACK), (246, 246, 246), inner=(223, 190, 115), tilt=8, room=R)
frame("print_cubs", 6.4, 75.5, "E", dk["top"], 12, 16, mat("plastic", (200, 195, 185)), (62, 64, 68), tilt=8, border=1.4, room=R)
f.chair("task_chair", 46.62, 77.23, 278, kind="task", rgb=(12, 12, 13), room=R)   # its centre is at (34, 79)
f.tv("tv_bed", XB, 69, "W", diagonal=43, mount="wall", z=55, room=R)
fixtures.ceiling_fan("fan", XB / 2, BCL_Y / 2, H, span=50, room=R)
R = "bedroom closet"
fixtures.closet_shelf("bcl_shelf", BCL_X1 / 2, Y_BS, "N", BCL_X1, z=66.4, depth=22.8, rod=False, room=R)
closet_rod("bcl_rod", 0.5, Y_BS - 13, BCL_X1 - 0.5, Y_BS - 13, 63.5, R)
for i, x in enumerate((29.0, 41.5)):
    bin_("closet_bin_%d" % i, x, x + 11.5, 108, 120, 66.4, 9.5, R, label=True)
bin_("hamper", 33, 47, 110, 124, 0, 21, R)

# ------------------------------------------------------------------ entry closet, laundry
R = "entry closet"
fixtures.water_heater("water_heater", XK + 12, Y_BATH_S + PART + 12, "S", diameter=20, height=58, room=R)
fixtures.closet_shelf("ecl_shelf", XK, (Y_BATH_S + PART + 24 + YS) / 2, "E", YS - Y_BATH_S - PART - 24, z=66.4, depth=24.5, rod=False, room=R)
closet_rod("ecl_rod", (XK + CL_X1 - PART) / 2, Y_BATH_S + PART + 24, (XK + CL_X1 - PART) / 2, YS - 0.5, 63.5, R)
R = "laundry"
fixtures.washer_dryer("laundry_center", ALC_X0, (Y_BS2 + Y_ALC_S) / 2, "E", kind="center", room=R)

# ------------------------------------------------------------------ bath
R = "bath"
bath.tub("tub", 45, Y_BATH_N, "S", surround=78, surround_key="porcelain", shelves=2, valve="left", hardware="black_metal", room=R)
bath.vanity("vanity", 0, 218, "E", width=30, depth=21, height=32.5, rgb=(116, 113, 106), room=R)
bath.mirror("mirror", 0, 218, "E", width=20, height=30, z=46, shelf=True, room=R)
bath.vanity_light("vanity_light", 0, 218, "E", z=81, room=R)
bath.towel_ring("towel_ring", 0, 202.5, "E", z=55, towel=True, room=R)
bath.toilet("toilet", 0, 266, "E", room=R)
bath.towel_bar("towel_bar", 0, 266, "E", z=60, towel=True, room=R)
f.plant("tank_plant", 4.8, 266, height=8, z=31, pot_rgb=(238, 236, 230), room=R)
pump_bottle("soap_dispenser", 4, 210, 33.75, "E", mat("porcelain", BLACK), R)
f.rug("bath_mat", 33, 206, "S", width=20, depth=24, rgb=(22, 22, 22), room=R)
fixtures.outlet("bath_gfci", 0, 233.5, "E", z=44, room=R)
fixtures.switch("bath_switch", BATH_W, 244.5, "W", room=R)
fixtures.vent("bath_exhaust", 35, 245, H_BATH, width=10, height=10, room=R)
ceiling_grid(0, BATH_W, Y_BATH_N, Y_BATH_S, H_BATH, (24, 48), (Y_BATH_N + 48, Y_BATH_N + 96), R)
smalls()

# ------------------------------------------------------------------ wall devices, ceiling fixtures
for n, x, y, fc, z, gang, R in (("sw_hall", 93, Y_BS2, "S", 48, 3, "kitchen"), ("sw_entry", 170, YS, "N", 48, 1, "kitchen"),
                                ("sw_bar", W, 186, "W", 48, 2, "kitchen"), ("sw_backsplash", W - 0.3, 206.5, "W", 44, 2, "kitchen"),
                                ("sw_bed", XB, 91.5, "W", 48, 2, "bedroom"), ("data_bed", XB, 61, "W", 14, 1, "bedroom"),
                                ("sw_living", XBE, 132.5, "E", 48, 1, "living")):
    fixtures.switch(n, x, y, fc, z=z, gang=gang, room=R)
for n, x, y, fc, z, R in (("out_hall", 93, Y_BS2, "S", 14, "kitchen"), ("out_closet_N", 96.5, Y_BATH_S, "N", 14, "kitchen"),
                          ("out_closet_E", CL_X1, 297, "E", 14, "kitchen"), ("out_knee", 178, 199, "S", 14, "kitchen"),
                          ("out_backsplash_1", W - 0.3, 253, "W", 44, "kitchen"), ("out_backsplash_2", W - 0.3, 313, "W", 44, "kitchen"),
                          ("out_dining", W, 150, "W", 14, "living"), ("out_living_E", W, 70, "W", 14, "living"),
                          ("out_living_N", 122, 0, "S", 14, "living"), ("out_bed_E", XB, 55, "W", 14, "bedroom"),
                          ("out_bed_W", 0, 50, "E", 14, "bedroom"), ("out_bed_N", 25, 0, "S", 14, "bedroom")):
    fixtures.outlet(n, x, y, fc, z=z, room=R)
for i, (x, y, z, R) in enumerate(((138, 42, H, "living"), (184, 42, H, "living"), (145, 160, H, "living"), (186, 215, H, "kitchen"),
                                  (186, 262, H, "kitchen"), (186, 310, H, "kitchen"), (135, 250, H, "kitchen"), (135, 318, H, "kitchen"),
                                  (66, 150, H_ALC, "laundry"), (37, 215, H_BATH, "bath"), (37, 265, H_BATH, "bath"))):
    fixtures.recessed_light("can_%d" % i, x, y, z, room=R)
fixtures.smoke_detector("smoke_kitchen", 140, 205, H, room="kitchen")
fixtures.smoke_detector("smoke_bedroom", 80, 88, H, room="bedroom")
fixtures.vent("supply_living", 159, 26, H, room="living")
fixtures.vent("supply_kitchen", 166, 252, H, room="kitchen")
for i, (x, y, z, R) in enumerate(((158, 85, H, "living"), (150, 300, H, "kitchen"), (50, 90, H, "bedroom"), (37, 240, H_BATH, "bath"),
                                  (150, 200, H, "kitchen"))):
    sprinkler("sprinkler_%d" % i, x, y, z, R)

s.build()
lights.daylight(sun_from="N", elevation=40)
lights.portal(wl, s); lights.portal(wb, s)
core.finish()

VIEWS = {   # eye, target[, shot() options; hide: prefix of the objects (a closet's doors) left out of that view]
    "01_entry": ((135, 335, 63), (150, 100, 55)),
    "02_kitchen": ((98, 262, 63), (W, 280, 44)),
    "03_living": ((150, 190, 63), (160, 0, 55)),
    "04_living_back": ((156, 44, 63), (178, YS, 46)),
    "05_bedroom": ((96, 112, 63), (40, 20, 50)),
    "06_bedroom_back": ((81.5, 8, 63), (60, 130, 44)),
    "07_bath": ((80, 226, 63), (0, 227, 40)),
    "08_bath_tub": ((26, 280, 63), (38, 170, 42)),
    "09_laundry": ((140, 152, 60), (ALC_X0, 150, 42)),
    "10_closet_doors": ((170, 300, 63), (CL_X1, 334, 45)),
    "11_bed_door": ((160, 60, 63), (XBE, 112, 45)),
    "12_bed_closet": ((30, 55, 63), (28, 125, 45), dict(hide="door_bcloset")),
    "13_entry_closet": ((165, 322, 63), (XK, 322, 50), dict(hide="door_closet")),
    "14_bar": ((140, 140, 68), (192, 190, 40)),
    "15_hall": ((170, 235, 63), (XK, 195, 45)),
    "16_sofa": ((125, 100, 63), (190, 30, 20)),
    "17_desk": ((70, 100, 63), (8, 74, 28)),
    "18_kitchen_south": ((150, 215, 63), (200, YS, 40)),
    "19_ceiling": ((140, 300, 30), (120, 150, H)),
}
names = sys.argv[sys.argv.index("--") + 2].split(",") if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 2 else []
for n in names:
    if n == "plan":
        view.hide_ceiling(True)
        view.shot("plan", (W / 2, YS / 2, 400), (W / 2, YS / 2, 0), OUT, ortho=620, exposure=0)
        view.hide_ceiling(False)
    elif n in VIEWS:
        opt = dict(VIEWS[n][2]) if len(VIEWS[n]) > 2 else {}
        hide = opt.pop("hide", None)
        hidden = [o for o in core.bpy.data.objects if hide and o.name.startswith(hide)]
        for o in hidden:
            o.hide_render = True
        view.shot(n, *VIEWS[n][:2], OUT, **opt)
        for o in hidden:
            o.hide_render = False
if "bake" in sys.argv:
    bake.bake(os.path.join(OUT, "site"), s, meta=dict(title="507 E Green - Plan C"))
