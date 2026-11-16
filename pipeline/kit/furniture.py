"""Furniture and furnishings. Every piece is one call that stands it at plan point (x, y):

  wall pieces   (sofa, bed, desk, console, shelf, tv, wall_art, curtains ...): (x, y) is the middle of the piece's
                back edge, on the wall face, and `facing` is the compass letter it faces, out from that wall. Free in
                the room, `facing` may be degrees (0 = S, turning through E = 90). Floor pieces stand 0.75 in front
                of (x, y) to clear the baseboard.
  round pieces  (plant, floor_lamp, table_lamp) and pillow: (x, y) is the centre.
  table-top pieces take `z`, the height of the surface they stand on; pieces with a surface return dict(top=...).

Sizes are inches, colours sRGB 0-255. Left and right are as seen from the room, looking at the piece.
`spot` turns "8 inches out from the wall and 6 to the right of this piece" into a plan point."""
import math
import random
from contextlib import contextmanager

import bmesh
from mathutils import Matrix, Vector

from . import core, lights
from .core import at, box, cyl, mat, tag, tube

GAP = 0.75   # floor pieces stand this far off the wall, in front of the baseboard
BEDS = {"twin": (38, 75), "full": (54, 75), "queen": (60, 80), "king": (76, 80)}
BOOKS = ((120, 52, 44), (48, 66, 92), (196, 186, 164), (62, 84, 66), (34, 34, 36), (176, 130, 70))


def spot(x, y, facing, u=0.0, v=0.0):
    """Plan (x, y) of the point u to the right of and v out in front of a piece placed at (x, y, facing): for
    standing a lamp on a nightstand or a pillow on a sofa."""
    with at(x, y, facing):
        p = core.plan(u, v)
    return p.x, p.y


@contextmanager
def _piece(x, y, facing, room, source):
    with tag(group="D", coll="furniture", room=room, **({"source": source} if source else {})), at(x, y, facing):
        yield


def _sharp(ob):
    """Smooth shading that still breaks at real corners."""
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    return ob


def _soft(name, u0, u1, v0, v1, z0, z1, m, r=1.0, puff=0.0, full=1.0, lean=0.0, roll=0.0):
    """Box with edges rounded to radius r. puff: inches its two largest faces crown outwards (a cushion); full < 1
    keeps the crown full out to a pinched seam (a pillow). lean: degrees the top tips back, roll: to the right."""
    h = (abs(u1 - u0) / 2, abs(v1 - v0) / 2, abs(z1 - z0) / 2)
    r = min(r, 0.98 * min(h))
    k = h.index(min(h))
    tans = [math.tan(math.radians(a)) for a in ((0, 15, 30, 45) if r >= 0.8 else (0, 22.5, 45))]

    def lines(hh):
        e = [hh - r + r * t for t in tans]
        n = 5 if puff else 1
        return [-c for c in reversed(e)] + [(hh - r) * (2 * i / n - 1) for i in range(1, n)] + e
    G = [lines(hh) for hh in h]
    N = [len(g) - 1 for g in G]
    R = Matrix.Rotation(math.radians(lean), 3, "X") @ Matrix.Rotation(math.radians(roll), 3, "Y")
    mid = Vector(((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2))
    bm, vs = bmesh.new(), {}

    def vert(t):
        if t not in vs:
            p = Vector([G[i][t[i]] for i in range(3)])
            q = Vector([max(r - hh, min(hh - r, c)) for c, hh in zip(p, h)])
            if (p - q).length > 1e-9:
                p = q + r * (p - q).normalized()
            if puff:
                a, b = [p[i] / h[i] for i in range(3) if i != k]
                p[k] *= 1 + puff / h[k] * max(0.0, (1 - a * a) * (1 - b * b)) ** full
            vs[t] = bm.verts.new(R @ p + mid)
        return vs[t]
    for d in range(3):
        a, b = [i for i in range(3) if i != d]
        for s in (0, N[d]):
            for i in range(N[a]):
                for j in range(N[b]):
                    quad = []
                    for ia, ib in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        t = [0, 0, 0]
                        t[d], t[a], t[b] = s, ia, ib
                        quad.append(vert(tuple(t)))
                    bm.faces.new(quad)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = core.emit(name, bm, m, True)
    # area-weighted normals keep the flat faces flat; plain smooth shading would shade them as if they bulged
    me = ob.data
    n = [Vector() for _ in me.vertices]
    for p in me.polygons:
        for i in p.vertices:
            n[i] += p.normal * p.area
    me.normals_split_custom_set_from_vertices([c.normalized() for c in n])
    return ob


def _pillow(name, u, v, z, w, h, t, m, lean=0.0, roll=0.0):
    """Cushion w wide, h tall and t thick with a pinched seam; (u, v) is its centre and z its lowest point."""
    a = math.radians(abs(lean))
    zc = z + h / 2 * math.cos(a) + 0.2 * t * math.sin(a)
    return _soft(name, u - w / 2, u + w / 2, v - 0.13 * t, v + 0.13 * t, zc - h / 2, zc + h / 2, m, r=0.125 * t, puff=0.37 * t,
                 full=0.7, lean=lean, roll=roll)


def _lathe(name, c, prof, m, seg=24):
    """Shape turned about the vertical through local (u, v) = c; prof is (radius, z) pairs, radius 0 closing it."""
    bm = bmesh.new()
    rings = [[bm.verts.new((c[0] + r * math.cos(2 * math.pi * i / seg), c[1] + r * math.sin(2 * math.pi * i / seg), z))
              for i in range(seg if r > 1e-6 else 1)] for r, z in prof]
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            q = list(dict.fromkeys((a[i % len(a)], a[j % len(a)], b[j % len(b)], b[i % len(b)])))
            if len(q) > 2:
                bm.faces.new(q)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _sharp(core.emit(name, bm, m))


def _cube(bm, u0, u1, v0, v1, z0, z1, mi=0):
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.transform(bm, verts=vs, matrix=Matrix.Translation(((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2))
                        @ Matrix.Diagonal((u1 - u0, v1 - v0, z1 - z0, 1)))
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi


def _legs(name, pts, z0, z1, r, m):
    for u, v in pts:
        cyl(name, (u, v), z0, z1, r * 0.7, m, seg=12, r1=r)


def _fronts(name, u0, u1, v, z0, z1, rows, cols, m, hw, doors=False):
    """Grid of drawer fronts (or doors) on the face at v, each with its pull."""
    cw, rh = (u1 - u0) / cols, (z1 - z0) / rows
    for i in range(cols):
        for j in range(rows):
            a, b = u0 + i * cw, z0 + j * rh
            box(name + ("_door" if doors else "_drawer"), a + 0.12, a + cw - 0.12, v, v + 0.75, b + 0.12, b + rh - 0.12, m)
            if doors:   # pairs of doors meet, so their pulls sit side by side
                hu, hz = (a + cw - 2.0 if i % 2 == 0 else a + 2.0), b + rh - 6.0
                pull = (hu - 0.22, hu + 0.22, hz - 2.5, hz + 2.5)
                posts = [(hu, hz - 2.0), (hu, hz + 2.0)]
            else:
                hu, hz, pw = a + cw / 2, b + rh * 0.62, min(3.0, cw / 4)
                pull = (hu - pw, hu + pw, hz - 0.22, hz + 0.22)
                posts = [(hu - pw + 0.5, hz), (hu + pw - 0.5, hz)]
            box(name + "_pull", pull[0], pull[1], v + 1.45, v + 1.85, pull[2], pull[3], hw)
            for pu, pz in posts:
                box(name + "_pull_post", pu - 0.18, pu + 0.18, v + 0.75, v + 1.45, pz - 0.18, pz + 0.18, hw)


def _cabinet(name, width, depth, height, rows, cols, m, hw, doors=False, leg=4.0):
    W, v1 = width / 2, GAP + depth
    _legs(name + "_leg", [(s * (W - 1.6), v) for s in (-1, 1) for v in (GAP + 1.6, v1 - 2.4)], 0, leg, 0.9, hw)
    box(name + "_body", -W, W, GAP, v1 - 0.8, leg, height - 1, m)
    _soft(name + "_top", -W - 0.4, W + 0.4, GAP, v1 + 0.3, height - 1, height, m, r=0.2)
    _fronts(name, -W + 0.4, W - 0.4, v1 - 0.8, leg + 0.4, height - 1.3, rows, cols, m, hw, doors)
    core.footprint(name, -W, W, GAP, v1, height)
    return dict(name=name, top=height)


# ------------------------------------------------------------------ seating
def sofa(name, x, y, facing="S", width=84.0, depth=36.0, seat_h=18.0, back_h=32.0, arm=7.0, arm_h=25.0, cushions=None,
         chaise=None, chaise_depth=62.0, material="fabric", rgb=(98, 94, 90), room="", source=None):
    """Straight sofa with two arms, seat cushions and back cushions.
    width         overall, arms included; arm: width of each arm, arm_h: its height
    cushions      seats across (default: one per 27 inches or so)
    chaise        None | 'left' | 'right': that end seat runs out to chaise_depth from the wall, making an L
    material      'fabric' | 'leather'
    Returns dict(top=seat_h): throw pillows stand on that height."""
    m, inner = mat(material, rgb), width - 2 * arm
    n = cushions or max(1, round(inner / 27))
    cw, v0, v1, bt, zb = inner / n, GAP, GAP + depth, 6.0, seat_h - 5.5
    with _piece(x, y, facing, room, source):
        _soft(name + "_base", -inner / 2 - 1, inner / 2 + 1, v0 + 1, v1 - 0.5, 2, zb, m, r=0.8)
        _soft(name + "_back", -width / 2, width / 2, v0, v0 + bt, 2, back_h - 3, m, r=2.0)
        for s in (-1, 1):
            _soft(name + "_arm", *sorted((s * inner / 2, s * width / 2)), v0, v1, 2, arm_h, m, r=2.5)
        feet = [(s * (width / 2 - 2.5), v) for s in (-1, 1) for v in (v0 + 2.5, v1 - 2.5)]
        core.footprint(name, -width / 2, width / 2, v0, v1, back_h)
        for i in range(n):
            u0 = -inner / 2 + i * cw
            ve = v1 + 0.5
            if chaise and i == (0 if chaise == "left" else n - 1):
                ve = GAP + chaise_depth
                _soft(name + "_chaise", u0, u0 + cw, v1 - 2, ve - 0.5, 2, zb, m, r=0.8)
                feet += [(u0 + 2.5, ve - 3), (u0 + cw - 2.5, ve - 3)]
                core.footprint(name + "_chaise", u0, u0 + cw, v1, ve, seat_h)
            _soft(name + "_seat", u0 + 0.15, u0 + cw - 0.15, v0 + bt - 0.5, ve, zb, seat_h, m, r=1.8, puff=0.6)
            _soft(name + "_cushion", u0 + 0.2, u0 + cw - 0.2, v0 + bt - 0.5, v0 + bt + 5.5, seat_h - 0.5, back_h, m, r=2.4,
                  puff=1.0, lean=10)
        _legs(name + "_foot", feet, 0, 2, 1.1, mat("black_metal"))
    return dict(name=name, top=seat_h)


def armchair(name, x, y, facing="S", width=34.0, depth=34.0, seat_h=18.0, back_h=32.0, arm=6.0, arm_h=25.0,
             material="fabric", rgb=(98, 94, 90), room="", source=None):
    """Upholstered armchair: a one-seat sofa."""
    return sofa(name, x, y, facing, width, depth, seat_h, back_h, arm, arm_h, 1, None, 0, material, rgb, room, source)


def chair(name, x, y, facing="S", kind="dining", seat_h=None, width=None, back=True, material="fabric", rgb=(62, 60, 58),
          frame=None, frame_rgb=None, room="", source=None):
    """kind 'dining' (four legs, padded seat and back) | 'task' (office chair on a five-star base with arms) |
    'stool' (round padded seat on four splayed legs; a bar stool at the default height).
    seat_h   seat height: default 18 dining, 19 task, 30 stool (24 suits a counter, 18 a low stool)
    width    of the seat: default 18, 20, 16
    back     False leaves the back (and a task chair's arms) off
    frame    'wood' | 'black_metal' | 'chrome' ...: default wood for dining, black_metal otherwise
    The chair faces `facing`, so one tucked under a table faces the table; (x, y) is behind its back."""
    seat_h = seat_h or {"dining": 18.0, "task": 19.0, "stool": 30.0}[kind]
    W = (width or {"dining": 18.0, "task": 20.0, "stool": 16.0}[kind]) / 2
    m, mf = mat(material, rgb), mat(frame or ("wood" if kind == "dining" else "black_metal"), frame_rgb)
    with _piece(x, y, facing, room, source):
        if kind == "dining":
            v0 = GAP + 2.0
            v1 = v0 + 2 * W + 1
            _legs(name + "_leg", [(s * (W - 1), v1 - 1.2) for s in (-1, 1)], 0, seat_h - 2.5, 0.8, mf)
            for s in (-1, 1):
                top = [(s * (W - 1), v0 - 1.5, seat_h + 17)] if back else []
                tube(name + "_leg", [(s * (W - 1), v0 + 1, 0), (s * (W - 1), v0 + 1, seat_h - 1)] + top, 0.7, mf)
            box(name + "_apron", -W + 0.6, W - 0.6, v0 + 0.5, v1 - 0.6, seat_h - 3.6, seat_h - 2.2, mf)
            _soft(name + "_seat", -W, W, v0, v1, seat_h - 2.5, seat_h, m, r=1.0, puff=0.4)
            if back:
                _soft(name + "_back", -W + 0.4, W - 0.4, v0 - 1.4, v0 + 0.4, seat_h + 5.5, seat_h + 17.5, m, r=0.8, puff=0.3, lean=8)
            core.footprint(name, -W, W, GAP, v1, seat_h)
        elif kind == "stool":
            c, t = GAP + W + 1.5, W - 1.0
            b = t + 1.5
            for s in (-1, 1):
                for d in (-1, 1):
                    tube(name + "_leg", [(s * b, c + d * b, 0.2), (s * t, c + d * t, seat_h - 3)], 0.45, mf)
            if seat_h > 22:
                zr = seat_h - 19.0
                hs = b - (b - t) * zr / (seat_h - 3)
                tube(name + "_ring", [(-hs, c - hs, zr), (hs, c - hs, zr), (hs, c + hs, zr), (-hs, c + hs, zr), (-hs, c - hs, zr)], 0.4, mf)
            _lathe(name + "_pan", (0, c), [(0, seat_h - 3.6), (W - 0.3, seat_h - 3.6), (W - 0.3, seat_h - 2.8), (0, seat_h - 2.8)], mf)
            _lathe(name + "_seat", (0, c), [(0, seat_h - 2.8), (W - 0.6, seat_h - 2.8), (W, seat_h - 1.8), (W - 0.2, seat_h - 0.7),
                                           (W - 1.6, seat_h - 0.1), (0, seat_h)], m, seg=32)
            if back:
                for s in (-1, 1):
                    tube(name + "_upright", [(s * t, c - t, seat_h - 3), (s * t, c - t - 1.2, seat_h + 13.5)], 0.45, mf)
                for z in (seat_h + 5.0, seat_h + 10.5):
                    box(name + "_slat", -t - 0.3, t + 0.3, c - t - 1.4, c - t - 0.8, z - 1.6, z + 1.6, mf)
            core.footprint(name, -b, b, c - b, c + b, seat_h)
        else:
            c, mp = GAP + 12.0, mat("plastic", (22, 22, 23))
            for i in range(5):
                a = math.radians(72 * i + 18)
                tube(name + "_star", [(0, c, 3.8), (11 * math.cos(a), c + 11 * math.sin(a), 2.7)], 0.7, mp)
                cyl(name + "_caster", (11 * math.cos(a), c + 11 * math.sin(a)), 0, 2.3, 1.1, mp, seg=12)
            cyl(name + "_hub", (0, c), 2.6, 5.0, 1.6, mp, seg=12)
            cyl(name + "_column", (0, c), 5.0, seat_h - 4.5, 1.0, mf, seg=12)
            cyl(name + "_mech", (0, c), seat_h - 4.5, seat_h - 3.0, 3.0, mp, seg=12)
            _soft(name + "_seat", -W, W, c - W + 1, c + W + 1, seat_h - 3.2, seat_h, m, r=1.2, puff=0.5)
            if back:
                _soft(name + "_back", -W + 1, W - 1, c - W - 0.6, c - W + 1.0, seat_h + 4, seat_h + 23, m, r=0.8, puff=0.5, lean=10)
                tube(name + "_spine", [(0, c - 2, seat_h - 3.5), (0, c - W - 0.4, seat_h - 2), (0, c - W - 1.2, seat_h + 12)], 0.7, mp)
                for s in (-1, 1):
                    tube(name + "_arm_post", [(s * (W - 0.6), c, seat_h - 2.5), (s * (W + 0.6), c + 0.4, seat_h + 7.2)], 0.55, mp)
                    _soft(name + "_arm", s * (W + 0.6) - 1.3, s * (W + 0.6) + 1.3, c - 4, c + 6, seat_h + 7.0, seat_h + 8.2, mp, r=0.5)
            core.footprint(name, -11, 11, c - 11, c + 11, seat_h)
    return dict(name=name, top=seat_h)


def ottoman(name, x, y, facing="S", width=24.0, depth=24.0, height=17.0, shape="rect", material="fabric", rgb=(74, 70, 68),
            room="", source=None):
    """Upholstered footstool or pouf. shape 'rect' | 'round' (width is then the diameter)."""
    m, W = mat(material, rgb), width / 2
    if shape == "round":
        depth = width
    with _piece(x, y, facing, room, source):
        if shape == "round":
            _lathe(name, (0, GAP + W), [(0, 1.5), (W - 1.2, 1.5), (W, 3.0), (W, height - 2.6), (W - 0.5, height - 1.0),
                                       (W - 2.0, height - 0.2), (0, height)], m, seg=32)
            feet = [(0.6 * W * s, GAP + W + 0.6 * W * d) for s in (-1, 1) for d in (-1, 1)]
        else:
            _soft(name, -W, W, GAP, GAP + depth, 1.5, height - 0.4, m, r=1.5, puff=0.4)
            feet = [(s * (W - 2.2), v) for s in (-1, 1) for v in (GAP + 2.2, GAP + depth - 2.2)]
        _legs(name + "_foot", feet, 0, 1.5, 0.9, mat("black_metal"))
        core.footprint(name, -W, W, GAP, GAP + depth, height)
    return dict(name=name, top=height)


# ------------------------------------------------------------------ tables and storage
def table(name, x, y, facing="S", width=48.0, depth=30.0, height=30.0, shape="rect", base="legs", top="wood", rgb=None,
          frame="wood", frame_rgb=None, shelf=False, room="", source=None):
    """Dining table (height 30), coffee table (16-18) or side table (20-24), by its sizes.
    shape   'rect' | 'round' (width is the diameter)
    base    'legs' | 'pedestal'
    top     vocabulary key of the top: 'wood', 'counter' (stone), 'black_glass', 'glass', 'black_metal'; rgb colours it
    frame   key of the legs or pedestal: 'wood', 'black_metal', 'chrome', 'brass'; frame_rgb colours it
    shelf   a lower shelf between the legs
    (x, y) is the middle of the back edge: to centre a table in a room, give the point depth/2 behind its centre."""
    mt, mf, W = mat(top, rgb), mat(frame, frame_rgb), width / 2
    if shape == "round":
        depth = width
    T, c, v1 = (1.25 if height > 24 else 0.9), GAP + depth / 2, GAP + depth
    lr = (1.1 if frame == "wood" else 0.6) * (1.0 if height > 24 else 0.75)
    with _piece(x, y, facing, room, source):
        if shape == "round":
            _lathe(name + "_top", (0, c), [(0, height - T), (W - 0.3, height - T), (W, height - T + 0.3), (W, height - 0.2),
                                          (W - 0.2, height), (0, height)], mt, seg=48)
            pts = [(0.68 * W * s, c + 0.68 * W * d) for s in (-1, 1) for d in (-1, 1)]
        else:
            _soft(name + "_top", -W, W, GAP, v1, height - T, height, mt, r=0.25)
            i = lr + (1.5 if frame == "wood" else 0.2)
            pts = [(s * (W - i), v) for s in (-1, 1) for v in (GAP + i, v1 - i)]
        if base == "pedestal":
            R = min(width, depth) * 0.3
            _lathe(name + "_base", (0, c), [(0, 0), (R, 0), (R, 0.8), (2.4, 2.4), (1.7, height - T - 4), (R * 0.55, height - T),
                                           (0, height - T)], mf)
        else:
            _legs(name + "_leg", pts, 0, height - T, lr, mf)
            (u0, a0), (u1, a1) = pts[0], pts[3]
            if shape != "round":
                for s in (u0, u1):
                    box(name + "_apron", s - 0.4, s + 0.4, a0, a1, height - T - 2.5, height - T, mf)
                for v in (a0, a1):
                    box(name + "_apron", u0, u1, v - 0.4, v + 0.4, height - T - 2.5, height - T, mf)
            if shelf:
                box(name + "_shelf", u0, u1, a0, a1, height * 0.2, height * 0.2 + 0.6, mf if top in ("glass", "black_glass") else mt)
        if min(width, depth) >= 12:
            core.footprint(name, -W, W, GAP, v1, height)
    return dict(name=name, top=height)


def desk(name, x, y, facing="S", width=48.0, depth=24.0, height=29.5, drawers=None, rgb=(74, 62, 54), frame="black_metal",
         frame_rgb=None, hardware="black_metal", room="", source=None):
    """Writing desk: a wood top (rgb) on four legs with a modesty rail at the back.
    drawers   None | 'left' | 'right': a three-drawer pedestal under that end
    The chair goes in front of it, facing the opposite way."""
    m, mf, W, v1 = mat("wood", rgb), mat(frame, frame_rgb), width / 2, GAP + depth
    with _piece(x, y, facing, room, source):
        _soft(name + "_top", -W, W, GAP, v1, height - 1.2, height, m, r=0.2)
        ds = {"left": -1, "right": 1}.get(drawers, 0)
        _legs(name + "_leg", [(s * (W - 2), v) for s in (-1, 1) if s != ds for v in (GAP + 2, v1 - 2)], 0, height - 1.2, 0.9, mf)
        box(name + "_rail", -W + 2, W - 2, GAP + 1.6, GAP + 2.4, height - 6, height - 1.2, mf)
        if ds:
            a, b = sorted((ds * (W - 1), ds * (W - 16)))
            box(name + "_pedestal", a, b, GAP + 1, v1 - 1.8, 1.0, height - 1.2, m)
            _fronts(name, a, b, v1 - 1.8, 1.0, height - 1.4, 3, 1, m, mat(hardware))
        core.footprint(name, -W, W, GAP, v1, height)
    return dict(name=name, top=height)


def console(name, x, y, facing="S", width=60.0, depth=18.0, height=24.0, doors=None, rgb=None, hardware="black_metal",
            room="", source=None):
    """Low cabinet with doors on short legs: a TV stand, sideboard or credenza. doors: how many (default one per
    18 inches or so). Wood, in `rgb`. A tv() given the same (x, y, facing) and z=height stands on it."""
    with _piece(x, y, facing, room, source):
        return _cabinet(name, width, depth, height, 1, doors or max(2, round(width / 18)), mat("wood", rgb), mat(hardware), doors=True)


def nightstand(name, x, y, facing="S", width=20.0, depth=16.0, height=24.0, drawers=2, rgb=None, hardware="black_metal",
               room="", source=None):
    """Bedside table with drawers. Stands beside the bed, against the same wall, facing the same way."""
    with _piece(x, y, facing, room, source):
        return _cabinet(name, width, depth, height, drawers, 1, mat("wood", rgb), mat(hardware))


def dresser(name, x, y, facing="S", width=56.0, depth=18.0, height=32.0, drawers=3, columns=2, rgb=None,
            hardware="black_metal", room="", source=None):
    """Chest of drawers: `drawers` rows in `columns` columns (a tall narrow chest is e.g. width 30, height 48,
    drawers 5, columns 1)."""
    with _piece(x, y, facing, room, source):
        return _cabinet(name, width, depth, height, drawers, columns, mat("wood", rgb), mat(hardware))


def shelf(name, x, y, facing="S", width=32.0, depth=12.0, height=72.0, shelves=5, books=True, rgb=None, room="", source=None):
    """Open bookcase with `shelves` levels (the bottom one included) under its top. books: fill most of them."""
    m, W, v1, T, rs = mat("wood", rgb), width / 2, GAP + depth, 0.75, random.Random(name)
    step = (height - 3.0 - T) / shelves
    with _piece(x, y, facing, room, source):
        for s in (-1, 1):
            box(name + "_side", *sorted((s * W, s * (W - T))), GAP, v1, 0, height, m)
        box(name + "_back", -W + T, W - T, GAP, GAP + 0.3, 0, height, m)
        box(name + "_top", -W + T, W - T, GAP + 0.3, v1, height - T, height, m)
        box(name + "_kick", -W + T, W - T, v1 - 1.5, v1 - 0.9, 0, 3.0 - T, m)
        bm = bmesh.new()
        for i in range(shelves):
            z = 3.0 + i * step
            box(name + "_board", -W + T, W - T, GAP + 0.3, v1 - 0.2, z - T, z, m)
            if not books or rs.random() < 0.15:
                continue
            u, end = -W + T + 0.3, W - T - rs.uniform(1, 0.45 * width)
            while u < end:
                w = rs.uniform(0.8, 1.9)
                _cube(bm, u, u + w, v1 - 1.2 - rs.uniform(5.5, 8.0), v1 - 1.2 - rs.uniform(0, 0.8), z, z + (step - T) * rs.uniform(0.6, 0.9),
                      rs.randrange(len(BOOKS)))
                u += w + 0.05
        if bm.verts:
            core.emit(name + "_books", bm, [mat("plastic", c) for c in BOOKS])
        core.footprint(name, -W, W, GAP, v1, height)
    return dict(name=name, top=height)


# ------------------------------------------------------------------ bedroom
def bed(name, x, y, facing="S", size="queen", width=None, length=None, height=24.0, headboard=46.0, pillows=None,
        frame="wood", frame_rgb=None, headboard_rgb=None, duvet_rgb=(238, 238, 234), sheet_rgb=(246, 246, 243), room="", source=None):
    """Made bed: frame on legs, headboard, mattress, duvet folded back at the top, sleeping pillows.
    (x, y) is the middle of the HEAD end, on the wall; `facing` is the way the foot points.
    size           'twin' 38x75 | 'full' 54x75 | 'queen' 60x80 | 'king' 76x80, or give width and length of the mattress
    height         top of the mattress
    headboard      height of its top (0: none); headboard_rgb upholsters it in fabric instead of the frame material
    pillows        how many (default 1 on a twin, else 2)
    frame          'wood' | 'black_metal' | 'fabric' ...; frame_rgb colours it
    The duvet hangs 1 inch past the mattress at the sides and foot, and the bed is headboard + length + 1 long."""
    w, L = BEDS[size] if width is None or length is None else (width, length)
    mf, md, ms = mat(frame, frame_rgb), mat("fabric", duvet_rgb), mat("fabric", sheet_rgb)
    W, zf, hb = w / 2, height - 10.0, 2.5 if headboard else 0.0
    v0 = GAP + hb
    v1 = v0 + L
    n = pillows or (1 if w < 50 else 2)
    with _piece(x, y, facing, room, source):
        if headboard:
            if headboard_rgb:
                _soft(name + "_headboard", -W - 2, W + 2, GAP, v0 + 0.4, 4, headboard, mat("fabric", headboard_rgb), r=1.2, puff=0.5)
            else:
                _soft(name + "_headboard", -W - 1.5, W + 1.5, GAP, v0, 0, headboard, mf, r=0.3)
        for s in (-1, 1):
            box(name + "_rail", *sorted((s * (W + 0.5), s * (W - 1.0))), v0, v1 + 0.5, zf - 5, zf, mf)
        box(name + "_rail", -W + 1, W - 1, v1 - 1.0, v1 + 0.5, zf - 5, zf, mf)
        box(name + "_slats", -W + 1, W - 1, v0, v1 - 1, zf - 1.5, zf - 0.5, mf)
        for u, v in [(s * (W - 0.6), v) for s in (-1, 1) for v in (v0 + 1.5, v1 - 1.0)] + [(0, v1 - 1.0)]:
            box(name + "_leg", u - 0.9, u + 0.9, v - 0.9, v + 0.9, 0, zf - 5, mf)
        _soft(name + "_mattress", -W, W, v0, v1, zf, height, ms, r=2.0)
        vf = v0 + 0.3 * L
        _soft(name + "_duvet", -W - 1, W + 1, vf, v1 + 1, height - 8.5, height + 1.2, md, r=1.6, puff=0.5)
        _soft(name + "_duvet_fold", -W - 1.1, W + 1.1, vf - 1.5, vf + 9, height - 8, height + 2.3, md, r=1.3, puff=0.3)
        pw = min(27.0, w / n - 2.0)
        for i in range(n):
            u = (i - (n - 1) / 2) * (w / n)
            _pillow(name + "_pillow", u, v0 + 9.8, height + 0.2, pw, 17.0, 7.0, ms, lean=58)
        core.footprint(name, -W - 1, W + 1, GAP, v1 + 1, height)
    return dict(name=name, top=height + 1.5)


# ------------------------------------------------------------------ furnishings
def tv(name, x, y, facing="S", diagonal=50.0, mount="feet", z=0.0, room="", source=None):
    """Flat television, `diagonal` inches corner to corner. (x, y) is the wall point behind it.
    mount   'feet': stands on its feet on a surface at height z, 5 inches out from the wall (give it the console's
            x, y, facing and z = the console's top) | 'wall': hung flat on the wall with its bottom edge at z"""
    w, h, mp = diagonal * 0.872 + 0.6, diagonal * 0.49 + 0.8, mat("plastic", (24, 24, 26))
    vc, zb = (5.0, z + 2.6) if mount == "feet" else (1.7, z)
    with _piece(x, y, facing, room, source):
        _soft(name + "_body", -w / 2, w / 2, vc - 0.7, vc + 0.7, zb, zb + h, mp, r=0.25)
        box(name + "_screen", -w / 2 + 0.3, w / 2 - 0.3, vc + 0.7, vc + 0.76, zb + 0.6, zb + h - 0.3, mat("screen"))
        if mount == "feet":
            for s in (-1, 1):
                for d in (-1, 1):
                    tube(name + "_foot", [(s * (w / 2 - 6), vc, zb + 0.5), (s * (w / 2 - 4.5), vc + d * 4.3, z + 0.3)], 0.3, mp)
        else:
            box(name + "_mount", -6, 6, 0, vc - 0.7, zb + h / 2 - 5, zb + h / 2 + 5, mat("black_metal"))
    return dict(name=name, top=zb + h)


def rug(name, x, y, facing="S", width=96.0, depth=60.0, shape="rect", rgb=(170, 165, 155), border_rgb=None, room="", source=None):
    """Area rug lying on the floor; (x, y) is the middle of its back edge (no wall gap), so the rug covers `depth`
    out from there. shape 'rect' | 'round' (width is the diameter). border_rgb: a 4 inch border in another colour."""
    m, W, z = mat("rug", border_rgb or rgb), width / 2, 0.07   # just above a room's own floor finish
    with _piece(x, y, facing, room, source):
        if shape == "round":
            _lathe(name, (0, W), [(0, z), (W, z), (W, z + 0.4), (0, z + 0.4)], m, seg=48)
            if border_rgb:
                _lathe(name + "_field", (0, W), [(W - 4, z + 0.4), (W - 4, z + 0.46), (0, z + 0.46)], mat("rug", rgb), seg=48)
        else:
            box(name, -W, W, 0, depth, z, z + 0.4, m)
            if border_rgb:
                box(name + "_field", -W + 4, W - 4, 4, depth - 4, z + 0.4, z + 0.46, mat("rug", rgb))


def curtains(name, x, y, facing="S", width=48.0, head=84.0, length=None, closed=0.25, rgb=(226, 221, 211), rod="black_metal",
             room="", source=None):
    """Curtain rod and two gathered panels over a window. (x, y) is the wall face at the middle of the window and
    `facing` the side of the wall the room is on.
    width    of the window; the rod runs 8 inches past each side
    head     height of the top of the window above the floor (sill + height, plus width / 2 for an arched top);
             the rod hangs 4 inches above it
    length   of the panels (default: down to the floor)
    closed   part of the window each panel covers: 0 clear of the glass, 0.5 drawn shut"""
    m, mr, zr, half = mat("fabric", rgb), mat(rod), head + 4.0, width / 2 + 8.0
    z0 = 0.5 if length is None else zr - length
    with _piece(x, y, facing, room, source):
        cyl(name + "_rod", (3.0, zr), -half - 1.5, half + 1.5, 0.45, mr, axis="u", seg=12)
        for s in (-1, 1):
            core.ellipsoid(name + "_finial", (s * (half + 2.2), 3.0, zr), (1.0, 0.9, 0.9), mr, seg=12)
            box(name + "_bracket", s * (half - 1) - 0.3, s * (half - 1) + 0.3, 0, 3.0, zr - 0.35, zr + 0.35, mr)
            a, b = sorted((s * half, s * width / 2 * (1 - 2 * closed)))
            n = int((b - a) / 0.4) + 1
            front = [(a + (b - a) * i / n, 3.0 + 0.9 * math.sin(2 * math.pi * (b - a) * i / n / 3.4)) for i in range(n + 1)]
            _sharp(core.prism(name + "_panel", front + [(u, v - 0.35) for u, v in reversed(front)], z0, zr - 0.7, m))


def plant(name, x, y, height=48.0, z=0.0, rgb=None, pot_rgb=(232, 230, 224), room="", source=None):
    """Potted plant centred on (x, y), `height` tall overall, standing on a surface at height z (0: the floor).
    Under 24 inches it is a bushy table-top plant; taller, a small tree on a trunk. rgb: leaf colour."""
    R, rs, tree = max(1.8, min(8.0, height * 0.11)), random.Random(name), height >= 24
    ph = R * (1.9 if tree else 1.6)
    green = tuple(rgb or core.VOCAB["plant"]["rgb"])
    mats = [mat("plant", green), mat("plant", tuple(int(c * 0.68) for c in green))]
    with _piece(x, y, "S", room, source):
        _lathe(name + "_pot", (0, 0), [(0, z), (R * 0.72, z), (R, z + ph), (R * 0.86, z + ph), (R * 0.82, z + ph - 0.7),
                                      (0, z + ph - 0.7)], mat("porcelain", pot_rgb))
        if tree:
            zc, rv, rh, n, leaf = z + ph + (height - ph) * 0.62, (height - ph) * 0.38, height * 0.2, 46, height * 0.13
            tube(name + "_trunk", [(0, 0, z + ph - 1), (R * 0.2, 0, z + ph + (height - ph) * 0.3), (0, R * 0.15, zc)], 0.5,
                 mat("wood", (92, 72, 52)), seg=8)
        else:
            zc, rv, rh, n, leaf = z + ph + (height - ph) * 0.45, (height - ph) * 0.42, max(R * 1.15, height * 0.22), 26, height * 0.26
        bm = bmesh.new()
        for i in range(n):
            d = Vector((rs.gauss(0, 1), rs.gauss(0, 1), rs.gauss(0, 1))).normalized()
            L, f = leaf * rs.uniform(0.7, 1.3), rs.uniform(0.4, 0.95)
            vs = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=4, radius=1.0)["verts"]
            M = (Matrix.Translation((d.x * rh * f, d.y * rh * f, zc + d.z * rv * f))
                 @ (d + Vector((0, 0, 0.3))).to_track_quat("X", "Z").to_matrix().to_4x4()
                 @ Matrix.Rotation(rs.uniform(-0.8, 0.8), 4, "X") @ Matrix.Diagonal((L / 2, L * 0.28, L * 0.05, 1)))
            bmesh.ops.transform(bm, matrix=M, verts=vs)
            for fc in {fc for v in vs for fc in v.link_faces}:
                fc.material_index = int(i % 3 == 0)
        core.emit(name + "_leaves", bm, mats, True)
        if tree and z == 0:
            core.footprint(name, -R, R, -R, R, height)


def _shade(name, R, z0, z1):
    ob = _lathe(name + "_shade", (0, 0), [(R, z0), (R * 0.8, z1), (R * 0.8 - 0.15, z1), (R - 0.15, z0), (R, z0)], mat("emit_shade"))
    ob.visible_shadow = False   # or the shade would box in its own bulb


def floor_lamp(name, x, y, height=62.0, shade=15.0, watts=9.0, frame="black_metal", room="", source=None):
    """Standing lamp centred on (x, y): base, pole, glowing drum shade `shade` across, and its light."""
    mf = mat(frame)
    with _piece(x, y, "S", room, source):
        _lathe(name + "_base", (0, 0), [(0, 0), (5.5, 0), (5.5, 0.6), (1.0, 1.3), (0, 1.3)], mf)
        cyl(name + "_pole", (0, 0), 1.0, height - shade * 0.35, 0.45, mf, seg=12)
        _shade(name, shade / 2, height - shade * 0.7, height)
        lights.bulb(name + "_bulb", 0, 0, height - shade * 0.35, watts)
        core.footprint(name, -6, 6, -6, 6, height)


def table_lamp(name, x, y, z=24.0, height=22.0, shade=11.0, watts=6.0, rgb=(226, 222, 212), room="", source=None):
    """Lamp centred on (x, y) standing on a surface at height z: ceramic base (rgb), glowing shade, and its light."""
    hb, R = height * 0.5, shade * 0.24
    with _piece(x, y, "S", room, source):
        _lathe(name + "_base", (0, 0), [(0, z), (R * 0.8, z), (R * 0.85, z + 0.5), (R, z + hb * 0.45), (R * 0.75, z + hb * 0.8),
                                       (0.5, z + hb), (0, z + hb)], mat("porcelain", rgb))
        cyl(name + "_stem", (0, 0), z + hb, z + height * 0.78, 0.25, mat("brass"), seg=8)
        _shade(name, shade / 2, z + height * 0.56, z + height)
        lights.bulb(name + "_bulb", 0, 0, z + height * 0.78, watts)


def wall_art(name, x, y, facing="S", width=24.0, height=30.0, z=58.0, rgb=(70, 90, 110), accent_rgb=None, border=2.5,
             frame="black_metal", frame_rgb=None, room="", source=None):
    """Framed picture hung on the wall at (x, y), its CENTRE at height z. The picture is plain colour `rgb` inside a
    white mat `border` wide (0: none); accent_rgb adds a horizon band and a disc in a second colour."""
    mf, W, z0, z1, F = mat(frame, frame_rgb), width / 2, z - height / 2, z + height / 2, 0.8
    with _piece(x, y, facing, room, source):
        for s in (-1, 1):
            box(name + "_frame", *sorted((s * W, s * (W - F))), 0, 1.0, z0, z1, mf)
            box(name + "_frame", -W + F, W - F, 0, 1.0, *sorted((z + s * height / 2, z + s * (height / 2 - F))), mf)
        box(name + "_mat", -W + F, W - F, 0, 0.5, z0 + F, z1 - F, mat("wall_paint", (244, 243, 238)))
        i = F + border
        box(name + "_picture", -W + i, W - i, 0.5, 0.56, z0 + i, z1 - i, mat("wall_paint", rgb))
        if accent_rgb:
            ma = mat("wall_paint", accent_rgb)
            box(name + "_accent", -W + i, W - i, 0.56, 0.6, z0 + i, z0 + i + (height - 2 * i) * 0.38, ma)
            cyl(name + "_accent", (W * 0.25, z + height * 0.14), 0.56, 0.6, min(W, height / 2) * 0.22, ma, axis="v", seg=32)


def wall_mirror(name, x, y, facing="S", width=24.0, height=36.0, z=58.0, shape="rect", frame="black_metal", frame_rgb=None,
                room="", source=None):
    """Framed mirror hung on the wall at (x, y), its CENTRE at height z. shape 'rect' | 'round' (width is the
    diameter). A full-length mirror is e.g. width 20, height 64, z 38."""
    mf, mm, W, F = mat(frame, frame_rgb), mat("mirror"), width / 2, 0.8
    with _piece(x, y, facing, room, source):
        if shape == "round":
            cyl(name + "_frame", (0, z), 0, 0.8, W, mf, axis="v", seg=48)
            cyl(name + "_glass", (0, z), 0.8, 0.86, W - F, mm, axis="v", seg=48, smooth=False)
        else:
            box(name + "_frame", -W, W, 0, 0.8, z - height / 2, z + height / 2, mf)
            box(name + "_glass", -W + F, W - F, 0.8, 0.86, z - height / 2 + F, z + height / 2 - F, mm)


def pillow(name, x, y, z, facing="S", size=18.0, lean=20.0, roll=0.0, rgb=(215, 208, 196), material="fabric", room="", source=None):
    """Square throw pillow centred on (x, y), its lowest edge resting at height z (a sofa's seat, a bed's top).
    It faces `facing` (use the sofa's) and leans back `lean` degrees against whatever is behind it, so put it
    about size / 4 in front of the back cushion; roll tips it sideways. Colour only: no patterns."""
    with _piece(x, y, facing, room, source):
        _pillow(name, 0, 0, z, size, size, size * 0.34, mat(material, rgb), lean, roll)


def throw(name, x, y, z, facing="S", width=24.0, on=18.0, drop=12.0, rgb=(62, 62, 64), room="", source=None):
    """Blanket draped over an edge. (x, y) is the middle of that edge, z the height of the surface (a bed's or
    ottoman's top, a sofa's arm) and `facing` the way the edge faces. It lies `on` inches back onto the surface
    and hangs `drop` inches down the front."""
    m = mat("fabric", rgb)
    with _piece(x, y, facing, room, source):
        _soft(name + "_top", -width / 2, width / 2, -on, 0.75, z - 0.1, z + 0.6, m, r=0.3)
        _soft(name + "_drop", -width / 2, width / 2, 0.1, 0.75, z - drop, z + 0.45, m, r=0.3)
