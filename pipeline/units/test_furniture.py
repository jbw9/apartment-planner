"""Every piece of kit.furniture in a living room and a bedroom staged like 507 E Green.
    blender -b --python test_furniture.py -- <out-dir> [views]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kit import core, lights, view
from kit import furniture as f
from kit.shell import Shell
from kit.openings import window

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
core.reset()

H, LW, LD, BX, BE, BD = 106.0, 170.0, 220.0, 174.5, 294.5, 150.0
s = Shell(H, floor="floor_wood", plank="v")
s.wall("wall_N", -8, BE + 8, -8, 0)
s.wall("wall_W", -8, 0, 0, LD + 8)
s.wall("wall_S", 0, BX, LD, LD + 8)
s.wall("partition", LW, BX, 0, LD)
s.wall("bed_S", BX, BE + 8, BD, BD + 8)
s.wall("bed_E", BE, BE + 8, 0, BD)
s.room("living", 0, LW, 0, LD)
s.room("bedroom", BX, BE, 0, BD)
wl = window(s, "win_living", 110, -4, 47, 31, 50, room="living")
wb = window(s, "win_bedroom", 250, -4, 42, 35, 46, room="bedroom")

# ---- living room: sectional on the east wall, ottoman under the window, console and TV on the west wall
R = "living"
so = f.sofa("sofa", LW, 50, "W", width=96, chaise="left", chaise_depth=45, room=R)
f.pillow("pillow_cream", 153, 30, so["top"], "W", size=18, room=R)
f.pillow("pillow_grey", 153, 76, so["top"], "W", size=20, rgb=(150, 142, 134), roll=6, room=R)
f.pillow("pillow_arm", 140, 14, so["top"], "S", size=16, lean=24, rgb=(196, 150, 96), room=R)
ot = f.ottoman("ottoman", 112, 0, "S", width=23, depth=29, height=18, room=R)
f.throw("throw_ottoman", 112, 29.75, ot["top"], "S", width=17, on=22, drop=9, rgb=(120, 118, 114), room=R)
st = f.table("side_table", LW, 110, "W", width=21, depth=21, height=22, top="black_glass", frame="black_metal", shelf=True, room=R)
f.plant("plant_side", 162, 105, height=10, z=st["top"], pot_rgb=(196, 160, 96), room=R)
f.table_lamp("lamp_side", 157, 115, z=st["top"], room=R)
co = f.console("console", 0, 70, "E", width=52, depth=21, height=36, doors=3, rgb=(214, 212, 204), room=R)
f.tv("tv_living", 0, 70, "E", diagonal=50, z=co["top"], room=R)
f.rug("rug_living", 82, 45, "S", width=84, depth=120, rgb=(186, 180, 168), border_rgb=(120, 116, 110), room=R)
f.table("coffee", 85, 62, "S", width=30, height=16, shape="round", room=R)
f.armchair("armchair", 22, 140, 125, rgb=(72, 88, 96), room=R)
f.floor_lamp("floor_lamp", 14, 112, room=R)
f.shelf("bookcase", 40, LD, "N", room=R)
dt = f.table("dining", 125, 157, "S", width=36, shape="round", base="pedestal", top="counter", frame="black_metal", room=R)
f.chair("chair_n", 125, 138, "S", room=R)
f.chair("chair_s", 125, 212, "N", rgb=(150, 120, 90), material="leather", room=R)
f.chair("stool_bar", LW, 135, "W", kind="stool", room=R)
f.chair("stool_low", 78, 190, 300, kind="stool", seat_h=18, back=False, frame="wood", rgb=(170, 160, 140), room=R)
f.wall_art("art_sofa", LW, 56, "W", width=36, height=24, z=62, rgb=(200, 190, 170), accent_rgb=(60, 84, 100), room=R)
f.wall_mirror("mirror_round", 95, LD, "N", width=26, shape="round", z=60, frame="brass", room=R)
f.plant("tree", 158, 206, height=62, room=R)
f.curtains("curtains_living", 110, 0, "S", width=47, head=81, length=58, room=R)

# ---- bedroom: full bed in the north-west corner, desk and task chair, TV on the east wall
R = "bedroom"
bd = f.bed("bed", BX, 31, "E", size="full", frame="black_metal", headboard_rgb=(120, 116, 110), room=R)
f.pillow("sham_1", 197, 18, bd["top"], "E", size=19, lean=28, rgb=(40, 40, 42), room=R)
f.pillow("sham_2", 197, 44, bd["top"], "E", size=19, lean=28, rgb=(40, 40, 42), room=R)
f.throw("throw_bed", 240, 59, bd["top"] + 0.3, "S", width=26, on=57, drop=10, rgb=(14, 14, 16), room=R)
ns = f.nightstand("nightstand", BX, 73, "E", rgb=(110, 84, 60), room=R)
f.table_lamp("lamp_bed", *f.spot(BX, 73, "E", v=8.5), z=ns["top"], rgb=(60, 70, 80), room=R)
dk = f.desk("desk", BX, 119, "E", width=44, depth=22, drawers="left", room=R)
f.chair("task_chair", 227.6, 116.2, 278, kind="task", rgb=(24, 24, 26), room=R)
f.tv("tv_bed", BE, 40, "W", diagonal=43, mount="wall", z=45, room=R)
dr = f.dresser("dresser", 250, BD, "N", room=R)
f.plant("plant_dresser", 232, BD - 9, height=14, z=dr["top"], room=R)
f.wall_mirror("mirror_dresser", 252, BD, "N", width=30, height=24, z=58, room=R)
f.wall_art("art_bed", BX, 31, "E", width=22, height=28, z=70, rgb=(60, 84, 100), room=R)
f.rug("rug_bed", 236, 64, "S", width=72, depth=48, rgb=(150, 152, 150), room=R)
f.ottoman("pouf", BE, 112, "W", width=20, shape="round", rgb=(176, 150, 110), room=R)
f.table("bench_table", BE, 84, "W", width=22, depth=14, height=22, frame="wood", room=R)
f.plant("tree_bed", 283, 12, height=54, room=R)
f.curtains("curtains_bed", 250, 0, "S", width=42, head=81, rgb=(110, 122, 130), room=R)

s.build()
lights.daylight(sun_from="N", elevation=40)
lights.portal(wl, s); lights.portal(wb, s)
for i, (x, y) in enumerate(((60, 60), (120, 60), (60, 160), (120, 160), (235, 45), (235, 110))):
    lights.lamp("can_%d" % i, x, y, H - 0.5)
core.finish()
print("[furniture] %d objects, %d triangles" % (len(core.bpy.data.collections["furniture"].objects),
      sum(len(p.vertices) - 2 for o in core.bpy.data.collections["furniture"].objects for p in o.data.polygons)))

VIEWS = {
    "L1_north": ((55, 205, 63), (125, 20, 35)),
    "L2_south": ((100, 14, 63), (85, 220, 30)),
    "L3_sofa": ((40, 40, 60), (170, 62, 22)),
    "L4_west": ((150, 135, 63), (0, 110, 30)),
    "L5_dining": ((60, 110, 63), (135, 200, 25)),
    "B1_bed": ((286, 142, 63), (195, 35, 25)),
    "B2_desk": ((272, 14, 63), (200, 150, 28)),
    "B3_east": ((183, 100, 63), (294, 70, 35)),
    "L6_close": ((118, 78, 48), (165, 30, 20)),
    "B4_close": ((228, 78, 50), (180, 52, 22)),
}
names = sys.argv[sys.argv.index("--") + 2].split(",") if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 2 else list(VIEWS) + ["plan"]
for n in names:
    if n == "plan":
        view.hide_ceiling(True)
        view.shot("plan", (143, 110, 400), (143, 110, 0), OUT, ortho=330, exposure=0)
        view.hide_ceiling(False)
    else:
        view.shot(n, *VIEWS[n], OUT)
