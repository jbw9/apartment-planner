"""Test room for kit.kitchen: the 507 E Green kitchen on the east wall, a different one on the north wall.
    blender -b --python test_kitchen.py -- <out-dir> [views]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kit import core, lights, view, kitchen
from kit.shell import Shell

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
core.reset()

H, W, D, EXT = 106.0, 240.0, 230.0, 8.0
s = Shell(H, wall_rgb=(226, 222, 213), floor="floor_wood", plank="v")
s.wall("wall_N", -EXT, W + EXT, -EXT, 0)
s.wall("wall_E", W, W + EXT, 0, D)
s.wall("wall_S", -EXT, W + EXT, D, D + EXT)
s.wall("wall_W", -EXT, 0, 0, D)
s.wall("knee", 196.5, W, 36, 50, z1=41)
s.room("kitchen", 0, W, 0, D)

# east wall: 507 E Green
GREIGE = (168, 162, 134)
kitchen.base_run("east", W, 50, "W", [("dishwasher", 24), ("sink", 36), ("drawers", 12), ("range", 30), ("doors", 24), ("gap", 2.5), ("fridge", 33)],
                 rgb=GREIGE, backsplash=26, room="kitchen")
kitchen.upper_run("east_up", W, 47, "W", [("doors", 27, 36), ("doors", 36, 30), ("doors", 12, 36), ("microwave", 30), ("doors", 24, 42),
                                          ("gap", 2), ("doors", 34, 24)], rgb=GREIGE, room="kitchen")
kitchen.counter("bar", 184.25, 26, "S", W - 184.25, depth=24.5, z=42.25, round_end="left", room="kitchen")

# north wall: white, knobs, glass-top range, hood, black appliances, dark counter
WHITE, DARK = (238, 238, 232), (62, 62, 66)
kitchen.base_run("north", 8, 0, "S", [("fridge", 33), ("gap", 1), ("doors", 18), ("range", 30), ("drawers", 18, 4), ("sink", 36), ("dishwasher", 24),
                                      ("doors", 15)], rgb=WHITE, counter_rgb=DARK, backsplash=4, splash="counter", pulls="knob", hardware="brass",
                 appliances="black", range_type="glass", bowls=2, faucet="chrome", room="kitchen")
kitchen.upper_run("north_up", 8, 0, "S", [("doors", 34, 18)], top=90, depth=24, rgb=WHITE, pulls="knob", hardware="brass", room="kitchen")
kitchen.upper_run("north_up2", 42, 0, "S", [("doors", 18, 36), ("hood", 30), ("doors", 18, 36), ("shelves", 36, 36), ("doors", 39, 36)], top=90,
                  rgb=WHITE, pulls="knob", hardware="brass", appliances="black", room="kitchen")

# west wall: single parts
kitchen.cabinet("pantry", 0, 150, "E", 24, kind="tall", height=84, wood=True, hardware="nickel", room="kitchen")
kitchen.cabinet("console", 0, 115, "E", 36, depth=21.5, top=True, glass=True, rgb=(150, 152, 149), room="kitchen")
isl = kitchen.counter("island", 70, 150, "S", 78, depth=30, room="kitchen")
kitchen.cabinet("island_drawers", 70, 151.5, "S", 18, kind="drawers", depth=27, room="kitchen")
kitchen.cabinet("island_sink_base", 88, 151.5, "S", 36, kind="sink", depth=27, room="kitchen")
kitchen.sink("island_sink", 92, 150, "S", counter=isl, depth=30, faucet="nickel", room="kitchen")
kitchen.dishwasher("island_dw", 124, 151.5, "S", depth=27, finish="white", room="kitchen")

s.build()
for i, (x, y) in enumerate(((60, 70), (150, 70), (60, 160), (150, 160), (200, 115), (200, 190))):
    lights.lamp("can_%d" % i, x, y, H - 0.5)
core.finish()

VIEWS = {
    "east_front": ((140, 135, 63), (W, 130, 50)),
    "east_oblique": ((170, 222, 63), (236, 90, 45)),
    "island": ((125, 226, 63), (105, 165, 25)),
    "north_front": ((96, 100, 63), (96, 0, 50)),
    "north_oblique": ((176, 62, 63), (30, 4, 42)),
    "west_parts": ((120, 100, 63), (20, 150, 30)),
    "bar": ((150, 70, 70), (230, 45, 38)),
}
names = sys.argv[sys.argv.index("--") + 2].split(",") if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 2 else list(VIEWS)
for n in names:
    view.shot(n, *VIEWS[n], OUT)
