"""Kitchens: runs of base and upper cabinets with their appliances, and the same parts one at a time.

Every part is placed by the plan point (x, y) of its LEFT BACK corner: its left end on the wall face, as seen from
the room looking at it. `facing` is the compass letter it faces (away from its wall) and widths run to the right
from there. Cabinets are painted `rgb` (or wood tinted `rgb`, with wood=True) with shaker fronts.
    pulls       'bar' | 'knob' | None, in material `hardware` (a metal from the vocabulary: 'black_metal',
                'stainless', 'nickel', 'brass', 'chrome')
    finish / appliances   'stainless' | 'white' | 'black'
"""
import math
from contextlib import contextmanager

import bmesh

from . import core
from .core import at, box, cyl, mat, tag

T, OVER, G = 1.25, 1.5, 0.07   # counter thickness, its overhang past the cabinet fronts, gap round a front
CABINETS = ("doors", "drawers", "sink")
COUNTERED = CABINETS + ("dishwasher",)


@contextmanager
def _part(x, y, facing, room, source):
    with tag(group="C", coll="kitchen", room=room, **({"source": source} if source else {})), at(x, y, facing):
        yield


def _style(rgb, wood, pulls, hardware):
    return dict(m=mat("cabinet_wood" if wood else "cabinet_paint", rgb), pulls=pulls, hw=mat(hardware))


def _finish(finish):
    return mat({"stainless": "stainless", "white": "appliance_white", "black": "appliance_black"}[finish])


def _boxes(name, boxes, material):
    """Several boxes (u0, u1, v0, v1, z0, z1) as one object, so a cabinet front is not five."""
    bm = bmesh.new()
    for u0, u1, v0, v1, z0, z1 in boxes:
        vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=(abs(u1 - u0), abs(v1 - v0), abs(z1 - z0)), verts=vs)
        bmesh.ops.translate(bm, vec=((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2), verts=vs)
    return core.emit(name, bm, material)


def _rings(name, rings, z0, z1, material, seg=20):
    """Flat rings (u, v, inner radius, outer radius) standing from z0 to z1, as one object."""
    bm = bmesh.new()
    for u, v, r0, r1 in rings:
        loop = lambda r, z: [bm.verts.new((u + r * math.cos(2 * math.pi * i / seg), v + r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]
        ib, it, ot, ob = loop(r0, z0), loop(r0, z1), loop(r1, z1), loop(r1, z0)
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((ib[j], ib[i], it[i], it[j]))
            bm.faces.new((it[i], ot[i], ot[j], it[j]))
            bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
    return core.emit(name, bm, material, True)


def _blocks(spans, kinds):
    """Merges neighbouring spans (kind, u0, u1, ...) of the given kinds into [u0, u1] stretches."""
    out = []
    for kind, u0, u1, *_ in spans:
        if kind in kinds:
            if out and out[-1][1] == u0:
                out[-1][1] = u1
            else:
                out.append([u0, u1])
    return out


# ------------------------------------------------------------------ cabinet fronts
def _front(name, u0, u1, z0, z1, F, m, glass=False):
    """Shaker front with its face at v=F."""
    u0, u1, z0, z1 = u0 + G, u1 - G, z0 + G, z1 - G
    fr = min(2.25, (u1 - u0) / 4, (z1 - z0) / 4, 1.6 if z1 - z0 < 7.5 else 9)
    frame = [(u0, u0 + fr, F - 0.75, F, z0, z1), (u1 - fr, u1, F - 0.75, F, z0, z1),
             (u0 + fr, u1 - fr, F - 0.75, F, z0, z0 + fr), (u0 + fr, u1 - fr, F - 0.75, F, z1 - fr, z1)]
    if glass:
        box(name + "_glass", u0 + fr, u1 - fr, F - 0.55, F - 0.45, z0 + fr, z1 - fr, mat("frosted_glass"))
    else:
        frame.append((u0 + fr, u1 - fr, F - 0.75, F - 0.25, z0 + fr, z1 - fr))
    _boxes(name, frame, m)


def _pull(name, u, z, F, k, length=5.0, axis="z"):
    if k["pulls"] == "knob":
        cyl(name, (u, z), F, F + 0.7, 0.25, k["hw"], axis="v", seg=12)
        core.ellipsoid(name, (u, F + 1.0, z), (0.6, 0.45, 0.6), k["hw"], seg=12)
    elif k["pulls"] == "bar":
        du, dz = (0, 1) if axis == "z" else (1, 0)
        h = length / 2
        _boxes(name, [(u - h * du - 0.22, u + h * du + 0.22, F + 0.93, F + 1.37, z - h * dz - 0.22, z + h * dz + 0.22)] +
               [(u + s * du - 0.18, u + s * du + 0.18, F, F + 0.93, z + s * dz - 0.18, z + s * dz + 0.18) for s in (0.6 - h, h - 0.6)], k["hw"])


def _doors(name, u0, u1, z0, z1, F, k, pull_z, glass=False):
    """One door up to 21 in wide, otherwise a pair; pulls at the meeting stiles."""
    mid = (u0 + u1) / 2
    for a, b, pu in ([(u0, mid, mid - 1.8), (mid, u1, mid + 1.8)] if u1 - u0 > 21 else [(u0, u1, u1 - 1.8)]):
        _front(name + "_door", a, b, z0, z1, F, k["m"], glass)
        _pull(name + "_pull", pu, pull_z, F, k)


def _drawer(name, u0, u1, z0, z1, F, k, pull=True):
    _front(name + "_drawer", u0, u1, z0, z1, F, k["m"])
    if pull:
        _pull(name + "_pull", (u0 + u1) / 2, (z0 + z1) / 2 + min(3.0, (z1 - z0 - 5) * 0.45), F, k, min(7.0, (u1 - u0) / 2), "u")


def _base(name, u0, w, kind, F, H, k, drawers=3, glass=False):
    """Floor cabinet u0..u0+w with fronts at v=F and its box top at H."""
    u1, m = u0 + w, k["m"]
    zt = H - 0.25
    zd = zt - 6.5   # the line under the top drawers, shared by every cabinet in a run
    if kind == "sink":
        # no box where the bowl hangs, or its top would close the hole in the counter
        box(name + "_carcass", u0, u1, 0, F - 0.75, 4, H - 10, m)
        _boxes(name + "_sides", [(u0, u0 + 0.75, 0, F - 0.75, H - 10, H), (u1 - 0.75, u1, 0, F - 0.75, H - 10, H),
                                 (u0 + 0.75, u1 - 0.75, 0, 0.75, H - 10, H)], m)
    else:
        box(name + "_carcass", u0, u1, 0, F - 0.75, 4, H, m)
    box(name + "_kick", u0, u1, 0, F - 3, 0, 4, m)
    if kind == "drawers":
        _drawer(name, u0, u1, zd, zt, F, k)
        step = (zd - 4.25) / (drawers - 1)
        for i in range(drawers - 1):
            _drawer(name, u0, u1, 4.25 + i * step, 4.25 + (i + 1) * step, F, k)
    elif kind == "tall":
        zs = 0.6 * H
        _doors(name, u0, u1, 4.25, zs, F, k, zs - 5, glass)
        _doors(name + "_upper", u0, u1, zs, zt, F, k, zs + 5, glass)
    else:
        _drawer(name, u0, u1, zd, zt, F, k, pull=kind != "sink")
        _doors(name, u0, u1, 4.25, zd, F, k, zd - 5, glass)


# ------------------------------------------------------------------ appliances and fixtures, in the current frame
def _fridge(name, u0, w, D, H, finish, hinge):
    m, dk, u1 = _finish(finish), mat("black_metal"), u0 + w
    zs = 0.73 * H   # top of the fridge door, the freezer above
    box(name + "_cabinet", u0, u1, 1, D - 2, 0.6, H, m)
    box(name + "_door", u0, u1, D - 2, D - 0.6, 1, zs, m)
    box(name + "_freezer_door", u0, u1, D - 2, D - 0.6, zs + 0.4, H - 0.3, m)
    box(name + "_gasket", u0 + 0.05, u1 - 0.05, D - 2.1, D - 1, zs, zs + 0.4, dk)
    box(name + "_grille", u0 + 1, u1 - 1, D - 1.5, D - 1, 0.2, 1, dk)
    hu = u0 + 1.8 if hinge == "right" else u1 - 1.8
    for z0, z1 in ((zs - 17.6, zs - 1.1), (zs + 1.4, zs + 12.4)):
        _boxes(name + "_handle", [(hu - 0.5, hu + 0.5, D + 0.3, D + 1, z0, z1)] +
               [(hu - 0.3, hu + 0.3, D - 0.6, D + 0.3, z - 0.4, z + 0.4) for z in (z0 + 0.8, z1 - 0.8)], m)


def _range(name, u0, w, kind, finish):
    """30 in class free-standing range: 27 deep, cooktop at 36, backguard to 43.5."""
    m, bg, dk = _finish(finish), mat("black_glass"), mat("black_metal")
    a, b = u0 + 0.2, u0 + w - 0.2
    box(name + "_body", a, b, 0.5, 26, 0.5, 35.5, m)
    box(name + "_drawer", a + 0.1, b - 0.1, 26, 27, 0.8, 5.6, m)
    box(name + "_door", a + 0.1, b - 0.1, 26, 27, 6, 26.6, bg)
    box(name + "_door_window", a + 5.5, b - 5.5, 26.9, 27.08, 10.5, 22, mat("black_glass", (35, 28, 26)))
    box(name + "_door_trim", a + 0.1, b - 0.1, 26, 27.1, 26.6, 30, m)
    _boxes(name + "_handle", [(a + 2, b - 2, 28.4, 29.2, 27.6, 28.6)] +
           [(u - 0.3, u + 0.3, 27, 28.4, 27.8, 28.4) for u in (a + 2.6, b - 2.6)], m)
    burners = [(a + 7.5, 20.5, 4.0), (b - 7.5, 20.5, 3.0), (a + 7.5, 9.5, 3.0), (b - 7.5, 9.5, 4.0)]
    if kind == "glass":
        box(name + "_top", a, b, 3.5, 27.1, 35.5, 36, bg)
        _rings(name + "_zones", [(u, v, r - 0.12, r) for u, v, r in burners], 35.9, 36.02, mat("black_glass", (90, 90, 92)), 32)
    else:
        top = m if finish == "white" else mat("appliance_black")
        box(name + "_top", a, b, 3.5, 27, 35.5, 36, top)
        box(name + "_top_trim", a, b, 26.4, 27.1, 34.6, 36, top)
        _rings(name + "_coils", [(u, v, rr - 0.4, rr) for u, v, r in burners for rr in (r - 0.95 * i for i in range(4)) if rr > 0.5],
               35.9, 36.25, dk)
        for u, v, r in burners:
            cyl(name + "_drip_pan", (u, v), 35.9, 36.03, r + 0.6, mat("chrome"))
    box(name + "_backguard", a, b, 0.5, 3.5, 36, 43.5, m)
    box(name + "_backguard_panel", a + 6, b - 6, 3.45, 3.6, 38.5, 42, bg)
    box(name + "_display", (a + b) / 2 - 1.2, (a + b) / 2 + 1.2, 3.55, 3.7, 40, 40.9, mat("emit_display"))
    for u in (a + 2.2, a + 4.6, b - 4.6, b - 2.2):
        cyl(name + "_knob", (u, 40.0), 3.5, 4.6, 0.8, dk, axis="v", seg=16)


def _dishwasher(name, u0, w, F, top, finish):
    dk, u1 = mat("black_metal"), u0 + w
    box(name + "_tub", u0 + 0.1, u1 - 0.1, 0.5, F - 1, 0.5, top, dk)
    box(name + "_door", u0 + 0.15, u1 - 0.15, F - 1, F, 4, top, _finish(finish))
    box(name + "_handle_pocket", u0 + 7, u1 - 7, F - 0.4, F + 0.02, top - 3.2, top - 1.9, dk)
    box(name + "_kick", u0, u1, F - 3, F - 2.5, 0, 4, dk)


def _microwave(name, u0, w, z0, h, D, finish):
    m, bg, u1, z1 = _finish(finish), mat("black_glass"), u0 + w, z0 + h
    box(name + "_body", u0, u1, 0.3, D - 0.8, z0, z1, m)
    box(name + "_vent", u0, u1, D - 0.8, D, z0, z0 + 2, mat("black_metal"))
    box(name + "_door", u0, u1 - 6, D - 0.8, D, z0 + 2, z1 - 0.3, m)
    box(name + "_window", u0 + 1.5, u1 - 8.5, D - 0.3, D + 0.05, z0 + 3.6, z1 - 2, bg)
    box(name + "_panel", u1 - 5.9, u1 - 0.3, D - 0.8, D + 0.05, z0 + 2, z1 - 0.3, bg)
    box(name + "_display", u1 - 4.5, u1 - 1.5, D, D + 0.1, z1 - 3.2, z1 - 2.2, mat("emit_display"))
    _boxes(name + "_handle", [(u1 - 7.6, u1 - 6.8, D + 0.9, D + 1.6, z0 + 3, z1 - 1.5)] +
           [(u1 - 7.5, u1 - 6.9, D, D + 0.9, z - 0.3, z + 0.3) for z in (z0 + 3.6, z1 - 2.1)], m)


def _hood(name, u0, w, z1, finish):
    """Under-cabinet range hood hanging from z1."""
    m, dk, u1 = _finish(finish), mat("black_metal"), u0 + w
    box(name + "_body", u0 + 0.1, u1 - 0.1, 0.3, 19.5, z1 - 5.5, z1, m)
    box(name + "_filter", u0 + 2, u1 - 2, 3, 17.5, z1 - 5.6, z1 - 5.5, dk)
    box(name + "_controls", u1 - 8, u1 - 2, 19.5, 19.6, z1 - 4.2, z1 - 3.2, dk)


def _sink(name, u0, w, v0, v1, z, thick, bowls, faucet, slab):
    """Undermount bowl u0..u0+w, v0..v1 under a counter whose top is at z; cuts its hole in `slab`."""
    u1, zu, zb, m = u0 + w, z - thick, z - thick - 9, mat("stainless")
    if slab:
        core.cut(slab, [box("cut", u0, u1, v0, v1, zu - 1, z + 1, None)])
    walls = [(u0 - 0.3, u0, v0 - 0.3, v1 + 0.3, zb, zu), (u1, u1 + 0.3, v0 - 0.3, v1 + 0.3, zb, zu),
             (u0, u1, v0 - 0.3, v0, zb, zu), (u0, u1, v1, v1 + 0.3, zb, zu), (u0 - 0.3, u1 + 0.3, v0 - 0.3, v1 + 0.3, zb - 0.3, zb)]
    mid = (u0 + u1) / 2
    if bowls == 2:
        walls.append((mid - 0.5, mid + 0.5, v0, v1, zb, zu - 0.5))
    _boxes(name + "_bowl", walls, m)
    for u in ((u0 + mid) / 2, (mid + u1) / 2) if bowls == 2 else (mid,):
        cyl(name + "_drain", (u, (v0 + v1) / 2), zb, zb + 0.15, 1.75, mat("chrome"))
    hw, fv = mat(faucet), v0 - 2.15
    cyl(name + "_faucet_base", (mid, fv), z, z + 1.2, 1.1, hw)
    cyl(name + "_faucet_body", (mid, fv), z + 1.2, z + 8.5, 0.65, hw)
    neck = [(mid, fv + 4.6 * (1 - math.cos(math.pi * i / 12)), z + 8.5 + 6.5 * math.sin(math.pi * i / 12)) for i in range(13)]
    core.tube(name + "_faucet_neck", neck + [(mid, fv + 9.2, z + 6.2)], 0.5, hw)
    cyl(name + "_faucet_head", (mid, fv + 9.2), z + 4.6, z + 7.4, 0.62, hw)
    box(name + "_faucet_lever", mid + 0.6, mid + 3.2, fv - 0.3, fv + 0.3, z + 6.5, z + 7.1, hw)


def _slab(name, u0, u1, depth, z, thick, m, round_end=None):
    if not round_end:
        return box(name, u0, u1, 0, depth, z - thick, z, m)
    r = depth / 2
    uc, s = (u0 + r, -1) if round_end == "left" else (u1 - r, 1)
    far = u1 if round_end == "left" else u0
    arc = [(uc + s * r * math.sin(math.pi * i / 24), r - r * math.cos(math.pi * i / 24)) for i in range(25)]
    return core.prism(name, [(far, depth), (far, 0)] + arc, z - thick, z, m)


# ------------------------------------------------------------------ runs
def base_run(name, x, y, facing, segments, depth=24.0, height=36.0, rgb=None, wood=False, counter_rgb=None, backsplash=0.0,
             splash="tile", pulls="bar", hardware="black_metal", appliances="stainless", range_type="coil", bowls=1,
             faucet="black_metal", room="", source=None):
    """A run of base cabinets and floor appliances along a wall, built left to right from plan point (x, y), the
    run's left end on the wall face as seen from the room.
    segments    [(type, width), ...] in inches, left to right:
                  'doors'       cabinet: a drawer over doors (one door up to 21 wide, otherwise a pair)
                  'drawers'     cabinet: a stack of 3 drawers, or (type, width, n) for n
                  'sink'        cabinet with an undermount sink and faucet in the counter over it (30 or wider)
                  'dishwasher'  under the counter (24)
                  'range'       free-standing, 27 deep, breaks the counter (30)
                  'fridge'      top-freezer, 30.5 deep and 66.5 tall, handles on the side nearer the run (33);
                                leave a 'gap' of an inch or two beside it
                  'gap'         nothing
    depth       wall to cabinet fronts; the counter overhangs them 1.5
    height      of the counter top, which runs over every cabinet, sink and dishwasher
    backsplash  height above the counter (0 for none; 18 reaches upper cabinets hung at 54), on the wall behind
                the counters and ranges; splash: 'tile' or 'counter' (the counter material, usually 4 high)
    rgb, wood   cabinet colour; counter_rgb: counter colour
    range_type  'coil' | 'glass';  bowls: 1 | 2 sink bowls;  faucet: its metal, as `hardware`"""
    k, mc = _style(rgb, wood, pulls, hardware), mat("counter", counter_rgb)
    F, H, CD = depth, height - T, depth + OVER
    spans, u = [], 0.0
    for kind, w, *opt in segments:
        spans.append((kind, u, u + w, opt))
        u += w
    kinds = [s[0] for s in spans]
    with _part(x, y, facing, room, source):
        slabs = [(a, b, box(name + "_counter", a, b, 0, CD, H, height, mc)) for a, b in _blocks(spans, COUNTERED)]
        if backsplash:
            ms, t = (mat("wall_tile"), 0.3) if splash == "tile" else (mc, 0.75)
            for a, b in _blocks(spans, COUNTERED + ("range",)):
                box(name + "_backsplash", a, b, 0, t, height, height + backsplash, ms)
        for a, b in _blocks(spans, COUNTERED + ("range",)):
            core.footprint(name, a, b, 0, CD, height)
        for i, (kind, u0, u1, opt) in enumerate(spans):
            n, w = "%s_%s%d" % (name, kind, i), u1 - u0
            if kind in CABINETS:
                _base(n, u0, w, kind, F, H, k, *opt)
                for ue, j in ((u0, i - 1), (u1 - 0.75, i + 1)):   # an end of the run shows the recess of the toe kick
                    if not (0 <= j < len(kinds) and kinds[j] in COUNTERED + ("range",)):
                        box(n + "_end", ue, ue + 0.75, F - 3, F - 0.75, 0, 4, k["m"])
            if kind == "sink":
                bw = min(32.0 if bowls == 2 else 28.0, w - 4)
                _sink(n, (u0 + u1 - bw) / 2, bw, 4.75, CD - 4.75, height, T, bowls, faucet,
                      next(ob for a, b, ob in slabs if a <= u0 < b))
            elif kind == "dishwasher":
                _dishwasher(n, u0, w, F, H - 0.25, appliances)
            elif kind == "range":
                _range(n, u0, w, range_type, appliances)
            elif kind == "fridge":
                _fridge(n, u0, w, 30.5, 66.5, appliances, "left" if i == 0 else "right")
                core.footprint(n, u0, u1, 0, 31.5, 66.5)


def upper_run(name, x, y, facing, segments, top=92.0, depth=12.0, height=36.0, rgb=None, wood=False, pulls="bar",
              hardware="black_metal", appliances="stainless", room="", source=None):
    """A run of wall cabinets, built left to right from plan point (x, y), the run's left end on the wall face as
    seen from the room. Line it up with a base_run by giving both the same point and matching widths.
    segments    [(type, width) or (type, width, cabinet height), ...] left to right:
                  'doors'      cabinet with doors (one up to 21 wide, otherwise a pair), `height` tall by default
                  'shelves'    open shelves, `height` tall by default
                  'microwave'  an over-the-range microwave (17 tall, 15.5 deep) under a cabinet 18 tall by default
                  'hood'       a range hood (5.5 tall, 19.5 deep) under a cabinet 12 tall by default
                  'gap'        nothing
    top         height of the cabinets' tops above the floor; every cabinet hangs down from it by its own height
    depth       wall to door faces (12; 24 for a cabinet over a fridge, as its own run)"""
    k, F, u0 = _style(rgb, wood, pulls, hardware), depth, 0.0
    with _part(x, y, facing, room, source):
        for i, (kind, w, *opt) in enumerate(segments):
            n, u1 = "%s_%s%d" % (name, kind, i), u0 + w
            h = opt[0] if opt else {"microwave": 18.0, "hood": 12.0}.get(kind, height)
            zb = top - h
            if kind == "shelves":
                _boxes(n, [(u0, u0 + 0.75, 0, F, zb, top), (u1 - 0.75, u1, 0, F, zb, top), (u0, u1, 0, 0.5, zb, top), (u0, u1, 0, F, top - 0.75, top)] +
                       [(u0 + 0.75, u1 - 0.75, 0.5, F, z, z + 0.75) for z in (zb + j * h / max(2, round(h / 14)) for j in range(max(2, round(h / 14))))], k["m"])
            elif kind != "gap":
                box(n + "_carcass", u0, u1, 0, F - 0.75, zb, top, k["m"])
                _doors(n, u0, u1, zb, top, F, k, zb + 3.8 if h > 20 else zb + h / 2)
                if kind == "microwave":
                    _microwave(n, u0 + 0.1, w - 0.2, zb - 17, 17, 15.5, appliances)
                elif kind == "hood":
                    _hood(n, u0, w, zb, appliances)
            u0 = u1


# ------------------------------------------------------------------ single parts
def cabinet(name, x, y, facing, width, kind="doors", depth=24.0, height=34.75, drawers=3, top=False, glass=False, rgb=None,
            wood=False, counter_rgb=None, pulls="bar", hardware="black_metal", room="", source=None):
    """One cabinet standing on the floor on its own: a base cabinet, a pantry, a console or sideboard.
    kind    'doors' (a drawer over doors; one door up to 21 wide, otherwise a pair) | 'drawers' (a stack of
            `drawers`) | 'tall' (pantry: two tiers of doors; give height 84 or so) | 'sink' (as 'doors', but the
            drawer front is fixed and the top is open for the bowl of a sink() in the counter() above)
    height  of the cabinet box. top: True adds a 1.25 counter slab on it, overhanging the front 1 and the ends 0.5
            (a console; cover several cabinets with one counter() instead)
    glass   frosted glass in the doors instead of a panel"""
    with _part(x, y, facing, room, source):
        k = _style(rgb, wood, pulls, hardware)
        _base(name, 0, width, kind, depth, height, k, drawers, glass)
        _boxes(name + "_ends", [(u, u + 0.75, depth - 3, depth - 0.75, 0, 4) for u in (0, width - 0.75)], k["m"])
        if top:
            box(name + "_top", -0.5, width + 0.5, 0, depth + 1, height, height + T, mat("counter", counter_rgb))
        core.footprint(name, 0, width, 0, depth, height + (T if top else 0))


def counter(name, x, y, facing, length, depth=25.5, z=36.0, thick=1.25, rgb=None, round_end=None, room="", source=None):
    """A counter slab on its own, for a peninsula, a raised bar on a knee wall or an island: `length` along the
    wall by `depth` out from it, its top at height z. base_run already makes its own counters.
    round_end   'left' | 'right' | None: that end finishes in a half circle (within `length`)
    Returns the slab, to pass to sink(counter=...)."""
    with _part(x, y, facing, room, source):
        return _slab(name, 0, length, depth, z, thick, mat("counter", rgb), round_end)


def sink(name, x, y, facing, width=28.0, bowls=1, faucet="black_metal", counter=None, depth=25.5, z=36.0, thick=1.25,
         room="", source=None):
    """An undermount sink and gooseneck faucet for a counter made with counter(); base_run's 'sink' has its own.
    (x, y) is the bowl's left end on the counter's back edge; the bowl is `width` wide and sits 4.75 in from the
    back and front of a counter `depth` deep, with the faucet behind it.
    counter   the slab counter() returned, in which the bowl's hole is cut; z, thick: that counter's top and thickness
    bowls     1 | 2;  faucet: its metal ('black_metal', 'chrome', 'stainless', 'nickel', 'brass')"""
    with _part(x, y, facing, room, source):
        _sink(name, 0, width, 4.75, depth - 4.75, z, thick, bowls, faucet, counter)


def fridge(name, x, y, facing, width=33.0, depth=30.5, height=66.5, finish="stainless", hinge="right", room="", source=None):
    """Top-freezer refrigerator. hinge: 'right' puts the hinges right and the handles left, as seen from the room."""
    with _part(x, y, facing, room, source):
        _fridge(name, 0, width, depth, height, finish, hinge)
        core.footprint(name, 0, width, 0, depth + 1, height)


def range_(name, x, y, facing, width=30.0, kind="coil", finish="stainless", room="", source=None):
    """Free-standing electric range, 27 deep with the cooktop at 36 and a backguard with knobs.
    kind    'coil' (four coil burners) | 'glass' (smooth black top)"""
    with _part(x, y, facing, room, source):
        _range(name, 0, width, kind, finish)
        core.footprint(name, 0, width, 0, 27, 36)


def dishwasher(name, x, y, facing, width=24.0, depth=24.0, height=34.5, finish="stainless", room="", source=None):
    """Built-in dishwasher, to stand under a counter() (base_run's 'dishwasher' has its own counter)."""
    with _part(x, y, facing, room, source):
        _dishwasher(name, 0, width, depth, height, finish)
        core.footprint(name, 0, width, 0, depth, height)


def microwave(name, x, y, facing, z, width=30.0, height=17.0, depth=15.5, finish="stainless", room="", source=None):
    """Over-the-range microwave on the wall with its underside at height z (upper_run's 'microwave' has its own)."""
    with _part(x, y, facing, room, source):
        _microwave(name, 0, width, z, height, depth, finish)
