"""Test rooms for kit.bath and kit.fixtures: the 507 E Green bath, a hall showing every fixture, and a second bath
with the variants the first one does not use.
    blender -b --python test_bath.py -- <out-dir> [views]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kit import bath, core, fixtures, view
from kit.shell import Shell
from kit.openings import door

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
core.reset()

H, HB = 106.0, 104.0
Y0, Y1 = 169.5, 285.5            # north and south faces of all three rooms
XE, XH, XB = 81.5, 231.5, 237.5  # hall west face, hall east face, bath 2 west face

s = Shell(H, wall_rgb=(226, 222, 213), floor="floor_wood", plank="v")
s.wall("wall_W", -8, 0, 161, Y1 + 6)
s.wall("wall_S", -8, 343.5, Y1, Y1 + 6)
s.wall("chase", 0, 15, 165, 199.5)
s.wall("tub_N", 15, 75, 165, Y0)
s.wall("bath_E", 75, XE, 165, Y1)
s.wall("wall_N", XE, 343.5, Y0 - 6, Y0)
s.wall("hall_E", XH, XB, Y0, Y1)
s.wall("wall_E", 337.5, 343.5, Y0, Y1)
s.wall("tub2_end", 273, 277.5, 255.5, Y1)
s.room("bath", 15, 75, Y0, Y1, ceiling=HB, ceiling_key="ceiling_tile")
s.room("bath", 0, 15, 199.5, Y1, ceiling=HB, ceiling_key="ceiling_tile")
s.room("hall", XE, XH, Y0, Y1)
s.room("bath2", XB, 337.5, Y0, Y1, floor="floor_tile")
door(s, "door_bath", 78, 224, 30, swing="W", hinge="left", angle=95, room="bath")

# ---- 507 E Green bath (dimensions of the f1-opus build)
R = "bath"
bath.tub("tub", 45, Y0, "S", surround=78, surround_key="porcelain", shelves=2, valve="left", hardware="black_metal", room=R)
bath.vanity("vanity", 0, 218, "E", width=30, depth=21, height=32.5, rgb=(116, 113, 106), room=R)
bath.mirror("mirror", 0, 218, "E", width=20, height=30, z=46, shelf=True, room=R)
bath.vanity_light("vanity_light", 0, 218, "E", z=81, room=R)
bath.towel_ring("towel_ring", 0, 202.5, "E", z=55, towel=True, room=R)
bath.toilet("toilet", 0, 266, "E", room=R)
bath.towel_bar("towel_bar", 0, 266, "E", z=60, towel=True, room=R)
bath.paper_holder("paper", 22, Y1, "N", room=R)
fixtures.outlet("bath_gfci", 0, 233.5, "E", z=44, room=R)
fixtures.switch("bath_switch", 75, 244.5, "W", room=R)
fixtures.vent("bath_exhaust", 35, 245, HB, width=10, height=10, room=R)
fixtures.recessed_light("bath_can_0", 37, 215, HB, room=R)
fixtures.recessed_light("bath_can_1", 37, 265, HB, room=R)

# ---- hall: every fixture
R = "hall"
fixtures.washer_dryer("laundry_center", 100, Y0, "S", kind="center", room=R)
fixtures.washer_dryer("laundry_pair", 155, Y0, "S", kind="side_by_side", finish="stainless", room=R)
fixtures.closet_shelf("wire_shelf", 155, Y0, "S", 56, z=70, room=R)
fixtures.water_heater("water_heater", 212, 186, "S", room=R)
fixtures.closet_shelf("wood_shelf", XH, 245, "W", 70, kind="wood", room=R)
fixtures.vent("wall_register", XH, 198, 90, facing="W", room=R)
fixtures.washer_dryer("laundry_stack", 204, Y1, "N", finish="black", room=R)
fixtures.panel("panel", 110, Y1, "N", room=R)
fixtures.thermostat("thermostat", 133, Y1, "N", room=R)
fixtures.switch("switch_3", 150, Y1, "N", gang=3, room=R)
fixtures.switch("switch_2", 166, Y1, "N", gang=2, room=R)
fixtures.outlet("outlet_S", 150, Y1, "N", room=R)
fixtures.switch("switch_1", XE, 247, "E", room=R)
fixtures.outlet("outlet_W", XE, 262, "E", room=R)
fixtures.ceiling_fan("fan", 156, 232, H, room=R)
fixtures.recessed_light("can_0", 100, 200, H, room=R)
fixtures.recessed_light("can_1", 205, 205, H, room=R)
fixtures.flush_light("flush", 100, 265, H, room=R)
fixtures.pendant("pendant_cage", 135, 270, H, drop=40, room=R)
fixtures.pendant("pendant_cone", 170, 270, H, shade="cone", hardware="brass", room=R)
fixtures.pendant("pendant_globe", 200, 236, H, drop=30, shade="globe", hardware="nickel", room=R)
fixtures.vent("supply", 130, 205, H, room=R)
fixtures.smoke_detector("smoke", 175, 200, H, room=R)

# ---- bath 2: the variants
R = "bath2"
bath.shower("shower", XB + 18, Y0, "S", glass_side="right", room=R)
bath.tub("tub2", 307.5, Y1, "N", surround=84, valve="right", enclosure="glass", room=R)
bath.vanity("vanity2", 337.5, 215, "W", width=49, height=33, doors=2, drawers=3, style="slab", false_front=False,
            cabinet="cabinet_wood", pulls="knob", hardware="nickel", faucet="single", counter_rgb=(60, 60, 62), room=R)
bath.mirror("mirror2", 337.5, 215, "W", width=36, height=38, z=42, kind="plain", lit=True, room=R)
bath.mirror("med_cabinet", XB, 232, "E", width=16, height=26, z=48, kind="cabinet", room=R)
bath.vanity_light("vanity_light2", XB, 232, "E", z=80, width=14, bulbs=2, hardware="chrome", room=R)
bath.towel_bar("towel_bar2", XB, 262, "E", z=48, length=18, hardware="chrome", room=R)
bath.towel_ring("towel_ring2", XB, 214, "E", hardware="brass", room=R)
bath.paper_holder("paper2", XB, 276, "E", hardware="nickel", roll=False, room=R)
fixtures.flush_light("flush2", 290, 222, H, room=R)

s.build()
core.finish()

VIEWS = {
    "bath": ((80, 226, 63), (0, 227, 40)),
    "bath_tub": ((45, 278, 63), (45, 170, 45)),
    "bath_south": ((55, 212, 63), (12, 285, 28)),
    "bath_up": ((62, 280, 40), (25, 215, 104)),
    "bath_curtain": ((22, 204, 60), (70, 197, 45)),
    "hall_N": ((150, 280, 63), (150, 170, 50)),
    "hall_S": ((120, 206, 63), (165, 285, 50)),
    "hall_E": ((95, 228, 63), (231, 232, 60)),
    "hall_W": ((185, 212, 63), (82, 245, 45)),
    "hall_up": ((150, 282, 45), (150, 215, 106)),
    "bath2_NE": ((245, 278, 63), (300, 185, 40)),
    "bath2_SW": ((320, 180, 63), (270, 285, 35)),
}
names = sys.argv[sys.argv.index("--") + 2].split(",") if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 2 else list(VIEWS)
for n in names:
    view.shot(n, *VIEWS[n], OUT)
