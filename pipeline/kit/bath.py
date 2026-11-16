"""Bathroom parts. Each stands against a wall: (x, y) is a plan point on the wall face, at the middle of the part,
and `facing` is the compass letter the part faces, out from that wall into the room ('N' is up the page).
'left' and 'right' are as seen by someone in the room looking at the part. Heights are above the floor.
`hardware` is a metal key of the vocabulary: 'black_metal', 'chrome', 'nickel' or 'brass'.
Call these before shell.build(), so baseboards stop at the parts that stand on the floor."""
import math

import bmesh

from . import core, lights
from .core import at, box, cyl, mat, prism, tag, tube

WHITE = (240, 240, 236)


def _part(room, source):
    return tag(group="C", coll="bath", room=room, **({"source": source} if source else {}))


def _ellipse(cu, cv, ru, rv, n=40):
    return [(cu + ru * math.cos(2 * math.pi * i / n), cv + rv * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _rrect(u0, u1, v0, v1, r, n=6):
    pts = []
    for cu, cv, a0 in ((u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180), (u1 - r, v0 + r, 270)):
        pts += [(cu + r * math.cos(math.radians(a0 + 90 * k / n)), cv + r * math.sin(math.radians(a0 + 90 * k / n))) for k in range(n + 1)]
    return pts


def _bowl(name, c, radii, material, inside=False):
    """Lower half of an ellipsoid, open at the top; `inside` turns its faces inward, for a basin."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_outer=True)
    if inside:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.scale(bm, vec=radii, verts=bm.verts)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    return core.emit(name, bm, material, True)


def _trim(name, hw, valve_z, head_z, spout_z=None):
    """Shower valve, arm and head (and a tub spout), in a frame on the wall they come out of."""
    cyl(name + "_valve_plate", (0, valve_z), 0, 0.3, 3.2, hw, axis="v")
    cyl(name + "_valve_handle", (0, valve_z), 0.3, 2.5, 0.5, hw, axis="v")
    box(name + "_valve_lever", -0.3, 0.3, 1.9, 2.5, valve_z - 3.0, valve_z, hw)
    if spout_z:
        cyl(name + "_spout", (0, spout_z), 0, 5.2, 0.7, hw, axis="v")
    cyl(name + "_shower_flange", (0, head_z), 0, 0.25, 1.2, hw, axis="v")
    tube(name + "_shower_arm", [(0, 0, head_z), (0, 4.0, head_z + 0.5), (0, 6.5, head_z - 0.8)], 0.35, hw)
    cyl(name + "_shower_head", (0, 6.5), head_z - 2.4, head_z - 0.8, 2.4, hw, r1=0.8)


def tub(name, x, y, facing, length=60.0, width=30.0, height=15.5, surround=78.0, surround_key="wall_tile", shelves=0,
        valve="left", hardware="chrome", enclosure="curtain", drawn=0.2, curtain_rgb=WHITE, room="", source=None):
    """Alcove tub. (x, y) is the middle of its long side on the back wall; `facing` is the way its apron faces. It
    expects a wall at both ends, `length` apart.
    surround      height of the top of the wall finish on the three walls, or None for bare walls
    surround_key  'wall_tile', 'stone_tile', or 'porcelain' for a one-piece acrylic surround
    shelves       soap shelves moulded into the back wall (acrylic surrounds)
    valve         end wall with the valve, spout and shower head: 'left' | 'right' | None
    enclosure     'curtain' (on a rod) | 'rod' (bare rod) | 'glass' (sliding doors on the rim) | None
    drawn         how much of the length the curtain covers, gathered at the end away from the valve (1.0 = closed)"""
    L, m, hw = length / 2, mat("porcelain"), mat(hardware)
    s = {"left": -1, "right": 1}.get(valve, 0)
    e = -s or 1   # the end away from the valve
    t = 0.3 if surround else 0.0
    with _part(room, source), at(x, y, facing):
        core.cut(box(name, -L, L, 0, width, 0, height, m), [box("cut", -L + 3, L - 3, 2.5, width - 3.5, 2.0, height + 1, None)])
        cyl(name + "_drain", (-e * (L - 5.5), width / 2 - 0.5), 2.0, 2.1, 1.2, mat("chrome"))
        if surround:
            ms = mat(surround_key)
            box(name + "_surround_back", -L, L, 0, t, height, surround, ms)
            for i in (-1, 1):
                box(name + "_surround_end", *sorted((i * L, i * (L - t))), t, width, height, surround, ms)
            for i in range(shelves):
                box(name + "_shelf", *sorted((-e * (L - 12), -e * (L - 26))), t, 3.5, 44.0 + 14 * i, 44.6 + 14 * i, ms)
        if s:
            with at(s * (L - t), width / 2 - 0.5, 180 + 90 * s):
                _trim(name, hw, height + 16.5, height + 58.5, height + 5.5)
        vr, zr = width - 1.5, height + 61.5
        if enclosure in ("curtain", "rod"):
            cyl(name + "_rod", (vr, zr), -L, L, 0.5, hw, axis="u")
        if enclosure == "curtain":
            ua, ub = e * (L - 0.8), e * (L - 0.8 - max(drawn * length - 1.6, 10.0))
            n, amp = 60, 1.6 - drawn
            bm = bmesh.new()
            rows = [[bm.verts.new((ua + (ub - ua) * i / n, vr + amp * math.sin(i / n * math.pi * 14), z)) for i in range(n + 1)]
                    for z in (7.0, zr - 0.8)]
            for i in range(n):
                bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
            core.emit(name + "_curtain", bm, mat("fabric", curtain_rgb), True)
            for i in range(12):
                cyl(name + "_curtain_ring", (ua + (ub - ua) * (i + 0.5) / 12, zr), vr - 0.15, vr + 0.15, 0.9, hw, axis="v", seg=12)
        elif enclosure == "glass":
            zt = height + 58.0
            for z0, z1 in ((height, height + 0.6), (zt, zt + 1.4)):
                box(name + "_door_track", -L + t, L - t, width - 2.8, width - 0.4, z0, z1, hw)
            for i in (-1, 1):
                box(name + "_door_jamb", *sorted((i * (L - t), i * (L - t - 0.8))), width - 2.8, width - 0.4, height + 0.6, zt, hw)
                v = width - 1.6 - 0.6 * i * e   # the panel at the valve end slides on the room side and carries the pull
                box(name + "_door_glass", *sorted((i * (L - t - 0.8), -i * 1.5)), v - 0.15, v + 0.15, height + 0.6, zt, mat("glass"))
            ub = -e * 4.0
            box(name + "_door_pull", ub - 0.3, ub + 0.3, width + 0.1, width + 0.6, height + 22, height + 34, hw)
            for z in (height + 23, height + 33):
                box(name + "_door_pull_post", ub - 0.25, ub + 0.25, width - 0.85, width + 0.1, z - 0.25, z + 0.25, hw)
        core.footprint(name, -L, L, 0, width, height)


def shower(name, x, y, facing, width=36.0, depth=36.0, height=84.0, tile="wall_tile", valve="left", glass_side=None,
           hardware="chrome", room="", source=None):
    """Shower stall with a base, tiled walls and a glass front with a door. (x, y) is the middle of its back wall;
    `facing` is the way the door faces. The door is at the end away from the valve; a front wider than 30" also gets
    a fixed panel.
    height      top of the tile
    tile        'wall_tile' | 'stone_tile' | 'porcelain' (acrylic)
    valve       wall with the valve and shower head: 'left' | 'right' | 'back'
    glass_side  None when there is a wall at both ends (alcove), or 'left' | 'right' for a corner stall whose
                that end is a fixed glass panel instead of a wall"""
    W, m, hw, mg = width / 2, mat(tile), mat(hardware), mat("glass")
    s = {"left": -1, "right": 1}.get(valve, 0)
    g = {"left": -1, "right": 1}.get(glass_side, 0)
    e = -s or -g or 1   # the door's end
    zt, vf = 76.0, depth - 1.0
    with _part(room, source), at(x, y, facing):
        core.cut(box(name + "_base", -W, W, 0, depth, 0, 4.0, mat("porcelain")), [box("cut", -W + 2.5, W - 2.5, 2.5, depth - 2.5, 1.5, 5, None)])
        cyl(name + "_drain", (0, depth / 2), 1.5, 1.6, 1.6, mat("chrome"))
        box(name + "_tile_back", -W, W, 0, 0.4, 4.0, height, m)
        for i in (-1, 1):
            if i == g:
                box(name + "_glass_side", *sorted((i * (W - 0.85), i * (W - 0.55))), 0.4, vf - 0.4, 4.0, zt, mg)
                box(name + "_frame", *sorted((i * (W - 1.1), i * (W - 0.3))), 0.4, vf + 0.4, zt, zt + 1.0, hw)
            else:
                box(name + "_tile_end", *sorted((i * W, i * (W - 0.4))), 0.4, depth, 4.0, height, m)
            box(name + "_frame", *sorted((i * (W - 1.1), i * (W - 0.3))), vf - 0.4, vf + 0.4, 4.0, zt, hw)
        box(name + "_frame", -W + 0.3, W - 0.3, vf - 0.4, vf + 0.4, zt, zt + 1.0, hw)
        ua, ub = e * (W - 1.1), e * (W - 1.1 - min(width - 2.2, 28.0))   # the door, hinge edge first
        box(name + "_door", *sorted((ua, ub)), vf - 0.15, vf + 0.15, 4.3, zt, mg)
        if abs(ub + e * (W - 1.1)) > 0.1:
            box(name + "_glass_front", *sorted((ub - e * 0.1, -e * (W - 1.1))), vf - 0.15, vf + 0.15, 4.0, zt, mg)
        for z in (14.0, 66.0):
            box(name + "_door_hinge", *sorted((ua + e * 0.2, ua - e * 1.6)), vf - 0.4, vf + 0.4, z - 1.5, z + 1.5, hw)
        up = ub + e * 2.5
        box(name + "_door_pull", up - 0.3, up + 0.3, vf + 1.0, vf + 1.5, 38, 50, hw)
        for z in (39, 49):
            box(name + "_door_pull_post", up - 0.25, up + 0.25, vf + 0.15, vf + 1.0, z - 0.25, z + 0.25, hw)
        with at(s * (W - 0.4), depth / 2 if s else 0.4, 180 + 90 * s if s else 0):
            _trim(name, hw, 46.0, 80.0)
        core.footprint(name, -W, W, 0, depth, zt)


def toilet(name, x, y, facing, room="", source=None):
    """Two-piece elongated toilet, 20" wide and 28" out from the wall. (x, y) is the point on the wall behind the
    middle of the tank."""
    m, ch = mat("porcelain"), mat("chrome")
    with _part(room, source), at(x, y, facing):
        prism(name + "_tank", _rrect(-9.75, 9.75, 1.0, 8.5, 2.2), 15.5, 30.0, m)
        prism(name + "_tank_lid", _rrect(-10.1, 10.1, 0.6, 9.0, 2.4), 30.0, 31.0, m)
        box(name + "_lever", -7.8, -5.5, 8.5, 9.4, 27.0, 27.6, ch)
        prism(name + "_pedestal", _ellipse(0, 14.5, 4.6, 7.5), 0, 10.0, m)
        _bowl(name + "_bowl", (0, 17.0, 15.0), (7.4, 11.0, 6.5), m)
        box(name + "_neck", -6.0, 6.0, 6.0, 11.0, 9.0, 15.5, m)
        prism(name + "_seat", _ellipse(0, 17.5, 7.5, 10.9), 15.0, 15.8, m)
        prism(name + "_lid", _ellipse(0, 17.3, 7.1, 10.4), 15.8, 16.6, m)
        box(name + "_hinge", -4.5, 4.5, 6.3, 7.8, 15.2, 16.4, m)
        cyl(name + "_supply_valve", (5.5, 7.7), 0, 1.4, 0.6, ch, axis="v")
        tube(name + "_supply", [(5.5, 1.2, 7.7), (5.5, 2.2, 7.7), (5.5, 2.6, 12.0), (6.5, 2.6, 15.5)], 0.18, ch)
        core.footprint(name, -10, 10, 1.0, 28.5, 31.0)   # clear of the wall, so the baseboard runs on behind


def _front(name, u0, u1, z0, z1, vf, m, style):
    """Door or drawer front whose face is at v = vf."""
    u0, u1, z0, z1 = u0 + 0.07, u1 - 0.07, z0 + 0.07, z1 - 0.07
    if style != "shaker":
        return box(name, u0, u1, vf - 0.75, vf, z0, z1, m)
    box(name, u0, u1, vf - 0.75, vf - 0.25, z0, z1, m)
    fr = min(2.25, (u1 - u0) / 4, (z1 - z0) / 4)
    for a, b, c, d in ((u0, u0 + fr, z0, z1), (u1 - fr, u1, z0, z1), (u0 + fr, u1 - fr, z0, z0 + fr), (u0 + fr, u1 - fr, z1 - fr, z1)):
        box(name + "_frame", a, b, vf - 0.25, vf, c, d, m)


def _pull(name, u, z, vf, kind, hw, upright):
    if kind == "knob":
        cyl(name, (u, z), vf, vf + 0.5, 0.3, hw, axis="v")
        cyl(name, (u, z), vf + 0.5, vf + 1.1, 0.6, hw, axis="v")
    elif kind == "bar":
        du, dz = (0.22, 2.5) if upright else (2.5, 0.22)
        box(name, u - du, u + du, vf + 0.93, vf + 1.37, z - dz, z + dz, hw)
        for k in (-1, 1):
            pu, pz = (u, z + k * 1.9) if upright else (u + k * 1.9, z)
            box(name + "_post", pu - 0.18, pu + 0.18, vf, vf + 0.93, pz - 0.18, pz + 0.18, hw)


def vanity(name, x, y, facing, width=30.0, depth=21.0, height=32.5, doors=2, drawers=0, drawer_side="right", style="shaker",
           false_front=True, cabinet="cabinet_paint", rgb=None, pulls="bar", hardware="black_metal", faucet="centerset",
           sinks=1, counter_rgb=None, room="", source=None):
    """Vanity cabinet with a counter, backsplash, oval sink and faucet. (x, y) is the middle of its back on the wall.
    The front is `doors` equal doors, plus one stack of `drawers` drawers as wide as a door on `drawer_side`.
    height        top of the cabinet; the counter is 1.25" thicker and overhangs 1" at the front, 0.5" at the ends
    style         'shaker' (framed fronts) | 'slab'
    false_front   fixed panel above the doors, as a sink base has
    cabinet, rgb  'cabinet_paint' or 'cabinet_wood', and its colour
    pulls         'bar' | 'knob' | None, in the `hardware` metal, as is the faucet
    faucet        'centerset' (spout and two handles) | 'single' (one lever)
    sinks         1, or 2 for a double vanity"""
    W, vf, top = width / 2, depth, height + 1.25
    mc, hw, mt, mp = mat(cabinet, rgb), mat(hardware), mat("counter", counter_rgb), mat("porcelain")
    bw = width / (doors + (1 if drawers else 0))
    with _part(room, source), at(x, y, facing):
        box(name + "_carcass", -W, W, 0, vf - 0.75, 3.5, height, mc)
        box(name + "_kick", -W, W, 0, vf - 3.0, 0, 3.5, mc)
        u0 = -W + (bw if drawers and drawer_side == "left" else 0)
        zd = height - 7.0 if false_front else height
        if doors and false_front:
            _front(name + "_false_front", u0, u0 + doors * bw, zd, height, vf, mc, style)
        for i in range(doors):
            _front("%s_door_%d" % (name, i), u0 + i * bw, u0 + (i + 1) * bw, 3.75, zd, vf, mc, style)
            # doors pair up, so the pulls meet in the middle of each pair
            _pull(name + "_pull", u0 + (i + 1) * bw - 1.6 if i % 2 == 0 else u0 + i * bw + 1.6, zd - 5.0, vf, pulls, hw, True)
        ud = -W if drawer_side == "left" else W - bw
        for i in range(drawers):
            z0, z1 = (3.75 + (height - 3.75) * k / drawers for k in (i, i + 1))
            _front("%s_drawer_%d" % (name, i), ud, ud + bw, z0, z1, vf, mc, style)
            _pull(name + "_pull", ud + bw / 2, (z0 + z1) / 2, vf, pulls, hw, False)
        ctr = box(name + "_top", -W - 0.5, W + 0.5, 0, vf + 1.0, height, top, mt)
        box(name + "_backsplash", -W - 0.5, W + 0.5, 0, 0.75, top, top + 3.0, mt)
        vs = vf / 2 + 0.5
        for i in range(sinks):
            uc = (i - (sinks - 1) / 2) * W
            core.cut(ctr, [core.ellipsoid("cut", (uc, vs, top), (8.5, 6.8, 4.5), None)])
            _bowl(name + "_sink", (uc, vs, top), (8.45, 6.75, 4.45), mp, inside=True)   # a hair smaller, to sit inside the cut
            cyl(name + "_sink_drain", (uc, vs), top - 4.45, top - 4.3, 0.8, mat("chrome"))
            if faucet == "single":
                cyl(name + "_faucet", (uc, 2.8), top, top + 5.0, 0.8, hw)
                box(name + "_faucet_spout", uc - 0.4, uc + 0.4, 2.6, 7.4, top + 3.4, top + 4.2, hw)
                box(name + "_faucet_lever", uc - 0.3, uc + 0.3, 2.2, 5.2, top + 5.0, top + 5.5, hw)
            else:
                box(name + "_faucet_base", uc - 3.2, uc + 3.2, 1.2, 3.8, top, top + 0.8, hw)
                cyl(name + "_faucet", (uc, 2.5), top + 0.8, top + 4.5, 0.55, hw)
                tube(name + "_faucet_spout", [(uc, 2.5, top + 4.3), (uc, 4.5, top + 5.2), (uc, 6.0, top + 4.2), (uc, 6.4, top + 3.4)], 0.4, hw)
                for k in (-2.6, 2.6):
                    cyl(name + "_faucet_handle", (uc + k, 2.5), top + 0.8, top + 2.2, 0.45, hw)
                    box(name + "_faucet_handle", uc + k - 0.25, uc + k + 0.25, 2.2, 4.4, top + 2.0, top + 2.5, hw)
        core.footprint(name, -W - 0.5, W + 0.5, 0, vf + 1.0, top)


def mirror(name, x, y, facing, width=20.0, height=30.0, z=46.0, kind="framed", frame="black_metal", shelf=False, lit=False,
           room="", source=None):
    """Wall mirror; z is its bottom edge.
    kind   'framed' (1" frame in the `frame` metal) | 'plain' (frameless glass) | 'cabinet' (white medicine
           cabinet standing 4.5" off the wall, with a mirror door)
    shelf  ledge with a rail under the mirror, in the frame metal
    lit    glowing LED strip down each side, which lights the room"""
    W, mm, mf = width / 2, mat("mirror"), mat(frame)
    with _part(room, source), at(x, y, facing):
        if kind == "framed":
            box(name + "_frame", -W, W, 0, 1.0, z, z + height, mf)
            box(name, -W + 1.0, W - 1.0, 1.0, 1.05, z + 1.0, z + height - 1.0, mm)
        elif kind == "cabinet":
            box(name + "_cabinet", -W, W, 0, 4.5, z, z + height, mat("plastic"))
            box(name, -W, W, 4.6, 4.85, z, z + height, mm)
        else:
            box(name, -W, W, 0, 0.25, z, z + height, mm)
        if shelf:
            box(name + "_shelf", -W, W, 0, 4.5, z - 1.4, z - 0.8, mf)
            box(name + "_shelf_rail", -W, W, 4.3, 4.6, z + 0.4, z + 0.7, mf)
            for u in (-W, W - 0.3):
                box(name + "_shelf_end", u, u + 0.3, 0, 4.6, z - 1.4, z + 0.7, mf)
        if lit:
            for i in (-1, 1):
                box(name + "_led", *sorted((i * (W + 0.2), i * (W + 1.6))), 0, 0.5, z, z + height, mat("emit_warm"))
                lights.bulb("%s_led_%s" % (name, "LR"[i > 0]), i * (W + 0.9), 2.5, z + height / 2, 6.0)


def vanity_light(name, x, y, facing, z=81.0, width=24.0, bulbs=3, hardware="black_metal", watts=4.0, room="", source=None):
    """Bar light over a mirror: `bulbs` frosted shades hanging from a bar `width` long whose underside is at z. Each
    shade has its own lamp of `watts`."""
    W, hw = width / 2, mat(hardware)
    with _part(room, source), at(x, y, facing):
        box(name, -W, W, 0, 1.1, z, z + 1.4, hw)
        for i in range(bulbs):
            u = (i - (bulbs - 1) / 2) * (width - 6.0) / max(bulbs - 1, 1)
            box(name + "_arm", u - 0.3, u + 0.3, 1.1, 4.0, z + 0.4, z + 1.0, hw)
            cyl(name + "_cup", (u, 4.0), z + 0.5, z + 1.8, 1.0, hw)
            cyl(name + "_shade", (u, 4.0), z - 4.0, z + 0.5, 1.6, mat("frosted_glass"))
            cyl(name + "_lens", (u, 4.0), z - 4.06, z - 4.0, 1.35, mat("emit_warm"))
            # the shade is opaque to Cycles, so the lamp hangs just under it
            lights.bulb("%s_bulb_%d" % (name, i), u, 4.0, z - 5.2, watts, 0.8)


def _towel(name, w, v0, v1, z, front, back, rgb):
    """Towel folded over something at height z: flaps hang at v0 (behind) and v1 (in front)."""
    m = mat("fabric", WHITE if rgb is True else rgb)
    box(name, -w / 2, w / 2, v1, v1 + 0.45, z - front, z + 0.45, m)
    box(name, -w / 2, w / 2, v0 - 0.45, v0, z - back, z + 0.45, m)
    box(name, -w / 2, w / 2, v0, v1, z, z + 0.45, m)


def towel_bar(name, x, y, facing, z=60.0, length=24.0, hardware="black_metal", towel=None, room="", source=None):
    """Towel bar `length` long centred on (x, y) at height z. towel: True for a white bath towel folded over the
    middle of the bar, or its (r, g, b)."""
    L, hw = length / 2, mat(hardware)
    with _part(room, source), at(x, y, facing):
        box(name, -L, L, 2.2, 2.7, z - 0.25, z + 0.25, hw)
        for i in (-1, 1):
            box(name + "_post", *sorted((i * (L - 0.1), i * (L + 1.1))), 0, 2.8, z - 0.65, z + 0.65, hw)
        if towel:
            _towel(name + "_towel", min(14.0, length - 4), 2.15, 2.75, z + 0.25, 24.0, 20.0, towel)


def towel_ring(name, x, y, facing, z=55.0, hardware="black_metal", towel=None, room="", source=None):
    """Towel ring, 5" across, centred at height z. towel: True for a white hand towel through it, or its (r, g, b)."""
    hw = mat(hardware)
    with _part(room, source), at(x, y, facing):
        box(name + "_mount", -0.7, 0.7, 0, 0.9, z + 2.4, z + 4.2, hw)
        tube(name, [(2.6 * math.sin(a), 0.9, z + 2.6 * math.cos(a)) for a in (i * 2 * math.pi / 24 for i in range(25))], 0.2, hw)
        if towel:
            _towel(name + "_towel", 7.0, 0.65, 1.15, z - 2.4, 17.0, 14.0, towel)


def paper_holder(name, x, y, facing, z=26.0, hardware="black_metal", roll=True, room="", source=None):
    """Toilet-paper holder centred at height z, with a roll on it unless roll=False."""
    hw = mat(hardware)
    with _part(room, source), at(x, y, facing):
        box(name + "_mount", 2.5, 3.9, 0, 0.5, z - 1.0, z + 1.0, hw)
        box(name + "_arm", 2.9, 3.5, 0.5, 3.4, z - 0.3, z + 0.3, hw)
        cyl(name, (3.1, z), -3.0, 3.5, 0.3, hw, axis="u")
        if roll:
            cyl(name + "_roll", (3.1, z), -2.4, 2.1, 2.3, mat("fabric", (246, 246, 242)), axis="u")
