"""Builds a unit inside Blender from the files the agents write, then checks, renders or bakes it.

    blender -b --python unit.py -- <unit-dir> [--only room[,room]] [--views plan,name,...] [--final] [--check] [--bake <out-dir>]

<unit-dir>/shell.py     def build() -> Shell     walls, rooms, doors, windows, daylight
<unit-dir>/room_*.py    def build(s)             everything in one room;  VIEWS = {name: (eye, target)} in plan inches
Renders go to <unit-dir>/renders; --only builds just the named rooms on the shell, which is quicker while working
on one. layout.json (the shell's rooms, walls and openings) is rewritten on every run."""
import glob
import importlib
import json
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
UNIT = os.path.abspath(argv[0])
opt = lambda name: argv[argv.index(name) + 1] if name in argv else None
sys.path[:0] = [UNIT, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")]

from kit import bake, check, core, view  # noqa: E402

core.reset()
s = importlib.import_module("shell").build()
only = opt("--only").split(",") if opt("--only") else None
views = {}
for path in sorted(glob.glob(os.path.join(UNIT, "room_*.py"))):
    name = os.path.basename(path)[5:-3]
    if only is None or name in only:
        mod = importlib.import_module("room_" + name)
        with core.tag(room=name):
            mod.build(s)
        views.update(getattr(mod, "VIEWS", {}))
s.build()
core.finish()
json.dump(s.plan(), open(os.path.join(UNIT, "layout.json"), "w"), indent=1)

if "--check" in argv:
    problems = check.report(s)
    json.dump(problems, open(os.path.join(UNIT, "check.json"), "w"), indent=1)
    print("\n".join(["[check] " + p for p in problems]) or "[check] nothing found")

out = os.path.join(UNIT, "renders")
for n in (opt("--views") or "").split(","):
    if n == "plan":
        view.plan_shot(s, out)
    elif n in views:
        view.shot(n, *views[n], out, quality="final" if "--final" in argv else "preview")
    elif n:
        print("[views] no view named %r; have: %s" % (n, ", ".join(views)))

if opt("--bake"):
    meta = json.load(open(os.path.join(UNIT, "meta.json"))) if os.path.exists(os.path.join(UNIT, "meta.json")) else {}
    bake.bake(opt("--bake"), s, meta=meta)
