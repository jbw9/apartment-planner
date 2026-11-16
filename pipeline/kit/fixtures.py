"""Lights, wall devices, closet shelves and utility appliances.
Ceiling parts take plan (x, y) and z, the height of the ceiling they hang from (a room's own, if it is lowered).
Wall parts take a plan point (x, y) on the wall face, at the middle of the part, and `facing`, the compass letter
the part faces, out from that wall into the room ('N' is up the page); their z is the height of their centre unless
stated. Every light fixture brings its own lamp, so a unit needs no lights beyond its fixtures.
Call these before shell.build(), so baseboards stop at the parts that stand on the floor."""
import math

import bmesh
from mathutils import Matrix

from . import core, lights
from .core import at, box, cyl, mat, tag, tube

FINISH = {"white": ("appliance_white", "appliance_black"), "stainless": ("stainless", "appliance_black"),
          "black": ("appliance_black", "stainless")}   # body, controls


def _part(room, source):
    return tag(group="C", coll="fixtures", room=room, **({"source": source} if source else {}))


def _boxes(name, boxes, material):
    """Boxes (u0, u1, v0, v1, z0, z1) as one object: a grille's slots or a shelf's wires would otherwise be dozens."""
    bm = bmesh.new()
    for u0, u1, v0, v1, z0, z1 in boxes:
        vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=(abs(u1 - u0), abs(v1 - v0), abs(z1 - z0)), verts=vs)
        bmesh.ops.translate(bm, vec=((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2), verts=vs)
    return core.emit(name, bm, material)


# ------------------------------------------------------------------ lights
def recessed_light(name, x, y, z, radius=2.8, watts=14.0, room="", source=None):
    """Recessed can light in the ceiling; radius is the lens's."""
    with _part(room, source):
        cyl(name + "_trim", (x, y), z - 0.25, z, radius + 0.6, mat("plastic"), seg=32)
        cyl(name, (x, y), z - 0.3, z - 0.25, radius, mat("emit_warm"), seg=32)
    return lights.lamp(name + "_lamp", x, y, z - 0.5, watts, radius - 0.3)


def flush_light(name, x, y, z, radius=6.0, watts=20.0, room="", source=None):
    """Round flush-mount ceiling light: a white drum 1.5" deep with a glowing lens."""
    with _part(room, source):
        cyl(name + "_rim", (x, y), z - 1.5, z, radius + 0.3, mat("plastic"), seg=32)
        cyl(name, (x, y), z - 1.56, z - 1.5, radius, mat("emit_warm"), seg=32)
    return lights.lamp(name + "_lamp", x, y, z - 1.8, watts, radius - 1.0)


def pendant(name, x, y, z, drop=36.0, shade="cage", hardware="black_metal", watts=8.0, room="", source=None):
    """Pendant on a cord; `drop` is from the ceiling down to the bottom of the shade.
    shade  'cage' (9" square open frame round a glass cylinder and bulb) | 'cone' (10" metal shade) |
           'globe' (8" glowing ball)"""
    hw, me = mat(hardware), mat("emit_warm")
    zb = z - drop
    with _part(room, source), at(x, y):
        if shade == "cage":
            s, zt = 4.5, zb + 10.5
            _boxes(name + "_cage", [(i * s - 0.15, i * s + 0.15, j * s - 0.15, j * s + 0.15, zb, zt) for i in (-1, 1) for j in (-1, 1)]
                   + [(i * s - 0.15, i * s + 0.15, -s, s, k - 0.15, k + 0.15) for i in (-1, 1) for k in (zb + 0.15, zt - 0.15)]
                   + [(-s, s, i * s - 0.15, i * s + 0.15, k - 0.15, k + 0.15) for i in (-1, 1) for k in (zb + 0.15, zt - 0.15)]
                   + [(-s, s, -0.15, 0.15, zt - 0.3, zt), (-0.15, 0.15, -s, s, zt - 0.3, zt)], hw)
            cyl(name + "_glass", (0, 0), zb + 1.5, zt - 0.5, 2.1, mat("glass"))
            cyl(name + "_bulb", (0, 0), zb + 3.4, zb + 7.5, 1.1, me)
            zl = zb + 2.4   # inside the glass, under the bulb, which would shadow a lamp at its centre
        elif shade == "cone":
            zt = zb + 6.0
            cyl(name + "_shade", (0, 0), zb, zt, 5.0, hw, r1=1.0)
            cyl(name + "_lens", (0, 0), zb - 0.06, zb, 4.2, me)
            zl = zb - 1.0
        else:
            zt = zb + 8.0
            core.ellipsoid(name + "_globe", (0, 0, zb + 4.0), (4.0, 4.0, 4.0), me)
            zl = zb - 1.0
        cyl(name + "_cap", (0, 0), zt - 0.4, zt + 0.8, 1.0, hw)
        cyl(name + "_cord", (0, 0), zt + 0.8, z - 0.5, 0.12, hw, seg=8)
        cyl(name + "_canopy", (0, 0), z - 1.2, z, 2.5, hw)
        return lights.bulb(name + "_lamp", 0, 0, zl, watts, 0.6)


def ceiling_fan(name, x, y, z, blades=4, span=52.0, light=True, rgb=None, watts=24.0, room="", source=None):
    """Ceiling fan on a short downrod; the blades turn 9" below the ceiling. span: blade tip to opposite tip.
    light: LED light kit under the motor. rgb: colour of the whole fan (default white)."""
    m = mat("plastic", rgb)
    with _part(room, source), at(x, y):
        cyl(name + "_canopy", (0, 0), z - 2.5, z, 2.6, m)
        cyl(name + "_downrod", (0, 0), z - 7.0, z - 2.5, 0.45, m, seg=12)
        cyl(name + "_motor", (0, 0), z - 11.0, z - 7.0, 4.2, m, seg=32)
        for k in range(blades):
            with at(0, 0, 45 + 360.0 * k / blades):
                box(name + "_blade_iron", 3.8, 7.5, -0.9, 0.9, z - 9.5, z - 9.15, m)
                bm = bmesh.new()
                bmesh.ops.create_cube(bm, size=1.0)
                bmesh.ops.scale(bm, vec=(span / 2 - 5.5, 5.2, 0.22), verts=bm.verts)
                bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(8), 3, "X"))
                bmesh.ops.translate(bm, vec=((span / 2 + 5.5) / 2, 0, z - 9.0), verts=bm.verts)
                core.emit(name + "_blade", bm, m)
        if not light:
            cyl(name + "_cap", (0, 0), z - 11.8, z - 11.0, 2.2, m)
            return None
        cyl(name + "_lightkit", (0, 0), z - 12.5, z - 11.0, 3.6, m, seg=32)
        cyl(name + "_lens", (0, 0), z - 12.6, z - 12.5, 3.2, mat("emit_warm"), seg=32)
        return lights.lamp(name + "_lamp", 0, 0, z - 12.9, watts, 3.0)


# ------------------------------------------------------------------ ceiling and wall devices
def vent(name, x, y, z, facing=None, width=12.0, height=8.0, room="", source=None):
    """Air register or exhaust grille. With `facing` it is on the wall at (x, y), centred at height z, `width` along
    the wall. Without, it is on the ceiling of height z, centred on (x, y), `width` along x and `height` along y."""
    W, Hh, n = width / 2, height / 2, max(2, int(height / 1.6))
    if facing:
        q = lambda a0, a1, b0, b1, d0, d1: (a0, a1, d0, d1, z + b0, z + b1)
    else:
        q = lambda a0, a1, b0, b1, d0, d1: (a0, a1, b0, b1, z - d1, z - d0)
    with _part(room, source), at(x, y, facing or "S"):
        box(name, *q(-W, W, -Hh, Hh, 0, 0.4), mat("plastic"))
        _boxes(name + "_slots", [q(-W + 0.8, W - 0.8, b - 0.25, b + 0.25, 0.38, 0.45)
                                 for b in ((Hh - 1.0) * (2 * i / (n - 1) - 1) for i in range(n))], mat("black_metal"))


def smoke_detector(name, x, y, z, room="", source=None):
    """Smoke detector on the ceiling."""
    with _part(room, source):
        cyl(name, (x, y), z - 1.6, z, 2.6, mat("plastic"))
        cyl(name + "_led", (x + 1.2, y), z - 1.65, z - 1.6, 0.3, mat("plastic", (200, 40, 30)))


def thermostat(name, x, y, facing, z=48.0, room="", source=None):
    """Wall thermostat, 4" x 4.5", with a small screen."""
    with _part(room, source), at(x, y, facing):
        box(name, -2.0, 2.0, 0, 0.9, z - 2.25, z + 2.25, mat("plastic"))
        box(name + "_screen", -1.1, 1.1, 0.9, 0.95, z - 0.2, z + 1.6, mat("screen", (70, 74, 72)))


def outlet(name, x, y, facing, z=14.0, room="", source=None):
    """Duplex receptacle with its white cover plate. z 14 is a wall outlet; about 44 over a counter or vanity."""
    m = mat("plastic")
    with _part(room, source), at(x, y, facing):
        box(name, -1.45, 1.45, 0, 0.25, z - 2.3, z + 2.3, m)
        for dz in (-0.75, 0.75):
            box(name + "_receptacle", -0.65, 0.65, 0.25, 0.37, z + dz - 0.55, z + dz + 0.55, m)


def switch(name, x, y, facing, z=48.0, gang=1, room="", source=None):
    """Rocker light switches under one white cover plate; gang: 1 to 3 switches side by side."""
    m, w = mat("plastic"), 2.9 + 1.75 * (gang - 1)
    with _part(room, source), at(x, y, facing):
        box(name, -w / 2, w / 2, 0, 0.25, z - 2.3, z + 2.3, m)
        for i in range(gang):
            u = -w / 2 + (i + 0.5) * w / gang
            box(name + "_rocker", u - 0.55, u + 0.55, 0.25, 0.37, z - 1.2, z + 1.2, m)


def panel(name, x, y, facing, z=21.0, width=14.5, height=30.0, rgb=(118, 120, 116), room="", source=None):
    """Electrical panel: a flush metal cover with a door and latch. z is its BOTTOM edge; rgb its paint."""
    W, m, zc = width / 2, mat("door_paint", rgb), z + height / 2
    with _part(room, source), at(x, y, facing):
        box(name + "_trim", -W, W, 0, 0.5, z, z + height, m)
        box(name + "_door", -W + 2.0, W - 2.0, 0.5, 0.7, z + 2.5, z + height - 2.5, m)
        box(name + "_latch", W - 3.6, W - 2.4, 0.7, 0.95, zc - 1.0, zc + 1.0, mat("black_metal"))
        _boxes(name + "_screws", [(u - 0.2, u + 0.2, 0.5, 0.62, zz - 0.2, zz + 0.2) for u in (-W + 0.8, W - 0.8)
                                  for zz in (z + 0.8, zc, z + height - 0.8)], mat("nickel"))


# ------------------------------------------------------------------ closets and utilities
def closet_shelf(name, x, y, facing, width, z=66.0, depth=12.0, kind="wire", rod=True, room="", source=None):
    """Closet shelf with a hanging rod under its front edge, spanning `width` between two side walls. (x, y) is the
    middle of the shelf on the back wall; z is the top of the shelf.
    kind  'wire' (white wire shelf on braces) | 'wood' (white board on cleats, metal rod)"""
    W = width / 2 - 0.25
    with _part(room, source), at(x, y, facing):
        if kind == "wire":
            m, t = mat("plastic"), 0.07
            n = int(2 * W)
            us = [-W + 0.3 + i * (2 * W - 0.6) / n for i in range(n + 1)]
            _boxes(name, [(u - t, u + t, 0.2, depth, z - 2 * t, z) for u in us]
                   + [(u - t, u + t, depth - t, depth + t, z - 1.6, z) for u in us]
                   + [(-W, W, v - 0.1, v + 0.1, z - 0.34, z - 0.14) for v in (0.3, depth / 2, depth)]
                   + [(-W, W, depth - 0.1, depth + 0.1, z - 1.7, z - 1.5)], m)
            k = max(1, round(width / 30.0))
            for i in range(k):
                u = -W + (i + 0.5) * 2 * W / k
                tube(name + "_brace", [(u, depth - 1.0, z - 0.4), (u, 0.3, z - depth + 0.6)], 0.2, m, seg=8)
            if rod:
                cyl(name + "_rod", (depth - 1.5, z - 2.6), -W, W, 0.5, m, axis="u", seg=12)
        else:
            m = mat("trim_paint")
            box(name, -W, W, 0, depth, z - 0.75, z, m)
            box(name + "_cleat", -W, W, 0, 0.75, z - 4.25, z - 0.75, m)
            for i in (-1, 1):
                box(name + "_cleat", *sorted((i * W, i * (W - 0.75))), 0.75, depth, z - 4.25, z - 0.75, m)
            if rod:
                cyl(name + "_rod", (depth - 1.5, z - 2.5), -W + 0.75, W - 0.75, 0.65, mat("nickel"), axis="u", seg=16)


def _front_loader(name, u0, z0, m, mc):
    """27" wide, 30" deep, 38" high front-loading washer or dryer standing 1" off the wall."""
    uc, z1 = u0 + 13.5, z0 + 38.4
    box(name, u0, u0 + 27.0, 1.0, 31.0, z0 + 0.4, z1, m)
    cyl(name + "_door", (uc, z0 + 17.5), 31.0, 32.0, 9.2, m, axis="v", seg=36)
    cyl(name + "_door_glass", (uc, z0 + 17.5), 32.0, 32.2, 6.8, mat("black_glass"), axis="v", seg=36)
    box(name + "_controls", u0 + 4.5, u0 + 22.5, 31.0, 31.2, z1 - 6.2, z1 - 2.6, mc)
    cyl(name + "_dial", (u0 + 19.5, z1 - 4.4), 31.2, 32.0, 1.2, m, axis="v")


def washer_dryer(name, x, y, facing, kind="stacked", finish="white", room="", source=None):
    """Washer and dryer standing against the wall; (x, y) is the point on the wall behind the middle of the set.
    kind    'stacked' (front loaders, dryer on top: 27" wide, 31" deep, 77" high) |
            'side_by_side' (front loaders: 54.5" wide, 38" high) |
            'center' (one-piece laundry centre, top-load washer under a dryer: 24" wide, 28" deep, 75" high)
    finish  'white' | 'stainless' | 'black'"""
    m, mc = (mat(k) for k in FINISH[finish])
    with _part(room, source), at(x, y, facing):
        if kind == "center":
            box(name + "_washer", -12, 12, 1.0, 28.0, 0.3, 37.0, m)
            box(name + "_washer_lid", -10.5, 10.5, 7.0, 26.5, 37.0, 37.6, m)
            for u in (-12, 11.1):
                box(name + "_stack_side", u, u + 0.9, 1.0, 28.0, 37.0, 48.0, m)
            box(name + "_stack_back", -12, 12, 1.0, 6.0, 37.0, 48.0, mc)
            box(name + "_dryer", -12, 12, 1.0, 28.0, 48.0, 75.0, m)
            box(name + "_dryer_controls", -11.7, 11.7, 28.0, 28.4, 48.3, 53.5, mc)
            cyl(name + "_dryer_dial", (6.0, 51.0), 28.4, 29.5, 1.2, m, axis="v")
            box(name + "_dryer_door", -10, 10, 28.0, 28.6, 56.0, 72.0, m)
            box(name + "_dryer_door_inset", -9, 9, 28.6, 28.65, 57.0, 71.0, mc)
            box(name + "_dryer_door_handle", 8.3, 9.3, 28.6, 29.2, 61.0, 67.0, m)
            cyl(name + "_dryer_vent", (0, 64.0), 0, 1.0, 2.0, mat("nickel"), axis="v")
            core.footprint(name, -12, 12, 0, 28.0, 75.0)
        elif kind == "side_by_side":
            _front_loader(name + "_washer", -27.25, 0, m, mc)
            _front_loader(name + "_dryer", 0.25, 0, m, mc)
            core.footprint(name, -27.25, 27.25, 0, 31.0, 38.4)
        else:
            _front_loader(name + "_washer", -13.5, 0, m, mc)
            _front_loader(name + "_dryer", -13.5, 38.4, m, mc)
            core.footprint(name, -13.5, 13.5, 0, 31.0, 76.8)


def water_heater(name, x, y, facing="S", diameter=20.0, height=58.0, room="", source=None):
    """Tank water heater standing on the floor, centred on plan (x, y); `facing` is the side its controls are on."""
    r, m, mn = diameter / 2, mat("appliance_white"), mat("nickel")
    with _part(room, source), at(x, y, facing):
        cyl(name, (0, 0), 0.5, height, r, m, seg=32)
        core.ellipsoid(name + "_top", (0, 0, height), (r, r, 1.5), m)
        for u in (-r / 2, r / 2):
            cyl(name + "_pipe", (u, 0), height, height + 6.0, 0.5, mn, seg=12)
        box(name + "_controls", -2.5, 2.5, r - 0.6, r + 1.2, 6.0, 12.0, mat("appliance_black"))
        tube(name + "_relief", [(r - 2.0, 0, height - 5.0), (r + 0.8, 0, height - 5.0), (r + 0.8, 0, 6.0)], 0.35, mn, seg=8)
        core.footprint(name, -r, r, -r, r, height + 6.0)
