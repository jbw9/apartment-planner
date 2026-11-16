"""Builds the apartment from spec.py inside Blender, bakes lighting, exports GLB + plan.json.

  blender -b --python build.py -- [preview] [bake] [export] [--res 4096] [--samples 256]
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec as S

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default):
    return type(default)(ARGS[ARGS.index(name) + 1]) if name in ARGS else default

WORK = arg("--work", "/Volumes/Movies/apartment-3d-work/build")
OUT = os.path.join(HERE, "..", "public", "model")
RES = arg("--res", 4096)
SAMPLES = arg("--samples", 256)
IN = 0.0254
CEIL = S.CEIL
U0, V0 = S.U0, S.V0


def T(u, v, z):
    return (u * IN, -v * IN, z * IN)


# ---------------------------------------------------------------- materials
# name: (rgb, roughness, metallic, extra)
MATS = {
    "wall_white":    ((0.80, 0.79, 0.76), 0.9, 0, {}),
    "wall_accent":   ((0.60, 0.59, 0.55), 0.9, 0, {}),
    "ceiling_white": ((0.82, 0.82, 0.80), 0.95, 0, {}),
    "floor_lvp":     ((0.50, 0.40, 0.29), 0.45, 0, {}),
    "trim_white":    ((0.84, 0.84, 0.82), 0.5, 0, {}),
    "door_white":    ((0.84, 0.84, 0.82), 0.45, 0, {}),
    "exterior":      ((0.35, 0.36, 0.37), 0.9, 0, {}),
    "cap":           ((0.10, 0.10, 0.11), 1.0, 0, {}),
    "cab_dark":      ((0.14, 0.14, 0.15), 0.5, 0, {}),
    "cab_wood":      ((0.62, 0.55, 0.45), 0.55, 0, {}),
    "quartz":        ((0.86, 0.86, 0.84), 0.25, 0, {}),
    "tile_marble":   ((0.82, 0.82, 0.82), 0.2, 0, {}),
    "stainless":     ((0.55, 0.56, 0.57), 0.32, 1, {}),
    "chrome":        ((0.75, 0.76, 0.78), 0.08, 1, {}),
    "nickel":        ((0.62, 0.61, 0.59), 0.35, 1, {}),
    "black_glass":   ((0.015, 0.015, 0.017), 0.06, 0, {}),
    "appliance_dark": ((0.08, 0.08, 0.085), 0.4, 0, {}),
    "appliance_white": ((0.86, 0.86, 0.86), 0.3, 0, {}),
    "tub_white":     ((0.88, 0.88, 0.88), 0.12, 0, {}),
    "porcelain":     ((0.90, 0.90, 0.89), 0.08, 0, {}),
    "mirror":        ((0.9, 0.9, 0.9), 0.02, 1, {}),
    "wire_white":    ((0.88, 0.88, 0.87), 0.5, 0, {}),
    "deck":          ((0.62, 0.62, 0.61), 0.8, 0, {}),
    "rail_black":    ((0.03, 0.03, 0.035), 0.5, 0, {}),
    "heater_grille": ((0.25, 0.25, 0.26), 0.6, 0, {}),
    "light_emit":    ((1.0, 0.86, 0.68), 0.5, 0, {"emit": 1}),
    "led_emit":      ((1.0, 0.95, 0.88), 0.5, 0, {"emit": 1}),
    "glass":         ((1, 1, 1), 0.0, 0, {"glass": 1}),
    "glass_rail":    ((0.9, 0.95, 0.95), 0.0, 0, {"glass": 1}),
}


def make_materials():
    out = {}
    for name, (rgb, rough, metal, ex) in MATS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        if ex.get("glass"):
            b.inputs["Transmission Weight"].default_value = 1.0
            b.inputs["Alpha"].default_value = 0.25
        out[name] = m
    return out


# ---------------------------------------------------------------- geometry accumulators
class Geo:
    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def poly(self, pts, n, mat):
        P = [Vector(T(*p)) for p in pts]
        N = Vector((n[0], -n[1], n[2]))
        if (P[1] - P[0]).cross(P[2] - P[1]).dot(N) < 0:
            P.reverse()
        i = len(self.v)
        self.v += [tuple(p) for p in P]
        self.f.append(list(range(i, i + len(P))))
        self.m.append(mat)


G = {k: Geo() for k in ("A", "B", "N", "G")}
GROUP_OF = {"glass": "G", "glass_rail": "G", "exterior": "N", "cap": "N", "light_emit": "N",
            "led_emit": "N", "wire_white": "N", "mirror": "N"}
A_MATS = {"wall_white", "wall_accent", "ceiling_white", "floor_lvp"}


def geo(mat, shell=False):
    if mat in GROUP_OF:
        return G[GROUP_OF[mat]]
    return G["A"] if shell else G["B"]


def box(mat, u0, u1, v0, v1, z0, z1, skip="", inside=False, shell=False, mats=None):
    """Axis-aligned box. skip: faces to omit, lowercase = min side (u,v,z), uppercase = max side."""
    u0, u1 = min(u0, u1), max(u0, u1)
    v0, v1 = min(v0, v1), max(v0, v1)
    z0, z1 = min(z0, z1), max(z0, z1)
    s = -1 if inside else 1
    faces = {
        "u": ([(u0, v0, z0), (u0, v1, z0), (u0, v1, z1), (u0, v0, z1)], (-s, 0, 0)),
        "U": ([(u1, v0, z0), (u1, v1, z0), (u1, v1, z1), (u1, v0, z1)], (s, 0, 0)),
        "v": ([(u0, v0, z0), (u1, v0, z0), (u1, v0, z1), (u0, v0, z1)], (0, -s, 0)),
        "V": ([(u0, v1, z0), (u1, v1, z0), (u1, v1, z1), (u0, v1, z1)], (0, s, 0)),
        "z": ([(u0, v0, z0), (u1, v0, z0), (u1, v1, z0), (u0, v1, z0)], (0, 0, -s)),
        "Z": ([(u0, v0, z1), (u1, v0, z1), (u1, v1, z1), (u0, v1, z1)], (0, 0, s)),
    }
    for k, (pts, n) in faces.items():
        if k in skip:
            continue
        m = (mats or {}).get(k, mat)
        geo(m, shell).poly(pts, n, m)


def cyl(mat, c, r, h, axis="z", segs=28, caps="ab", r2=None, ry=None):
    """Cylinder from point c extending h along axis. ry: second radius for an elliptical section."""
    ax = "uvz".index(axis)
    o = [i for i in range(3) if i != ax]
    ry = ry or r
    r2 = r if r2 is None else r2

    def pt(a, t, rr):
        p = list(c)
        p[ax] += t
        p[o[0]] += math.cos(a) * rr
        p[o[1]] += math.sin(a) * rr * (ry / r)
        return tuple(p)
    g = geo(mat)
    for i in range(segs):
        a0, a1 = 2 * math.pi * i / segs, 2 * math.pi * (i + 1) / segs
        am = (a0 + a1) / 2
        n = [0, 0, 0]
        n[o[0]], n[o[1]] = math.cos(am), math.sin(am)
        g.poly([pt(a0, 0, r), pt(a1, 0, r), pt(a1, h, r2), pt(a0, h, r2)], n, mat)
    for t, rr, key, sgn in ((0, r, "a", -1), (h, r2, "b", 1)):
        if key in caps:
            n = [0, 0, 0]
            n[ax] = sgn * (1 if h > 0 else -1)
            g.poly([pt(2 * math.pi * i / segs, t, rr) for i in range(segs)], n, mat)


def ellipsoid(mat, c, rad, t0=0.0, t1=1.0, segs=28, rings=10, inside=False):
    """Lat/long ellipsoid; t0..t1 selects the latitude band (0 = bottom pole, 1 = top pole)."""
    g = geo(mat)

    def pt(i, j):
        th = math.pi * (t0 + (t1 - t0) * j / rings) - math.pi / 2
        ph = 2 * math.pi * i / segs
        return (c[0] + rad[0] * math.cos(th) * math.cos(ph), c[1] + rad[1] * math.cos(th) * math.sin(ph),
                c[2] + rad[2] * math.sin(th))
    for j in range(rings):
        for i in range(segs):
            pts = [pt(i, j), pt(i + 1, j), pt(i + 1, j + 1), pt(i, j + 1)]
            pts = [p for k, p in enumerate(pts) if p not in pts[:k]]
            if len(pts) < 3:
                continue
            m = [sum(p[k] for p in pts) / len(pts) - c[k] for k in range(3)]
            n = [m[k] / (rad[k] ** 2) for k in range(3)]
            if inside:
                n = [-x for x in n]
            g.poly(pts, n, mat)


def tube(mat, path, r, segs=12):
    g = geo(mat)
    P = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        a = t.cross(ref).normalized()
        b = t.cross(a).normalized()
        rings.append([p + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * r
                      for k in range(segs)])
    for i in range(len(rings) - 1):
        for k in range(segs):
            q = [rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]]
            n = (q[0] + q[1] + q[2] + q[3]) / 4 - (P[i] + P[i + 1]) / 2
            g.poly([tuple(x) for x in q], tuple(n), mat)
    g.poly([tuple(x) for x in rings[0]], tuple(P[0] - P[1]), mat)
    g.poly([tuple(x) for x in rings[-1]], tuple(P[-1] - P[-2]), mat)


def slab_with_hole(mat, u0, u1, v0, v1, z0, z1, hole, ellipse=False, skip=""):
    """Counter slab with a rectangular or elliptical cut-out. hole = (hu0, hu1, hv0, hv1)."""
    # an elliptical hole holds a bowl that hangs below the slab; an underside would shade it black
    box(mat, u0, u1, v0, v1, z0, z1, skip="Z" + skip + ("z" if ellipse else ""))
    g = geo(mat)
    hu0, hu1, hv0, hv1 = hole
    cu, cv, ru, rv = (hu0 + hu1) / 2, (hv0 + hv1) / 2, (hu1 - hu0) / 2, (hv1 - hv0) / 2
    if not ellipse:
        for a, b, c, d in ((u0, hu0, v0, v1), (hu1, u1, v0, v1), (hu0, hu1, v0, hv0), (hu0, hu1, hv1, v1)):
            g.poly([(a, c, z1), (b, c, z1), (b, d, z1), (a, d, z1)], (0, 0, 1), mat)
        box(mat, hu0, hu1, hv0, hv1, z0, z1, skip="zZ", inside=True)
        return
    angs = sorted(set([2 * math.pi * i / 48 for i in range(48)] +
                      [math.atan2(sv - cv, su - cu) % (2 * math.pi) for su in (u0, u1) for sv in (v0, v1)]))

    def rect_pt(a):
        du, dv = math.cos(a), math.sin(a)
        t = min(((u1 if du > 0 else u0) - cu) / du if abs(du) > 1e-9 else 1e9,
                ((v1 if dv > 0 else v0) - cv) / dv if abs(dv) > 1e-9 else 1e9)
        return (cu + du * t, cv + dv * t, z1)

    def ell_pt(a, z):
        return (cu + ru * math.cos(a), cv + rv * math.sin(a), z)
    for i in range(len(angs)):
        a, b = angs[i], angs[(i + 1) % len(angs)]
        g.poly([ell_pt(a, z1), ell_pt(b, z1), rect_pt(b), rect_pt(a)], (0, 0, 1), mat)


# ---------------------------------------------------------------- voxel shell (walls, floor, ceilings)
BASE_RUNS = []


def build_shell():
    boxes = list(S.WALLS) + list(S.OPENINGS.values()) + [(u0, u1, v0, v1, z0, z1) for u0, u1, v0, v1, z0, z1 in S.CEILINGS]
    floor = (U0 - 10, 267.5, V0 - 10, 405.5, -S.SLAB, 0)
    boxes.append(floor)
    xs = sorted({b[i] for b in boxes for i in (0, 1)})
    ys = sorted({b[i] for b in boxes for i in (2, 3)})
    zs = sorted({b[i] for b in boxes for i in (4, 5)})
    nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
    lab = np.zeros((nx, ny, nz), np.uint8)

    def sl(b):
        return (slice(xs.index(b[0]), xs.index(b[1])), slice(ys.index(b[2]), ys.index(b[3])),
                slice(zs.index(b[4]), zs.index(b[5])))
    for b in S.CEILINGS:
        lab[sl(b)] = 2
    lab[sl(floor)] = 1
    for b in S.WALLS:
        lab[sl(b)] = 1
    opening_of = np.full((nx, ny, nz), -1, np.int8)
    names = list(S.OPENINGS)
    for i, n in enumerate(names):
        lab[sl(S.OPENINGS[n])] = 0
        opening_of[sl(S.OPENINGS[n])] = i

    cx = [(xs[i] + xs[i + 1]) / 2 for i in range(nx)]
    cy = [(ys[i] + ys[i + 1]) / 2 for i in range(ny)]
    cz = [(zs[i] + zs[i + 1]) / 2 for i in range(nz)]

    def air_class(i, j, k):
        if not (0 <= i < nx and 0 <= j < ny and 0 <= k < nz):
            return "out", None
        if opening_of[i, j, k] >= 0:
            return "open", names[opening_of[i, j, k]]
        if 0 < cz[k] < CEIL:
            for (u0, u1, v0, v1) in S.ROOMS.values():
                if u0 < cx[i] < u1 and v0 < cy[j] < v1:
                    return "room", None
        return "out", None

    def L(i, j, k):
        if not (0 <= i < nx and 0 <= j < ny and 0 <= k < nz):
            return 0
        return lab[i, j, k]

    C = (xs, ys, zs)
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                s = lab[i, j, k]
                if s == 0:
                    continue
                idx = (i, j, k)
                for ax in range(3):
                    for sgn in (-1, 1):
                        nb = list(idx)
                        nb[ax] += sgn
                        o = L(*nb)
                        plane = C[ax][idx[ax] + (1 if sgn > 0 else 0)]
                        n = [0, 0, 0]
                        n[ax] = sgn
                        mat = None
                        if o == 0:
                            cls, oname = air_class(*nb)
                            if s == 1:
                                if cls == "out":
                                    mat = None if (ax == 2 and sgn < 0) else "exterior"
                                elif cls == "open":
                                    floorlike = ax == 2 and sgn > 0 and plane == 0 and oname != "slider"
                                    mat = "floor_lvp" if floorlike else "trim_white"
                                else:
                                    if ax == 2:
                                        mat = "floor_lvp" if (sgn > 0 and plane == 0) else "wall_white"
                                    else:
                                        mat = "wall_accent" if (ax == 1 and plane == 0 and sgn > 0) else "wall_white"
                                        if zs[k] == 0:
                                            o_ax = 1 - ax
                                            BASE_RUNS.append((ax, plane, sgn, C[o_ax][idx[o_ax]], C[o_ax][idx[o_ax] + 1]))
                            else:
                                mat = None if cls == "out" else "ceiling_white"
                        elif s == 1 and o == 2 and ax == 2 and sgn > 0:
                            mat = "cap"
                        if mat is None:
                            continue
                        a, b = [x for x in range(3) if x != ax]
                        p = []
                        for da, db in ((0, 0), (1, 0), (1, 1), (0, 1)):
                            q = [0, 0, 0]
                            q[ax] = plane
                            q[a] = C[a][idx[a] + da]
                            q[b] = C[b][idx[b] + db]
                            p.append(tuple(q))
                        geo(mat, shell=True).poly(p, n, mat)

    def solid_at(u, v, z=1.0):
        i = np.searchsorted(xs, u) - 1
        j = np.searchsorted(ys, v) - 1
        k = np.searchsorted(zs, z) - 1
        return L(i, j, k) != 0
    return solid_at


NO_BASE = [(231, 258, 134, 308), (55, 117, 228, 262), (29, 52, 303, 354), (79, 117, 353, 396)]


def build_baseboards(solid_at):
    runs = {}
    for ax, plane, sgn, a0, a1 in BASE_RUNS:
        runs.setdefault((ax, plane, sgn), []).append((a0, a1))
    for (ax, plane, sgn), iv in runs.items():
        iv.sort()
        merged = [list(iv[0])]
        for a0, a1 in iv[1:]:
            if a0 <= merged[-1][1] + 1e-6:
                merged[-1][1] = max(merged[-1][1], a1)
            else:
                merged.append([a0, a1])
        front = plane + sgn * 0.25
        inside = plane - sgn * 0.25
        for a0, a1 in merged:
            def pt(a, w):
                return (w, a) if ax == 0 else (a, w)
            if not solid_at(*pt(a0 - 0.25, inside)):
                a0 -= 0.5
            if not solid_at(*pt(a1 + 0.25, inside)):
                a1 += 0.5
            pieces = [(a0, a1)]
            for (u0, u1, v0, v1) in NO_BASE:
                w0, w1, b0, b1 = (u0, u1, v0, v1) if ax == 0 else (v0, v1, u0, u1)
                if w0 < front < w1:
                    nxt = []
                    for p0, p1 in pieces:
                        if b1 <= p0 or b0 >= p1:
                            nxt.append((p0, p1))
                        else:
                            if p0 < b0:
                                nxt.append((p0, b0))
                            if b1 < p1:
                                nxt.append((b1, p1))
                    pieces = nxt
            for p0, p1 in pieces:
                if p1 - p0 < 0.6:
                    continue
                if ax == 0:
                    box("trim_white", plane, plane + sgn * 0.5, p0, p1, 0, 4, skip="u" if sgn > 0 else "U")
                else:
                    box("trim_white", p0, p1, plane, plane + sgn * 0.5, 0, 4, skip="v" if sgn > 0 else "V")


# ---------------------------------------------------------------- doors, windows, trim
def casing(name, sides):
    u0, u1, v0, v1, z0, z1 = S.OPENINGS[name]
    along_v = (u1 - u0) < (v1 - v0)
    for side in sides:  # -1 = low face, +1 = high face of the wall
        if along_v:
            pl = u0 if side < 0 else u1
            for a, b in ((v0 - 3.5, v0), (v1, v1 + 3.5)):
                box("trim_white", pl, pl + side * 0.75, a, b, 0, z1 + 0.25)
            box("trim_white", pl, pl + side * 1.0, v0 - 4, v1 + 4, z1 + 0.25, z1 + 4.75)
        else:
            pl = v0 if side < 0 else v1
            for a, b in ((u0 - 3.5, u0), (u1, u1 + 3.5)):
                box("trim_white", a, b, pl, pl + side * 0.75, 0, z1 + 0.25)
            box("trim_white", u0 - 4, u1 + 4, pl, pl + side * 1.0, z1 + 0.25, z1 + 4.75)


def lever(u, v, z, axis, both=1.4):
    """Lever handle through a door leaf. axis = leaf thickness axis ('u' or 'v'); (u,v) at leaf centre."""
    for sgn in (-1, 1):
        off = sgn * both / 2
        if axis == "u":
            cyl("nickel", (u + off, v, z), 1.3, sgn * 0.4, axis="u", segs=20)
            cyl("nickel", (u + off + sgn * 0.4, v, z), 0.45, sgn * 1.6, axis="u", segs=12)
            box("nickel", u + off + sgn * 1.6, u + off + sgn * 2.2, v - 0.4, v + 4.2, z - 0.35, z + 0.35)
        else:
            cyl("nickel", (u, v + off, z), 1.3, sgn * 0.4, axis="v", segs=20)
            cyl("nickel", (u, v + off + sgn * 0.4, z), 0.45, sgn * 1.6, axis="v", segs=12)
            box("nickel", u - 0.4, u + 4.2, v + off + sgn * 1.6, v + off + sgn * 2.2, z - 0.35, z + 0.35)


def build_doors():
    for n, sides in (("bed_door", (-1, 1)), ("bath_door", (-1, 1)), ("closet_door", (-1, 1)), ("entry_door", (-1,))):
        casing(n, sides)
    T_ = 1.4
    # bedroom door: open 90 deg into the bedroom, parked along the closet wall
    box("door_white", 84, 116, 126 - T_, 126, 0.5, 80.5)
    lever(87, 126 - T_ / 2, 36, "v")
    # bathroom door: open into the bath
    box("door_white", 84, 116, 348 - T_, 348, 0.5, 80.5)
    lever(87, 348 - T_ / 2, 36, "v")
    # walk-in closet door: open into the closet
    box("door_white", 38.5, 38.5 + T_, 135.5, 167.5, 0.5, 80.5)
    lever(38.5 + T_ / 2, 164.5, 36, "u")
    # entry door, closed
    box("door_white", 128.5, 164.5, 395.3, 397.05, 0, 81)
    lever(161, 395.3 + 0.9, 38, "v", both=1.8)
    cyl("nickel", (161, 395.3, 44), 1.2, -0.5, axis="v", segs=20)
    # hinges
    for z in (8, 40, 72):
        box("nickel", 115.9, 116.3, 126 - 0.1, 126 + 0.5, z, z + 3.5)
        box("nickel", 115.9, 116.3, 348 - 0.1, 348 + 0.5, z, z + 3.5)
        box("nickel", 38.4, 38.9, 135.2, 135.7, z, z + 3.5)
        box("nickel", 128.2, 128.7, 394.9, 395.4, z, z + 3.5)
    # coat closet bypass doors (one slid open) + head track
    box("door_white", 188.6, 189.6, 320, 350.5, 0.6, 80.4)
    box("door_white", 190.2, 191.2, 321, 351.5, 0.6, 80.4)
    cyl("nickel", (188.6, 346, 36), 1.0, -0.12, axis="u", segs=20)
    box("trim_white", 188.2, 191.8, 320, 379, 80.4, 81)


def build_windows():
    # ---- bedroom window: fixed upper lite over an awning lower lite
    u0, u1, _, _, z0, z1 = S.OPENINGS["bed_window"]
    f0, f1 = V0 - 6.5, V0 - 3.5
    W = "trim_white"
    box(W, u0, u0 + 2, f0, f1, z0, z1); box(W, u1 - 2, u1, f0, f1, z0, z1)
    box(W, u0 + 2, u1 - 2, f0, f1, z0, z0 + 2); box(W, u0 + 2, u1 - 2, f0, f1, z1 - 2, z1)
    box(W, u0 + 2, u1 - 2, f0, f1, 46, 49.5)
    for a, b in ((z0 + 2, 46),):  # awning sash
        box(W, u0 + 2, u0 + 3.6, f0 + 0.6, f1 + 0.3, a, b); box(W, u1 - 3.6, u1 - 2, f0 + 0.6, f1 + 0.3, a, b)
        box(W, u0 + 3.6, u1 - 3.6, f0 + 0.6, f1 + 0.3, a, a + 1.6); box(W, u0 + 3.6, u1 - 3.6, f0 + 0.6, f1 + 0.3, b - 1.6, b)
    box("glass", u0 + 2, u1 - 2, V0 - 5.1, V0 - 4.9, z0 + 2, 46)
    box("glass", u0 + 2, u1 - 2, V0 - 5.1, V0 - 4.9, 49.5, z1 - 2)
    box(W, u0 + 16, u0 + 24, f1, f1 + 0.9, z0 + 2.2, z0 + 3.2)  # awning operator
    # interior trim: stool, apron, casings, shade cassette
    box(W, u0 - 3, u1 + 3, V0 - 3.5, V0 + 1.6, z0, z0 + 0.9)
    box(W, u0 - 2.2, u1 + 2.2, V0, V0 + 0.6, z0 - 3.5, z0)
    box(W, u0 - 2.5, u0, V0, V0 + 0.6, z0 + 0.9, z1); box(W, u1, u1 + 2.5, V0, V0 + 0.6, z0 + 0.9, z1)
    box(W, u0 - 3, u1 + 3, V0, V0 + 0.8, z1, z1 + 3.5)
    box(W, u0, u1, V0 - 3.4, V0 - 0.4, z1 - 3, z1)
    # ---- balcony slider: fixed panel + sliding panel
    u0, u1, _, _, z0, z1 = S.OPENINGS["slider"]
    f0, f1 = V0 - 7.5, V0 - 3.0
    box(W, u0, u0 + 2.2, f0, f1, 0, z1); box(W, u1 - 2.2, u1, f0, f1, 0, z1)
    box(W, u0 + 2.2, u1 - 2.2, f0, f1, 0, 1.4); box(W, u0 + 2.2, u1 - 2.2, f0, f1, z1 - 2.2, z1)
    mid = (u0 + u1) / 2
    for a, b, p0, p1 in ((u0 + 2.2, mid + 1.5, f0 + 0.4, f0 + 2.0), (mid - 1.5, u1 - 2.2, f1 - 2.0, f1 - 0.4)):
        box(W, a, a + 3, p0, p1, 1.4, z1 - 2.2); box(W, b - 3, b, p0, p1, 1.4, z1 - 2.2)
        box(W, a + 3, b - 3, p0, p1, 1.4, 5.4); box(W, a + 3, b - 3, p0, p1, z1 - 5.2, z1 - 2.2)
        box("glass", a + 3, b - 3, (p0 + p1) / 2 - 0.1, (p0 + p1) / 2 + 0.1, 5.4, z1 - 5.2)
    box(W, mid - 0.2, mid + 0.8, f1 - 0.4, f1 + 0.9, 36, 44)   # pull handle
    # interior: side casings + shade valance
    box(W, u0 - 2.5, u0, V0, V0 + 0.6, 0, z1); box(W, u1, u1 + 2.5, V0, V0 + 0.6, 0, z1)
    box(W, u0 - 3, u1 + 3, V0, V0 + 3.2, z1, z1 + 4)
    # ---- balcony
    b0, b1, d, e0 = 125, 241, V0 - 70, V0 - 10
    box("deck", b0, b1, d, e0, -3, -0.6)
    R = "rail_black"
    for (a, b, c, e) in ((b0, b1, d, d + 2), (b0, b0 + 2, d, e0), (b1 - 2, b1, d, e0)):
        box(R, a, b, c, e, 40, 42); box(R, a, b, c, e, 2.5, 4)
    posts = [(b0, d), (b1 - 2, d), (b0 + (b1 - b0 - 2) / 3, d), (b0 + 2 * (b1 - b0 - 2) / 3, d), (b0, e0 - 2), (b1 - 2, e0 - 2)]
    for (pu, pv) in posts:
        box(R, pu, pu + 2, pv, pv + 2, -0.6, 40)
    box("glass_rail", b0 + 2, b1 - 2, d + 0.8, d + 1.2, 4, 40)
    box("glass_rail", b0 + 0.8, b0 + 1.2, d + 2, e0 - 2, 4, 40)
    box("glass_rail", b1 - 1.2, b1 - 0.8, d + 2, e0 - 2, 4, 40)


# ---------------------------------------------------------------- kitchen
def bar_pull(u, v, z, axis, length=5.0, proud=1.2, mat="stainless"):
    """Bar handle on a front facing -U at plane u. axis 'v' = horizontal, 'z' = vertical."""
    if axis == "v":
        box(mat, u - proud - 0.4, u - proud, v - length / 2, v + length / 2, z - 0.2, z + 0.2)
        for o in (-length / 2 + 0.6, length / 2 - 0.6):
            box(mat, u - proud, u, v + o - 0.15, v + o + 0.15, z - 0.15, z + 0.15)
    else:
        box(mat, u - proud - 0.4, u - proud, v - 0.2, v + 0.2, z - length / 2, z + length / 2)
        for o in (-length / 2 + 0.6, length / 2 - 0.6):
            box(mat, u - proud, u, v - 0.15, v + 0.15, z + o - 0.15, z + o + 0.15)


def build_kitchen():
    KW, FR = 257.5, 233.5     # wall plane, carcass front
    D, WD = "cab_dark", "cab_wood"
    g = 0.0625
    K = S.KITCHEN

    def front(v0, v1, z0, z1, mat=D, u=FR):
        box(mat, u - 0.75, u, v0 + g, v1 - g, z0 + g, z1 - g, skip="U")

    def base(v0, v1, kind):
        box(D, FR, KW, v0, v1, 4.5, 34.5, skip="UZ")
        box(D, FR + 3, KW, v0, v1, 0, 4.5, skip="UZ")
        if kind == "drawers4":
            h = 29.5 / 4
            for i in range(4):
                front(v0, v1, 5 + i * h, 5 + (i + 1) * h)
                bar_pull(FR - 0.75, (v0 + v1) / 2, 5 + (i + 0.62) * h, "v")
        elif kind == "sink":
            front(v0, v1, 28.5, 34.5)
            m = (v0 + v1) / 2
            front(v0, m, 5, 28.5); front(m, v1, 5, 28.5)
            bar_pull(FR - 0.75, m - 1.6, 24.5, "z"); bar_pull(FR - 0.75, m + 1.6, 24.5, "z")
        else:
            front(v0, v1, 28.5, 34.5)
            bar_pull(FR - 0.75, (v0 + v1) / 2, 31.5, "v")
            front(v0, v1, 5, 28.5)
            bar_pull(FR - 0.75, v0 + 2.2 if kind == "door_l" else v1 - 2.2, 24.5, "z")

    base(*K["drawers"], "drawers4")
    base(*K["sink"], "sink")
    base(*K["cab_a"], "door_r")
    base(*K["cab_b"], "door_l")
    box(D, FR - 0.75, KW, 134.9, 135, 4.5, 34.5)   # finished end panel
    # dishwasher
    v0, v1 = K["dw"]
    box("appliance_dark", FR + 3, KW, v0, v1, 0, 4.5, skip="UZ")
    box("stainless", FR - 1.0, FR, v0 + 0.2, v1 - 0.2, 4.6, 34.3)
    box("stainless", FR - 2.6, FR - 2.1, v0 + 2.5, v1 - 2.5, 30.2, 31.0)
    for o in (v0 + 3, v1 - 3.4):
        box("stainless", FR - 2.1, FR - 1.0, o, o + 0.4, 30.3, 30.9)
    # countertops
    slab_with_hole("quartz", FR - 1.5, KW, 134.5, K["range"][0], 34.5, 36, (238, 254, 157, 185), skip="U")
    box("quartz", FR - 1.5, KW, K["range"][1], K["fridge"][0] + 0.75, 34.5, 36, skip="U")
    box("stainless", 238, 254, 157, 185, 26.5, 34.5, skip="Z", inside=True)
    cyl("chrome", (246, 171, 26.5), 2.0, 0.15, segs=20)
    # faucet
    cyl("chrome", (255.6, 171, 36), 1.1, 1.2, segs=20)
    pts = [(255.6, 171, 37.2), (255.6, 171, 47)]
    for i in range(1, 9):
        a = math.pi * i / 8
        pts.append((255.6 - 3.6 + 3.6 * math.cos(a), 171, 47 + 3.6 * math.sin(a)))
    pts.append((248.4, 171, 44.5))
    tube("chrome", pts, 0.5)
    box("chrome", 254.9, 255.3, 172.2, 172.7, 38.5, 41.5)
    # backsplash tile
    box("tile_marble", KW - 0.4, KW, 134.5, K["fridge"][0] + 0.75, 36, 96, skip="U")
    # range
    v0, v1 = K["range"]
    box("stainless", FR, KW - 0.5, v0 + 0.15, v1 - 0.15, 0.2, 35.6, skip="U")
    box("black_glass", FR - 1.2, KW - 3.5, v0 + 0.15, v1 - 0.15, 35.6, 36.15)
    box("stainless", FR - 1.2, FR, v0 + 0.2, v1 - 0.2, 1.2, 8.6)
    box("black_glass", FR - 1.4, FR, v0 + 0.2, v1 - 0.2, 8.9, 29.5)
    box("stainless", FR - 1.5, FR, v0 + 0.2, v1 - 0.2, 29.5, 35.4)
    box("stainless", FR - 3.4, FR - 2.8, v0 + 2, v1 - 2, 31.6, 32.4)
    for o in (v0 + 2.6, v1 - 3.0):
        box("stainless", FR - 2.8, FR - 1.5, o, o + 0.4, 31.7, 32.3)
    box("stainless", KW - 3.5, KW - 0.4, v0 + 0.15, v1 - 0.15, 35.6, 44.5)
    box("black_glass", KW - 3.6, KW - 3.5, v0 + 9, v1 - 9, 37.5, 43)
    for o in (v0 + 3, v0 + 6.3, v1 - 6.3, v1 - 3):
        cyl("appliance_dark", (KW - 3.5, o, 40.3), 0.95, -0.9, axis="u", segs=16)
    # refrigerator bay
    v0, v1 = K["fridge"]
    box(D, FR - 2.5, KW, v0, v0 + 0.75, 0, 96)
    f0, f1 = v0 + 3.6, v1 - 2.6
    box("appliance_dark", FR - 1.5, KW - 1, f0, f1, 0.6, 66.5, skip="U")
    box("stainless", FR - 4.3, FR - 1.6, f0, f1, 1.2, 45.6)
    box("stainless", FR - 4.3, FR - 1.6, f0, f1, 46.0, 66.4)
    box("stainless", FR - 6.0, FR - 5.4, f0 + 1.2, f0 + 2.2, 31, 44.5)
    box("stainless", FR - 6.0, FR - 5.4, f0 + 1.2, f0 + 2.2, 47.2, 58)
    for z in (31.3, 43.6, 47.5, 57.1):
        box("stainless", FR - 5.4, FR - 4.3, f0 + 1.3, f0 + 2.1, z, z + 0.6)
    box(D, FR, KW, v0 + 0.75, v1, 68, 96, skip="UZ")
    m = (v0 + 0.75 + v1) / 2
    front(v0 + 0.75, m, 68, 96); front(m, v1, 68, 96)
    bar_pull(FR - 0.75, m - 1.6, 71.5, "z"); bar_pull(FR - 0.75, m + 1.6, 71.5, "z")
    # upper cabinets (wood) ------------------------------------------------
    UF = 244.5 + 0.75

    def upper(v0, v1, z0, z1, doors, hand="split"):
        box(WD, UF, KW, v0, v1, z0, z1, skip="UZ")
        w = (v1 - v0) / doors
        for i in range(doors):
            box(WD, UF - 0.75, UF, v0 + i * w + g, v0 + (i + 1) * w - g, z0 + g, z1 - g, skip="U")
        if doors == 2:
            mm = (v0 + v1) / 2
            bar_pull(UF - 0.75, mm - 1.5, z0 + 4, "z"); bar_pull(UF - 0.75, mm + 1.5, z0 + 4, "z")
        else:
            bar_pull(UF - 0.75, v1 - 1.8 if hand == "r" else v0 + 1.8, z0 + 4, "z")

    upper(135, 147, 54, 96, 1, "r")
    for z in (54, 68, 82):                       # open shelves
        box(WD, UF - 0.75, KW - 0.4, 147, 171, z, z + 0.75)
    box(WD, UF - 0.75, KW - 0.4, 147, 147.75, 54.75, 96); box(WD, UF - 0.75, KW - 0.4, 170.25, 171, 54.75, 96)
    upper(171, 201, 54, 96, 2)
    upper(201, 228, 54, 96, 2)
    upper(228, 258, 78, 96, 2)
    # microwave
    box("stainless", 242, KW - 0.4, 228.2, 257.8, 61, 77.9, skip="U")
    box("black_glass", 241.8, 242, 229, 250.5, 62.2, 76.8)
    box("appliance_dark", 241.85, 242, 251.3, 257.2, 62.2, 76.8)
    box("stainless", 240.4, 240.9, 250.2, 250.9, 63, 76)
    for z in (63.2, 75.2):
        box("stainless", 240.9, 242, 250.3, 250.8, z, z + 0.6)


# ---------------------------------------------------------------- bathroom, laundry, closets
def wire_shelf(axis, wall, sgn, a0, a1, z, depth=12.0):
    """Wire closet shelf on a wall. axis = wall normal axis ('u'/'v'), sgn = direction into the room."""
    W = "wire_white"
    t = 0.14

    def b(w0, w1, p0, p1, z0, z1):
        if axis == "u":
            box(W, w0, w1, p0, p1, z0, z1)
        else:
            box(W, p0, p1, w0, w1, z0, z1)
    n = int(depth)
    for i in range(n + 1):
        w = wall + sgn * (0.3 + i * (depth - 0.3) / n)
        b(w - t / 2, w + t / 2, a0, a1, z - t, z)
    front = wall + sgn * depth
    b(front - t, front + t, a0, a1, z - 1.6, z - 1.6 + 2 * t)
    k = int((a1 - a0) / 12) + 1
    for i in range(k + 1):
        p = a0 + 0.4 + i * (a1 - a0 - 0.8) / k
        b(min(wall, front), max(wall, front), p - 0.1, p + 0.1, z - 0.3, z - 0.3 + 0.16)
    if axis == "u":
        cyl(W, (wall + sgn * (depth - 1.5), a0, z - 2.6), 0.5, a1 - a0, axis="v", segs=10)
    else:
        cyl(W, (a0, wall + sgn * (depth - 1.5), z - 2.6), 0.5, a1 - a0, axis="u", segs=10)


def build_bath():
    TW = "tub_white"
    # tub with basin
    slab_with_hole(TW, 56, 116, 229, 261, 0, 20, (59.5, 112.5, 232.5, 257.5), skip="z")
    box(TW, 59.5, 112.5, 232.5, 257.5, 4, 20, skip="Z", inside=True)
    cyl("chrome", (64, 245, 4), 1.4, 0.15, segs=18)
    for (a, b, c, d) in ((56, 116, 229, 229.4), (115.6, 116, 229.4, 261), (56, 56.4, 229.4, 261)):
        box(TW, a, b, c, d, 20, 80)
    # shower trim on the chase wall
    cyl("chrome", (56.4, 245, 42), 3.2, 0.3, axis="u", segs=24)
    cyl("chrome", (56.7, 245, 42), 1.1, 2.2, axis="u", segs=16)
    box("chrome", 58.2, 58.8, 244.6, 245.4, 38, 42)
    cyl("chrome", (56.4, 245, 27), 1.0, 5.5, axis="u", segs=16)
    cyl("chrome", (56.4, 245, 82), 1.3, 0.3, axis="u", segs=18)
    tube("chrome", [(56.5, 245, 82), (60, 245, 82.5), (62.5, 245, 81)], 0.4)
    cyl("chrome", (62.5, 245, 81.4), 1.0, -1.4, segs=18, r2=2.3)
    tube("chrome", [(56, 262.5, 80), (76, 266.5, 80), (96, 266.5, 80), (116, 262.5, 80)], 0.5)
    # toilet
    P = "porcelain"
    box(P, 30.4, 38.6, 273, 293, 15, 29.5)
    box(P, 30.2, 39.0, 272.6, 293.4, 29.5, 31)
    cyl("chrome", (38.6, 276, 27.5), 0.5, 0.5, axis="u", segs=10)
    box("chrome", 39.1, 39.5, 275.6, 278.6, 27.2, 27.8)
    cyl(P, (44, 283, 0), 5.0, 9, segs=28, ry=4.2, r2=6.0, caps="")
    ellipsoid(P, (47.5, 283, 15), (10.8, 7.6, 7.5), t0=0.0, t1=0.5)
    box(P, 36.5, 42, 277, 289, 7.5, 15)
    ellipsoid(P, (47.5, 283, 15.2), (10.8, 7.6, 1.3), t0=0.5, t1=1.0, rings=5)
    box(P, 37, 40.5, 277, 289, 15, 16.2)
    # vanity
    D = "cab_dark"
    box(D, 30, 51, 304, 353, 4, 33, skip="uVZ")
    box(D, 30, 48, 304, 353, 0, 4, skip="uVZ")
    g = 0.0625
    for (a, b) in ((305, 321), (321, 337)):
        box(D, 51, 51.75, a + g, b - g, 4.4, 32.6, skip="u")
    for i in range(3):
        box(D, 51, 51.75, 337 + g, 352.4, 4.4 + i * 9.4 + g, 4.4 + (i + 1) * 9.4 - g, skip="u")
        box("nickel", 52.9, 53.3, 342, 347.5, 4.4 + i * 9.4 + 6.4, 4.4 + i * 9.4 + 6.8)
        for o in (342.5, 346.7):
            box("nickel", 51.75, 52.9, o, o + 0.3, 4.4 + i * 9.4 + 6.45, 4.4 + i * 9.4 + 6.75)
    for v in (319.4, 322.6):
        box("nickel", 52.9, 53.3, v - 0.2, v + 0.2, 22, 27.5)
        for z in (22.5, 26.7):
            box("nickel", 51.75, 52.9, v - 0.15, v + 0.15, z, z + 0.3)
    slab_with_hole("quartz", 30, 52.5, 303.5, 353, 33, 34.5, (34.5, 48, 319, 338), ellipse=True, skip="uV")
    ellipsoid("porcelain", (41.25, 328.5, 34.5), (6.75, 9.5, 5.2), t0=0.0, t1=0.5, inside=True)
    box("quartz", 30, 30.75, 303.5, 353, 34.5, 38.5, skip="uV")
    cyl("chrome", (32.8, 328.5, 34.5), 0.8, 5.2, segs=16)
    box("chrome", 32.6, 37.5, 328.1, 328.9, 38.2, 39.0)
    box("chrome", 32.4, 33.2, 329.3, 331.5, 39.7, 40.2)
    # mirror + backlight
    box("mirror", 30, 30.6, 310.5, 346.5, 42, 80, skip="u")
    for (a, b) in ((308.9, 310.3), (346.7, 348.1)):
        box("led_emit", 30, 30.5, a, b, 42, 80, skip="u")
    box("trim_white", 68, 78, 270, 280, 95.7, 96)
    box("heater_grille", 69, 77, 271, 279, 95.6, 95.7)
    # washer / dryer stack in the alcove
    AW = "appliance_white"
    for z0, z1, glassmat in ((0.4, 38.6, "black_glass"), (38.9, 77.2, "appliance_dark")):
        box(AW, 84.5, 111.5, 362, 393, z0, z1)
        zc = z0 + 17.5
        cyl(AW, (98, 362, zc), 9.2, -1.3, axis="v", segs=36, caps="")
        cyl(AW, (98, 360.7, zc), 9.2, 0.01, axis="v", segs=36, caps="a", r2=6.6)
        cyl(glassmat, (98, 360.9, zc), 6.6, 0.01, axis="v", segs=36, caps="a")
        box("appliance_dark", 89, 107, 361.8, 362, z1 - 6.2, z1 - 2.6)
    # towel bar by the toilet
    tube("chrome", [(30.3, 268.5, 40), (32.6, 268.5, 40), (32.6, 268.5, 40.01)], 0.3)


def build_closets():
    wire_shelf("u", 30, 1, 135.5, 224, 68)
    wire_shelf("v", 224, -1, 42.3, 116, 68)
    wire_shelf("u", 217.5, -1, 312.5, 395, 66)


# ---------------------------------------------------------------- misc: heaters, plates, lights
def plate(axis, plane, sgn, along, z, w=2.9, h=4.6, t=0.25, mat="trim_white"):
    if axis == "u":
        box(mat, plane, plane + sgn * t, along - w / 2, along + w / 2, z - h / 2, z + h / 2)
    else:
        box(mat, along - w / 2, along + w / 2, plane, plane + sgn * t, z - h / 2, z + h / 2)


def build_misc():
    # wall heaters
    box("trim_white", 121.5, 122.4, V0 + 17.5, V0 + 27.5, 6, 19)
    box("heater_grille", 122.4, 122.5, V0 + 19, V0 + 26, 9, 16.5)
    box("trim_white", 80, 90, V0, V0 + 0.9, 6, 19)
    box("heater_grille", 81.5, 88.5, V0 + 0.9, V0 + 1.0, 9, 16.5)
    plate("v", V0, 1, 100, 19, w=12, h=12, t=0.35)
    # outlets, switches, thermostats
    for a in (38, 96):
        plate("u", 121.5, 1, a, 16)
    plate("u", 121.5, 1, 88, 48)
    plate("u", 121.5, 1, 190, 60, w=3.2, h=4.2, t=0.9)
    plate("u", 121.5, 1, 205, 16)
    plate("u", 257.5, -1, 60, 16); plate("u", 257.5, -1, 112, 16)
    plate("u", 257.1, -1, 196, 44); plate("u", 257.1, -1, 222, 44); plate("u", 257.1, -1, 150, 44)
    plate("v", V0, 1, 73, 16); plate("u", U0, 1, 70, 16)
    plate("v", 130, -1, 30, 48); plate("v", 130, -1, 22, 60, w=3.2, h=4.2, t=0.9)
    plate("u", 116, -1, 60, 16); plate("u", U0, 1, 110, 16)
    plate("u", 121.5, 1, 356, 48, w=4.6)
    plate("u", 116, -1, 310, 48)
    # smoke detectors + sprinklers
    for (u, v, z) in ((150, 100, CEIL), (40, 110, CEIL), (160, 320, 96)):
        cyl("trim_white", (u, v, z), 2.8, -1.4, segs=24)
    for (u, v, z) in ((190, 66, CEIL), (58, 58, CEIL), (73, 196, CEIL)):
        cyl("trim_white", (u, v, z), 1.5, -0.25, segs=16)
        cyl("nickel", (u, v, z - 0.25), 0.35, -1.2, segs=8)
    # light fixtures
    for (u, v, z, r, kind) in S.LIGHTS:
        if kind == "can":
            cyl("trim_white", (u, v, z), r + 0.7, -0.2, segs=28, caps="b", r2=r + 0.55)
            cyl("light_emit", (u, v, z - 0.25), r, 0.01, segs=28, caps="a")
        else:
            cyl("trim_white", (u, v, z), r + 0.3, -1.1, segs=32, caps="")
            cyl("light_emit", (u, v, z - 1.1), r + 0.3, 0.01, segs=32, caps="a")


# ---------------------------------------------------------------- blender objects
def to_object(name, g, mats):
    me = bpy.data.meshes.new(name)
    me.from_pydata(g.v, [], g.f)
    names = sorted(set(g.m))
    for n in names:
        me.materials.append(mats[n])
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in g.m])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            l[uv].uv = (c.x, c.y) if ax == 2 else ((c.y, c.z) if ax == 0 else (c.x, c.z))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(35))
    return ob


def lightmap_unwrap(ob):
    me = ob.data
    lm = me.uv_layers.new(name="LM")
    me.uv_layers.active = lm
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.0025)
    bpy.ops.object.mode_set(mode="OBJECT")


def setup_cycles(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:
        print("GPU setup failed, using CPU:", e)
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.01
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 6
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.view_settings.view_transform = "Standard"


SUN_DIR = Vector((-0.50, -0.62, -0.60))   # blender coords; sun shines from outside the window wall into the unit


def make_lights():
    sc = bpy.context.scene
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    sc.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.78, 0.86, 1.0, 1)
    day, lamp = [], []
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.2
    sun.angle = math.radians(2.5)
    sun.color = (1.0, 0.93, 0.82)
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = SUN_DIR.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(so)
    day.append(so)
    for n, w, h in (("slider", 96, 92), ("bed_window", 40, 88)):
        u0, u1, v0, v1, z0, z1 = S.OPENINGS[n]
        L = bpy.data.lights.new("Portal_" + n, "AREA")
        L.shape = "RECTANGLE"
        L.size, L.size_y = (u1 - u0) * IN, (z1 - z0) * IN
        L.cycles.is_portal = True
        o = bpy.data.objects.new("Portal_" + n, L)
        o.location = T((u0 + u1) / 2, V0 - 9, (z0 + z1) / 2)
        o.rotation_euler = (math.radians(90), 0, 0)    # -Z of the light points to -Y (into the unit)
        sc.collection.objects.link(o)
        day.append(o)
    for (u, v, z, r, kind) in S.LIGHTS:
        L = bpy.data.lights.new("Lamp", "AREA")
        L.shape = "DISK"
        L.size = 2 * r * IN
        L.energy = 14 if kind == "can" else 22
        L.color = (1.0, 0.80, 0.58)
        L.spread = math.radians(150)
        o = bpy.data.objects.new("Lamp", L)
        o.location = T(u, v, z - (0.4 if kind == "can" else 1.3))
        sc.collection.objects.link(o)
        lamp.append(o)
    for (a, b) in ((308.9, 310.3), (346.7, 348.1)):        # mirror backlight
        L = bpy.data.lights.new("Led", "AREA")
        L.shape = "RECTANGLE"
        L.size, L.size_y = 1.4 * IN, 38 * IN
        L.energy = 9
        L.color = (1.0, 0.93, 0.84)
        o = bpy.data.objects.new("Led", L)
        o.location = T(30.7, (a + b) / 2, 61)
        o.rotation_euler = (0, math.radians(-90), 0)
        sc.collection.objects.link(o)
        lamp.append(o)
    return world, day, lamp


def set_scenario(world, day, lamp, which):
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Strength"].default_value = 1.0 if which == "day" else 0.0
    for o in day:
        o.hide_render = which != "day"
    for o in lamp:
        o.hide_render = which != "lamp"


def bake(ob, name, res):
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    for m in ob.data.materials:
        nt = m.node_tree
        node = nt.nodes.get("BakeTarget") or nt.nodes.new("ShaderNodeTexImage")
        node.name = "BakeTarget"
        node.image = img
        nt.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.data.uv_layers.active = ob.data.uv_layers["LM"]
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=6, use_clear=True)
    path = os.path.join(WORK, name + ".exr")
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format = "OPEN_EXR"
    st.color_depth = "16"
    st.exr_codec = "ZIP"
    st.color_mode = "RGB"
    img.save_render(path, scene=sc)
    print("baked", path)


def preview(tag):
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 16
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = 1280, 800
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = arg("--exposure", 1.5)
    st = sc.render.image_settings
    st.file_format = "JPEG"
    views = {
        "living":  ((189, 250, 62), (185, 0, 50)),
        "kitchen": ((140, 120, 62), (257, 230, 45)),
        "back":    ((190, 30, 62), (170, 395, 50)),
        "bedroom": ((90, 140, 62), (40, 0, 55)),
        "bedback": ((30, 15, 62), (80, 152, 45)),
        "bath":    ((105, 335, 62), (40, 270, 35)),
        "entry":   ((150, 385, 62), (180, 200, 50)),
        "top":     ((130, 200, 520), (130, 199, 0)),
    }
    only = arg("--views", "")
    for n, (eye, tgt) in views.items():
        if only and n not in only.split(","):
            continue
        co.location = T(*eye)
        d = Vector(T(*tgt)) - Vector(T(*eye))
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.lens = 30 if n == "top" else 16
        hide_top = n == "top"
        for o in sc.objects:
            if o.type == "MESH":
                for i, m in enumerate(o.data.materials):
                    pass
        sc.render.filepath = os.path.join(WORK, f"preview_{tag}_{n}.jpg")
        if hide_top:
            hidden = hide_material_faces("ceiling_white")
        bpy.ops.render.render(write_still=True)
        if hide_top:
            for me, data in hidden:
                me.polygons.foreach_set("hide", data)


def hide_material_faces(mat):
    return []


def export_plan():
    plan = {
        "unit": "inches", "ceiling": CEIL,
        "walls": S.WALLS, "openings": S.OPENINGS, "passable": S.PASSABLE, "rooms": S.ROOMS,
        "fixtures": S.FIXTURES, "doorSwings": S.DOOR_SWINGS, "ceilings": S.CEILINGS, "lights": S.LIGHTS,
        "sunDir": [SUN_DIR.x, SUN_DIR.z, -SUN_DIR.y],
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "plan.json"), "w") as f:
        json.dump(plan, f, indent=1)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(WORK, exist_ok=True)
    mats = make_materials()
    solid_at = build_shell()
    build_baseboards(solid_at)
    build_doors()
    build_windows()
    build_kitchen()
    build_bath()
    build_closets()
    build_misc()
    obs = {k: to_object({"A": "Shell", "B": "Fixtures", "N": "Unlit", "G": "Glass"}[k], g, mats) for k, g in G.items()}
    for k, o in obs.items():
        print(k, len(o.data.polygons), "faces")
    export_plan()
    world, day, lamp = make_lights()
    setup_cycles(SAMPLES)

    if "preview" in ARGS:
        obs["G"].hide_render = True
        if "--top" in ARGS:
            pass
        sc = bpy.context.scene
        sc.cycles.samples = arg("--pv-samples", 96)
        for which in arg("--scen", "day").split(","):
            set_scenario(world, day, lamp, which)
            preview(which)

    if "bake" in ARGS:
        obs["G"].hide_render = True
        for k in ("A", "B"):
            lightmap_unwrap(obs[k])
        res = {"A": RES, "B": arg("--resB", RES)}
        for which in ("day", "lamp"):
            set_scenario(world, day, lamp, which)
            for k in ("A", "B"):
                bake(obs[k], f"lm_{k}_{which}", res[k])
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "apartment.blend"))

    if "export" in ARGS:
        for o in list(day) + list(lamp):
            bpy.data.objects.remove(o)
        for m in bpy.data.materials:
            n = m.node_tree.nodes.get("BakeTarget")
            if n:
                m.node_tree.nodes.remove(n)
        bpy.ops.object.select_all(action="DESELECT")
        for o in obs.values():
            o.hide_render = False
            o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "apartment.glb"), export_format="GLB",
                                  use_selection=True, export_apply=True, export_yup=True,
                                  export_materials="EXPORT", export_cameras=False, export_lights=False)
        print("exported glb")


main()
