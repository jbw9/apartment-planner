"""Light. Daylight (sky, sun, window portals) and lamps (the unit's own fixtures) are kept apart because they are
baked separately, so the viewer can mix them from midday to night."""
import math

import bpy
from mathutils import Vector

from .core import FACING, IN, P, at, plan

LAMPS = []      # [x, y, z, radius, kind] in plan inches, for the viewer's reflections and minimap
SUN = [0.0, 0.0, 1.0]   # direction to the sun in plan axes


def _link(ob, scenario):
    c = bpy.data.collections.get("lights_" + scenario) or bpy.data.collections.new("lights_" + scenario)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    c.objects.link(ob)
    return ob


def daylight(sun_from="S", elevation=38.0, sky=(0.78, 0.86, 1.0), strength=1.0, sun=3.2):
    """Sky plus a sun shining from compass direction `sun_from` (letter, or degrees as for facing)."""
    sc = bpy.context.scene
    w = sc.world = bpy.data.worlds.new("sky")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value, bg.inputs[1].default_value = (*sky, 1), strength
    d = math.radians(FACING.get(sun_from, sun_from))
    el = math.radians(elevation)
    to_sun = Vector((math.sin(d) * math.cos(el) * 1, -math.cos(d) * math.cos(el), math.sin(el)))   # Blender axes
    L = bpy.data.lights.new("sun", "SUN")
    L.energy, L.angle, L.color = sun, math.radians(2.5), (1, 0.93, 0.82)
    SUN[:] = [math.sin(d) * math.cos(el), math.cos(d) * math.cos(el), math.sin(el)]
    ob = _link(bpy.data.objects.new("sun", L), "day")
    ob.rotation_euler = to_sun.to_track_quat("Z", "Y").to_euler()


def portal(win, shell):
    """Tells Cycles where daylight comes in, which makes window light converge far faster. Pass a window()'s result."""
    from .openings import _frame
    L = bpy.data.lights.new(win["name"] + "_portal", "AREA")
    L.shape, L.size, L.size_y = "RECTANGLE", (win["b"] - win["a"]) * IN, win["height"] * IN
    L.cycles.is_portal = True
    ob = _link(bpy.data.objects.new(L.name, L), "day")
    with at(*_frame(win["along"], win["a"], win["b"], win["c0"], win["c1"], win["side"])):
        u = (win["b"] - win["a"]) / 2
        ob.location = P(u, -(win["c1"] - win["c0"]) - 1, win["sill"] + win["height"] / 2)
        ob.rotation_euler = (P(u, 10, 0) - P(u, 0, 0)).to_track_quat("-Z", "Z").to_euler()


def lamp(name, x, y, z, watts=14.0, radius=2.5, spread=150.0, rgb=(1.0, 0.88, 0.74)):
    """Downlight: a disc shining down from plan point (x, y) at height z."""
    L = bpy.data.lights.new(name, "AREA")
    L.shape, L.size, L.energy, L.color, L.spread = "DISK", 2 * radius * IN, watts, rgb, math.radians(spread)
    ob = _link(bpy.data.objects.new(name, L), "lamp")
    ob.location = P(x, y, z)
    LAMPS.append([*plan(x, y, z), radius, "can"])
    return ob


def bulb(name, x, y, z, watts=9.0, radius=1.5, rgb=(1.0, 0.90, 0.78)):
    """Bare bulb shining all round (pendants, vanity lights, table lamps)."""
    L = bpy.data.lights.new(name, "POINT")
    L.energy, L.color, L.shadow_soft_size = watts, rgb, radius * IN
    ob = _link(bpy.data.objects.new(name, L), "lamp")
    ob.location = P(x, y, z)
    LAMPS.append([*plan(x, y, z), radius, "bulb"])
    return ob


def scenario(which):
    """'day', 'lamp' or 'both': which light is on for the next render or bake."""
    w = bpy.context.scene.world
    if w:
        w.node_tree.nodes["Background"].inputs[1].default_value = 1.0 if which in ("day", "both") else 0.0
    for s in ("day", "lamp"):
        c = bpy.data.collections.get("lights_" + s)
        for ob in (c.objects if c else ()):
            ob.hide_render = which not in (s, "both")
