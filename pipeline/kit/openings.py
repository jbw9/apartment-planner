"""Doors and windows. Each one finds the wall under its plan point, cuts its own opening and brings its frame,
casing and hardware, so a door is never left without a handle."""
import math

import bmesh

from . import core
from .core import at, box, cyl, mat, tag

J, CW, CT = 0.75, 2.5, 0.625   # jamb thickness, casing width and thickness


def _frame(along, a, b, c0, c1, side):
    """Origin and facing of the local frame for an opening seen from compass side `side`: u runs 0..b-a from the
    viewer's left, v is 0 on the near wall face and negative through the wall."""
    return {"S": (a, c1, "S"), "N": (b, c0, "N"), "E": (c1, b, "E"), "W": (c0, a, "W")}[side]


def _leaf(name, width, thick, height, panels, handle, hw, m, handle_u=None, both=True, deadbolt=False, hinges=True):
    """Door leaf in its own frame: u 0..width from the hinge edge, v across its thickness, centred."""
    t, z0 = thick, 0.5
    box(name, 0, width, -t / 2 + 0.25, t / 2 - 0.25, z0, z0 + height, m)
    st = 4.5 if width > 20 else 3.0
    rails = {0: [], 1: [(0, 6), (height - 4.5, height)], 2: [(0, 8), (34, 42), (height - 4.5, height)]}[panels]
    for s in (-1, 1):
        va, vb = sorted((s * (t / 2 - 0.25), s * t / 2))
        if panels == 0:
            box(name + "_face", 0, width, va, vb, z0, z0 + height, m)
            continue
        box(name + "_stile", 0, st, va, vb, z0, z0 + height, m)
        box(name + "_stile", width - st, width, va, vb, z0, z0 + height, m)
        for r0, r1 in rails:
            box(name + "_rail", st, width - st, va, vb, z0 + r0, z0 + r1, m)
    hu = width - 2.75 if handle_u is None else handle_u
    toward = -1 if hu > width / 2 else 1   # a lever points back across the leaf
    for s in ((-1, 1) if both else (1,)):
        vf = s * t / 2
        if handle == "lever":
            box(name + "_rose", hu - 1.1, hu + 1.1, *sorted((vf, vf + s * 0.45)), 35.4, 37.6, hw)
            box(name + "_lever", *sorted((hu - 0.4 * toward, hu + 4.3 * toward)), *sorted((vf + s * 0.45, vf + s * 1.6)), 36.2, 36.8, hw)
        elif handle == "knob":
            cyl(name + "_rose", (hu, 36.5), *sorted((vf, vf + s * 0.4)), 1.3, hw, axis="v")
            core.ellipsoid(name + "_knob", (hu, vf + s * 1.7, 36.5), (1.1, 0.9, 1.1), hw)
        elif handle == "pull":
            box(name + "_pull", hu - 0.3, hu + 0.3, *sorted((vf + s * 0.9, vf + s * 1.4)), 33, 41, hw)
            for z in (33.6, 40.4):
                box(name + "_pull_post", hu - 0.25, hu + 0.25, *sorted((vf, vf + s * 0.9)), z - 0.25, z + 0.25, hw)
        elif handle == "finger":
            box(name + "_cup", hu - 0.8, hu + 0.8, *sorted((vf, vf + s * 0.08)), 35.2, 36.8, hw)
        if deadbolt:
            cyl(name + "_bolt", (hu, 42.5), *sorted((vf, vf + s * 0.45)), 1.1, hw, axis="v")
    if hinges:
        for hz in (7.0, 40.0, 73.0):
            box(name + "_hinge", -0.15, 0.25, -0.5, 0.5, hz, hz + 3.5, mat("nickel"))


def door(shell, name, x, y, width, kind="hinged", swing="S", hinge="left", angle=0.0, height=80.0, panels=2, handle="lever",
         handles="both", hardware="black_metal", rgb=None, thick=1.375, deadbolt=False, peephole=False, threshold=False,
         casing=(True, True), room="", source=None, along=None):
    """A door in the wall under plan point (x, y), the middle of the opening.
    width   leaf width (both leaves together for 'double', 'bypass' and 'bifold'; clear width for 'opening')
    kind    'hinged' | 'double' | 'bypass' (sliding closet pair) | 'bifold' | 'opening' (cased, no leaf)
    swing   compass side of the wall the leaf opens into ('N' is up the page); for sliders, the side they are seen from
    hinge   'left' or 'right' as seen from that side; angle: degrees open
    panels  recessed panels per leaf: 0 flat, 1, or 2
    handle  'lever' | 'knob' | 'pull' | 'finger' | None; handles: 'both', 'left' or 'right' leaf of a double door
    casing  (near side, far side) trim, near being the swing side"""
    w, along, a, b, c0, c1 = shell.opening(x, y, width + 2 * J + 0.25, along)
    h = height + 2.0
    shell.box_hole(name, along, a, b, c0, c1, -1, h, doorway=True)
    L, t = b - a, c1 - c0
    m, mt, hw = mat("door_paint", rgb), shell.m_trim, mat(hardware)
    mid = (a + b) / 2
    inside = [shell.has_room(*((mid, c) if along == "x" else (c, mid))) for c in (c0 - 2, c1 + 2)]
    if kind != "opening" and inside.count(True) == 1:
        # a door out of the unit: without a dark panel behind it, daylight bakes in around the leaf's edges
        f0, f1 = (c1, c1 + 0.5) if inside[0] else (c0 - 0.5, c0)
        with tag(group="A", coll="doors", room=room):
            box(name + "_beyond", *((a - 1, b + 1, f0, f1) if along == "x" else (f0, f1, a - 1, b + 1)), 0, h + 1, mat("black_metal"))
    with tag(group="B", coll="doors", room=room, **({"source": source} if source else {})), at(*_frame(along, a, b, c0, c1, swing)):
        box(name + "_jamb", 0, J, -t, 0, 0, h - J, mt)
        box(name + "_jamb", L - J, L, -t, 0, 0, h - J, mt)
        box(name + "_head", 0, L, -t, 0, h - J, h, mt)
        for on, v0, v1 in ((casing[0], 0, CT), (casing[1], -t - CT, -t)):
            if on:
                box(name + "_casing", -CW, 0, v0, v1, 0, h, mt)
                box(name + "_casing", L, L + CW, v0, v1, 0, h, mt)
                box(name + "_casing", -CW, L + CW, v0, v1, h, h + CW, mt)
        if threshold:
            box(name + "_threshold", J, L - J, -t, 0, 0, 0.4, mat("nickel"))
        clear = L - 2 * J - 0.2
        if kind == "hinged":
            hu, d = (J + 0.1, -angle) if hinge == "left" else (L - J - 0.1, 180 + angle)
            with at(hu, -thick / 2, d):
                _leaf(name + "_leaf", clear, thick, height, panels, handle, hw, m, deadbolt=deadbolt)
                if peephole:
                    cyl(name + "_peephole", (clear / 2, 60), -thick / 2 - 0.1, thick / 2 + 0.1, 0.35, hw, axis="v")
        elif kind == "double":
            lw = clear / 2 - 0.06
            for side, hu, d in (("left", J + 0.1, -angle), ("right", L - J - 0.1, 180 + angle)):
                with at(hu, -thick / 2, d):
                    _leaf("%s_leaf_%s" % (name, side), lw, thick, height, panels, handle if handles in ("both", side) else None, hw, m)
        elif kind == "bypass":
            lw = clear / 2 + 1.0
            box(name + "_track", J, L - J, -3.6, -0.4, height + 0.3, height + 0.8, mat("nickel"))
            for i, (u0, v) in enumerate(((J, -1.2), (L - J - lw, -2.9))):
                with at(u0, v):
                    _leaf("%s_panel_%d" % (name, i), lw, 1.25, height - 1, panels, handle and "finger", hw, m,
                          handle_u=lw - 2.0 if i == 0 else 2.0, hinges=False)
        elif kind == "bifold":
            n = 4 if clear > 40 else 2
            pw = clear / n
            for i in range(n):
                with at(J + 0.1 + i * pw, -thick / 2):
                    knob = n == 2 and i == 1 or n == 4 and i in (1, 2)
                    _leaf("%s_panel_%d" % (name, i), pw - 0.1, thick, height, panels, "knob" if knob and handle else None, hw, m,
                          handle_u=(2.0 if i == 2 else pw - 2.0), both=False, hinges=False)
    return dict(name=name, along=along, a=a, b=b)


def window(shell, name, x, y, width, sill, height, top="flat", style="single_hung", blinds=True, stool=True, rgb=None,
           room="", source=None, along=None):
    """A window in the wall under plan point (x, y), the middle of the opening.
    sill    height of the bottom of the opening above the floor (0 for a sliding patio door)
    height  of the rectangular part; top='arch' adds a half circle of radius width/2 above it
    style   'single_hung' | 'slider' (two panels side by side; with sill 0, a patio door) | 'fixed'
    blinds  True: fitted and raised, so daylight comes in | 'down': lowered | False: none"""
    w, along, a, b, c0, c1 = shell.opening(x, y, width, along)
    side = shell.room_side(along, (a + b) / 2, c0, c1)
    fr = _frame(along, a, b, c0, c1, side)
    L, t, zs, zt, R = b - a, c1 - c0, sill, sill + height, width / 2
    shell.box_hole(name, along, a, b, c0, c1, zs, zt)
    if top == "arch":
        def arch():
            with at(*fr):
                return cyl("cut", (R, zt), -t - 1, 1, R, None, axis="v", seg=48, smooth=False)
        x0, x1, y0, y1 = (a, b, c0 - 1, c1 + 1) if along == "x" else (c0 - 1, c1 + 1, a, b)
        shell.hole(arch, x0, x1, y0, y1, zt, zt + R)
    v1 = -min(2.0, max(t - 3.5, 0.2))   # frame face, set back from the room
    v0 = v1 - 3.0
    F, S = 2.0, 1.6
    mv, mg = mat("vinyl", rgb), mat("glass")
    with tag(group="B", coll="windows", room=room, **({"source": source} if source else {})), at(*fr):
        box(name + "_jamb", 0, F, v0, v1, zs + F, zt - F, mv)
        box(name + "_jamb", L - F, L, v0, v1, zs + F, zt - F, mv)
        box(name + "_sill", 0, L, v0, v1, zs, zs + F, mv)
        box(name + "_head", 0, L, v0, v1, zt - F, zt, mv)
        if top == "arch":
            seg = 40
            ring = lambda r: [(R + r * math.cos(math.pi * i / seg), zt + r * math.sin(math.pi * i / seg)) for i in range(seg + 1)]
            bm = bmesh.new()
            fo, fi, bo, bi = ([bm.verts.new((u, v, z)) for u, z in ring(r)] for v, r in ((v1, R), (v1, R - F), (v0, R), (v0, R - F)))
            for i in range(seg):
                for q in ((fo[i], fo[i + 1], fi[i + 1], fi[i]), (bo[i], bi[i], bi[i + 1], bo[i + 1]),
                          (fo[i], bo[i], bo[i + 1], fo[i + 1]), (fi[i], fi[i + 1], bi[i + 1], bi[i])):
                    bm.faces.new(q)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            core.emit(name + "_arch", bm, mv)
            bm = bmesh.new()
            bm.faces.new([bm.verts.new((u, (v0 + v1) / 2, z)) for u, z in ring(R - F)])
            core.emit(name + "_arch_glass", bm, mg)
        panes = []   # (u0, u1, z0, z1, v0, v1)
        zi0, zi1 = zs + F, zt - F
        if style == "single_hung":
            zm = (zi0 + zi1) / 2
            panes = [(F, L - F, zm - 0.6, zi1, v0 + 0.1, v0 + 1.4), (F, L - F, zi0, zm + 0.6, v0 + 1.5, v0 + 2.8)]
        elif style == "slider":
            um = L / 2
            panes = [(F, um + 0.6, zi0, zi1, v0 + 0.1, v0 + 1.4), (um - 0.6, L - F, zi0, zi1, v0 + 1.5, v0 + 2.8)]
        else:
            panes = [(F, L - F, zi0, zi1, v0 + 0.8, v0 + 2.1)]
        for i, (u0, u1, z0, z1, va, vb) in enumerate(panes):
            n = "%s_sash_%d" % (name, i)
            box(n, u0, u0 + S, va, vb, z0, z1, mv)
            box(n, u1 - S, u1, va, vb, z0, z1, mv)
            box(n, u0 + S, u1 - S, va, vb, z0, z0 + S, mv)
            box(n, u0 + S, u1 - S, va, vb, z1 - S, z1, mv)
            box("%s_glass_%d" % (name, i), u0 + S, u1 - S, (va + vb) / 2 - 0.1, (va + vb) / 2 + 0.1, z0 + S, z1 - S, mg)
        if stool and zs > 1:
            box(name + "_stool", -1.0, L + 1.0, v1, 0.9, zs - 0.75, zs, shell.m_trim)
            box(name + "_apron", -0.5, L + 0.5, 0, 0.5, zs - 3.25, zs - 0.75, shell.m_trim)
        if blinds:
            mb, vb_ = mat("blind"), v1 + 0.9
            zb = zt - 3.0
            # raised unless asked for down: lowered blinds cut the daylight in the room to a tenth
            za, pitch = (zs + 0.3, 0.9) if blinds == "down" else (zb - 5.0, 0.12)
            bm = bmesh.new()
            th = math.radians(18)
            dv, dz = 0.5 * math.cos(th), 0.5 * math.sin(th)
            for i in range(int((zb - za) / pitch)):
                zc = za + 0.6 + i * pitch
                bm.faces.new([bm.verts.new(p) for p in ((0.6, vb_ - dv, zc - dz), (L - 0.6, vb_ - dv, zc - dz), (L - 0.6, vb_ + dv, zc + dz), (0.6, vb_ + dv, zc + dz))])
            core.emit(name + "_blind_slats", bm, mb)
            box(name + "_blind_head", 0.4, L - 0.4, vb_ - 0.9, vb_ + 0.9, zb, zb + 1.6, mb)
            box(name + "_blind_rail", 0.6, L - 0.6, vb_ - 0.5, vb_ + 0.5, za, za + 0.6, mb)
    return dict(name=name, along=along, a=a, b=b, c0=c0, c1=c1, side=side, sill=sill, height=height + (R if top == "arch" else 0))
