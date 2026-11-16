"""Walls, floors, ceilings and baseboards. Declare walls and rooms, add doors, windows and every other part, then
call build() last: it cuts the openings and runs baseboards along every wall face that borders a room, stopping at
doorways and at anything standing against the wall."""
from . import core
from .core import box, mat, tag

BB_H, BB_T, CASING = 5.25, 0.6, 2.75


def _sub(iv, cuts):
    for c0, c1 in cuts:
        iv = [p for a, b in iv for p in ((a, min(b, c0)), (max(a, c1), b)) if p[1] - p[0] > 0.5]
    return iv


def _and(iv, keeps):
    return [(max(a, k0), min(b, k1)) for a, b in iv for k0, k1 in keeps if min(b, k1) - max(a, k0) > 0.5]


class Shell:
    def __init__(self, height, wall_rgb=None, ceiling_rgb=None, trim_rgb=None, floor="floor_wood", floor_rgb=None, plank="u"):
        """height: ceiling height. floor: vocabulary key of the default flooring; plank: 'u' if boards run along x."""
        self.h = height
        self.m_wall, self.m_ceil, self.m_trim = mat("wall_paint", wall_rgb), mat("ceiling_paint", ceiling_rgb), mat("trim_paint", trim_rgb)
        self.m_floor = mat(floor, floor_rgb, plank)
        self.walls, self.rooms, self.holes, self.openings = [], [], [], {}

    def wall(self, name, x0, x1, y0, y1, z0=0.0, z1=None, rgb=None, source=None):
        """Axis-aligned wall occupying plan rectangle x0..x1, y0..y1. Use z0/z1 for knee walls, soffits and headers."""
        self.walls.append(dict(name=name, x0=min(x0, x1), x1=max(x0, x1), y0=min(y0, y1), y1=max(y0, y1), z0=z0,
                               z1=self.h if z1 is None else z1, m=mat("wall_paint", rgb) if rgb else self.m_wall, source=source))

    def room(self, name, x0, x1, y0, y1, ceiling=None, floor=None, floor_rgb=None, plank="u", ceiling_key=None, source=None):
        """Clear floor rectangle of a room, wall face to wall face; an L-shaped room is several calls with one name.
        ceiling: height if lower than the shell's. floor: vocabulary key if not the default flooring."""
        self.rooms.append(dict(name=name, x0=min(x0, x1), x1=max(x0, x1), y0=min(y0, y1), y1=max(y0, y1), ceiling=ceiling or self.h,
                               floor=mat(floor, floor_rgb, plank) if floor else None,
                               m_ceil=mat(ceiling_key) if ceiling_key else self.m_ceil, source=source))

    def wall_at(self, x, y):
        for w in self.walls:
            if w["x0"] <= x <= w["x1"] and w["y0"] <= y <= w["y1"] and w["z0"] <= 0.5:
                return w
        raise ValueError("no wall at plan point (%s, %s)" % (x, y))

    def opening(self, x, y, width, along=None):
        """Finds the wall under plan point (x, y), the middle of an opening `width` wide. Returns the wall, the axis it
        runs along, the opening's range a..b along it and the wall's faces c0..c1 across it."""
        w = self.wall_at(x, y)
        along = along or ("x" if w["x1"] - w["x0"] >= w["y1"] - w["y0"] else "y")
        mid = x if along == "x" else y
        c0, c1 = (w["y0"], w["y1"]) if along == "x" else (w["x0"], w["x1"])
        return w, along, mid - width / 2, mid + width / 2, c0, c1

    def has_room(self, x, y):
        return any(r["x0"] - 0.1 <= x <= r["x1"] + 0.1 and r["y0"] - 0.1 <= y <= r["y1"] + 0.1 for r in self.rooms)

    def room_side(self, along, mid, c0, c1):
        """Compass letter of the side of a wall that has a room on it (for windows in outside walls)."""
        lo, hi = ((mid, c0 - 2), (mid, c1 + 2)) if along == "x" else ((c0 - 2, mid), (c1 + 2, mid))
        letters = ("N", "S") if along == "x" else ("W", "E")
        return letters[1] if self.has_room(*hi) and not self.has_room(*lo) else letters[0] if self.has_room(*lo) else letters[1]

    def hole(self, cutter, x0, x1, y0, y1, z0, z1):
        """cutter() must return a new object to subtract from every wall it touches."""
        self.holes.append((cutter, min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), z0, z1))

    def box_hole(self, name, along, a, b, c0, c1, z0, z1, doorway=False):
        """Rectangular opening through a wall; doorway=True marks one people walk through."""
        x0, x1, y0, y1 = (a, b, c0 - 1, c1 + 1) if along == "x" else (c0 - 1, c1 + 1, a, b)
        self.hole(lambda: box("cut", x0, x1, y0, y1, z0, z1, None), x0, x1, y0, y1, z0, z1)
        self.openings[name] = dict(along=along, a=a, b=b, c0=c0, c1=c1, z0=max(z0, 0), z1=z1, doorway=doorway)

    # ---------------------------------------------------------------- build
    def build(self):
        X0, X1 = min(w["x0"] for w in self.walls), max(w["x1"] for w in self.walls)
        Y0, Y1 = min(w["y0"] for w in self.walls), max(w["y1"] for w in self.walls)
        with tag(group="A", coll="shell", room=""):
            for w in self.walls:
                with tag(source=w["source"] or core._tags[-1]["source"]):
                    ob = box(w["name"], w["x0"], w["x1"], w["y0"], w["y1"], w["z0"], w["z1"], w["m"])
                    cutters = [h[0]() for h in self.holes if h[1] < w["x1"] and h[2] > w["x0"] and h[3] < w["y1"] and h[4] > w["y0"]
                               and h[5] < w["z1"] and h[6] > w["z0"]]
                    core.cut(ob, cutters)
            box("floor", X0, X1, Y0, Y1, -0.5, 0, self.m_floor)
            box("slab", X0, X1, Y0, Y1, -8, -0.5, mat("concrete"))
            for r in self.rooms:
                with tag(room=r["name"], source=r["source"] or core._tags[-1]["source"]):
                    if r["floor"]:
                        box("floor_" + r["name"], r["x0"], r["x1"], r["y0"], r["y1"], 0, 0.06, r["floor"])
                    with tag(coll="ceiling"):
                        if r["ceiling"] < self.h - 0.01:
                            box("ceiling_" + r["name"], r["x0"], r["x1"], r["y0"], r["y1"], r["ceiling"], self.h, r["m_ceil"])
            with tag(coll="ceiling"):
                box("ceiling", X0, X1, Y0, Y1, self.h, self.h + 6, self.m_ceil)
        with tag(group="B", coll="trim", room=""):
            for w in self.walls:
                if w["z0"] > 0.5 or w["z1"] < 2 * BB_H:
                    continue
                for along, c, s in (("x", w["y0"], -1), ("x", w["y1"], 1), ("y", w["x0"], -1), ("y", w["x1"], 1)):
                    self._baseboard(w, along, c, s)

    def _baseboard(self, w, along, c, s):
        """Baseboard on the face of wall w at coordinate c (across the wall), the room being on side s."""
        a0, a1 = (w["x0"], w["x1"]) if along == "x" else (w["y0"], w["y1"])
        p = c + s * 0.5   # a line just in front of the face
        A, C = ("x", "y") if along == "x" else ("y", "x")
        over = lambda rects: [(r[A + "0"], r[A + "1"]) for r in rects if r[C + "0"] <= p <= r[C + "1"]]
        iv = _and([(a0, a1)], [(r[A + "0"] - 0.1, r[A + "1"] + 0.1) for r in self.rooms if r[C + "0"] - 1 <= p <= r[C + "1"] + 1])
        iv = _sub(iv, over([o for o in self.walls if o is not w and o["z0"] <= 0.5]))
        iv = _sub(iv, [(d["a"] - CASING, d["b"] + CASING) for d in self.openings.values()
                       if d["doorway"] and d["along"] == along and d["c0"] - 0.1 <= c <= d["c1"] + 0.1])
        feet = [dict(x0=f[1], y0=f[2], x1=f[3], y1=f[4]) for f in core.FOOTPRINTS]
        iv = _sub(iv, [(a - 0.05, b + 0.05) for a, b in over(feet)])
        for a, b in iv:
            # at an outside corner the board has to run past the wall's end to meet the one coming round
            if abs(a - a0) < 0.01 and self.has_room(*((a - 1, p) if along == "x" else (p, a - 1))):
                a -= BB_T
            if abs(b - a1) < 0.01 and self.has_room(*((b + 1, p) if along == "x" else (p, b + 1))):
                b += BB_T
            c0, c1 = sorted((c, c + s * BB_T))
            if along == "x":
                box("baseboard", a, b, c0, c1, 0, BB_H, self.m_trim)
            else:
                box("baseboard", c0, c1, a, b, 0, BB_H, self.m_trim)

    def plan(self):
        """The shell's part of plan.json, in the viewer's layout: boxes are [x0, x1, y0, y1, z0, z1] in plan inches."""
        rooms, n = {}, {}
        for r in self.rooms:   # the viewer keys rooms by name; a room made of several rectangles gets "name#2", ...
            n[r["name"]] = n.get(r["name"], 0) + 1
            rooms[r["name"] + ("#%d" % n[r["name"]] if n[r["name"]] > 1 else "")] = [r["x0"], r["x1"], r["y0"], r["y1"]]
        rect = lambda d: [d["a"], d["b"], d["c0"], d["c1"]] if d["along"] == "x" else [d["c0"], d["c1"], d["a"], d["b"]]
        return dict(
            unit="inches", ceiling=self.h,
            walls=[[w["x0"], w["x1"], w["y0"], w["y1"], w["z0"], w["z1"]] for w in self.walls if w["z0"] <= 0.5 and w["z1"] > 30],
            openings={k: rect(d) + [d["z0"], d["z1"]] for k, d in self.openings.items()},
            passable=[k for k, d in self.openings.items() if d["doorway"]],
            rooms=rooms, heights={r["name"]: r["ceiling"] for r in self.rooms})
