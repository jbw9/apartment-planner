"""Finds the mistakes that are easy to make and hard to see in a render. Call report(shell) after every part is placed;
it returns a list of plain sentences, empty when nothing is wrong."""
import bpy

from . import core, lights

HARDWARE = {"black_metal", "chrome", "nickel", "brass", "stainless"}


def _keys(ob):
    return {m.name.split(".")[0] for m in ob.data.materials if m}


def report(shell):
    out = []
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for name, d in shell.openings.items():
        if not d["doorway"]:
            continue
        parts = [o for o in meshes if o.name.startswith(name + "_leaf") or o.name.startswith(name + "_panel")]
        if parts and not any(_keys(o) & HARDWARE for o in meshes if o.name.startswith(name)):
            out.append("door '%s' has no handle" % name)
    rooms = {}
    for r in shell.rooms:
        rooms.setdefault(r["name"], []).append(r)
    inside = lambda rects, x, y, pad=0.0: any(r["x0"] - pad <= x <= r["x1"] + pad and r["y0"] - pad <= y <= r["y1"] + pad for r in rects)
    for name, rects in rooms.items():
        if not any(inside(rects, l[0], l[1]) for l in lights.LAMPS):
            out.append("room '%s' has no light fixture" % name)
    feet = core.FOOTPRINTS
    for i, (n, x0, y0, x1, y1, h) in enumerate(feet):
        if not inside(shell.rooms, (x0 + x1) / 2, (y0 + y1) / 2):
            out.append("'%s' stands outside every room" % n)
        for w in shell.walls:
            if w["z0"] > 0.5:
                continue
            ox, oy = min(x1, w["x1"]) - max(x0, w["x0"]), min(y1, w["y1"]) - max(y0, w["y0"])
            if ox > 1 and oy > 1:
                out.append("'%s' is %.1f in. inside wall '%s'" % (n, min(ox, oy), w["name"]))
        for m, a0, b0, a1, b1, _ in feet[i + 1:]:
            ox, oy = min(x1, a1) - max(x0, a0), min(y1, b1) - max(y0, b0)
            if ox > 1 and oy > 1 and m != n:
                out.append("'%s' and '%s' overlap by %.1f x %.1f in." % (n, m, ox, oy))
    for name, d in shell.openings.items():
        if d["doorway"]:
            mid = (d["a"] + d["b"]) / 2
            sides = [(mid, c) if d["along"] == "x" else (c, mid) for c in (d["c0"] - 6, d["c1"] + 6)]
            if not any(inside(shell.rooms, x, y, 0.5) for x, y in sides):   # the entry door has a room on one side only
                out.append("door '%s' has no room on either side" % name)
            if any(a0 < x < a1 and b0 < y < b1 for x, y in sides for _, a0, b0, a1, b1, _h in feet):
                out.append("door '%s' is blocked by something standing in front of it" % name)
    return out
