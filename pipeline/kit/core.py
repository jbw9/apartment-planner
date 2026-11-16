"""Core of the apartment parts kit: coordinates, placement, primitives, materials and tags.

Coordinates are INCHES as on the floor-plan drawing: x to the right, y DOWN the page, z up from the floor.
Inside `with at(x, y, facing):` coordinates are local to a part standing at plan point (x, y):
  u  along the wall, left to right as seen by someone in the room looking at the part
  v  out from the wall into the room (the direction the part faces)
  z  up
With no `at` active, (u, v, z) is plan (x, y, z).
"""
import math
import os
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix, Vector

IN = 0.0254
TEX = os.environ.get("KIT_TEX") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "public", "tex")
FACING = {"S": 0, "E": 90, "N": 180, "W": 270}
TO_BLENDER = Matrix.Diagonal((IN, -IN, IN, 1))

_stack = [Matrix.Identity(4)]
_tags = [dict(room="", source="seen", group="C", coll="parts")]
FOOTPRINTS = []   # [name, x0, y0, x1, y1, height] in plan inches, for collision in the viewer
MATS = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    del _stack[1:], _tags[1:], FOOTPRINTS[:]
    MATS.clear()
    from . import lights
    del lights.LAMPS[:]


@contextmanager
def at(x, y, facing="S", z=0.0):
    """Local frame at plan (x, y). `facing` is the compass letter the part faces (N is up the page), or degrees
    turning from S (0) through E (90)."""
    d = math.radians(FACING.get(facing, facing))
    vx, vy = math.sin(d), math.cos(d)
    _stack.append(_stack[-1] @ Matrix(((vy, vx, 0, x), (-vx, vy, 0, y), (0, 0, 1, z), (0, 0, 0, 1))))
    try:
        yield
    finally:
        _stack.pop()


@contextmanager
def tag(**kw):
    """room=..., source='seen'|'plan'|'guess', group='A' shell|'B' trim, doors, windows|'C' built-ins|'D' furniture,
    coll=collection name."""
    if kw.get("room") == "":   # parts pass room="" when the caller named none; the enclosing tag's room then stands
        del kw["room"]
    _tags.append({**_tags[-1], **kw})
    try:
        yield
    finally:
        _tags.pop()


def plan(u, v, z=0.0):
    """Local point -> plan inches."""
    return _stack[-1] @ Vector((u, v, z))


def P(u, v, z=0.0):
    """Local point -> Blender metres."""
    return TO_BLENDER @ plan(u, v, z)


def footprint(name, u0, u1, v0, v1, height):
    """Registers floor space the part occupies, so the viewer's walker cannot pass through it."""
    pts = [plan(u, v) for u in (u0, u1) for v in (v0, v1)]
    FOOTPRINTS.append([name, min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts),
                       height + _stack[-1].translation.z])


# ------------------------------------------------------------------ materials
# The viewer has a tuned material for every key here, so parts must use these and nothing else.
# kind: 'emit' and 'glass' are not lightmapped. tex: (file in TEX, inches per repeat along and across).
VOCAB = {
    "wall_paint": dict(rgb=(226, 222, 213), rough=0.92, spec=0.3),
    "ceiling_paint": dict(rgb=(242, 243, 243), rough=0.95, spec=0.2),
    "trim_paint": dict(rgb=(238, 238, 234), rough=0.45),
    "door_paint": dict(rgb=(236, 236, 232), rough=0.5),
    "floor_wood": dict(rgb=(255, 255, 255), rough=0.42, spec=0.38, tex=("floor_color.jpg", 112, 144), mean=(200, 184, 160)),
    "floor_tile": dict(rgb=(205, 203, 198), rough=0.3),
    "carpet": dict(rgb=(176, 168, 156), rough=1.0, spec=0.1),
    "wall_tile": dict(rgb=(255, 255, 255), rough=0.12, spec=0.6, tex=("subway.jpg", 12, 6), mean=(249, 249, 247)),
    "stone_tile": dict(rgb=(255, 255, 255), rough=0.15, spec=0.6, tex=("tile_marble.jpg", 48, 24), mean=(231, 232, 236)),
    "ceiling_tile": dict(rgb=(255, 255, 255), rough=0.95, spec=0.1, tex=("ceiling_tile.jpg", 24, 48), mean=(244, 245, 240)),
    "cabinet_paint": dict(rgb=(168, 162, 134), rough=0.45, spec=0.45),
    "cabinet_wood": dict(rgb=(255, 255, 255), rough=0.6, tex=("cab_wood.jpg", 24, 24), mean=(226, 217, 201)),
    "counter": dict(rgb=(240, 238, 232), rough=0.18, spec=0.6),
    "stainless": dict(rgb=(150, 150, 150), rough=0.32, metal=1.0),
    "black_metal": dict(rgb=(22, 22, 22), rough=0.45, metal=0.3),
    "chrome": dict(rgb=(230, 230, 230), rough=0.08, metal=1.0),
    "nickel": dict(rgb=(190, 188, 182), rough=0.3, metal=1.0),
    "brass": dict(rgb=(196, 160, 96), rough=0.3, metal=1.0),
    "black_glass": dict(rgb=(8, 8, 9), rough=0.05, spec=0.8),
    "appliance_white": dict(rgb=(240, 240, 236), rough=0.3),
    "appliance_black": dict(rgb=(14, 14, 15), rough=0.35),
    "porcelain": dict(rgb=(244, 244, 240), rough=0.12, spec=0.6),
    "mirror": dict(rgb=(240, 240, 240), rough=0.02, metal=1.0),
    "plastic": dict(rgb=(240, 240, 236), rough=0.35),
    "vinyl": dict(rgb=(240, 240, 238), rough=0.4),
    "blind": dict(rgb=(240, 240, 236), rough=0.5),
    "fabric": dict(rgb=(150, 148, 142), rough=0.95, spec=0.15),
    "leather": dict(rgb=(60, 44, 34), rough=0.5),
    "wood": dict(rgb=(150, 110, 70), rough=0.55),
    "rug": dict(rgb=(170, 165, 155), rough=1.0, spec=0.1),
    "plant": dict(rgb=(52, 96, 44), rough=0.6),
    "concrete": dict(rgb=(150, 150, 148), rough=0.9),
    "frosted_glass": dict(rgb=(215, 222, 222), rough=0.6),
    "screen": dict(rgb=(10, 10, 12), rough=0.08, spec=0.8),
    "glass": dict(kind="glass"),
    "emit_warm": dict(rgb=(255, 236, 205), kind="emit", strength=25.0),
    "emit_cool": dict(rgb=(235, 244, 255), kind="emit", strength=25.0),
    "emit_shade": dict(rgb=(255, 240, 215), kind="emit", strength=3.0),   # a lit fabric lamp shade
    "emit_display": dict(rgb=(120, 200, 255), kind="emit", strength=3.0),
    "outside": dict(rgb=(190, 208, 226), kind="emit", strength=1.0),
}


def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def mat(key, rgb=None, plank="u"):
    """Material from the vocabulary, optionally in another colour (sRGB 0-255). For a textured key, `rgb` is the
    colour the surface averages out to, and `plank` ('u' or 'v') is the plan axis its long side runs along ('u' is x)."""
    v = VOCAB[key]
    rgb = tuple(rgb or v.get("rgb", (255, 255, 255)))
    name = key if rgb == v.get("rgb", rgb) and plank == "u" else "%s.%02x%02x%02x%s" % (key, *rgb, "" if plank == "u" else "v")
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    # a textured key already has a colour of its own, so `rgb` is the colour the surface should average out to
    tint = tuple(min(255, round(c * 255 / t)) for c, t in zip(rgb, v["mean"])) if "mean" in v and rgb != (255, 255, 255) else rgb
    col = (*[lin(c) for c in tint], 1.0)
    m.diffuse_color = col
    m["rgb"], m["plank"] = list(tint), plank
    kind = v.get("kind")
    if kind == "emit":
        nt.nodes.clear()
        e, o = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
        e.inputs["Color"].default_value, e.inputs["Strength"].default_value = col, v["strength"]
        nt.links.new(e.outputs[0], o.inputs[0])
    elif kind == "glass":
        nt.nodes.clear()
        tr, gl, fr, mx, o = (nt.nodes.new("ShaderNode" + n) for n in ("BsdfTransparent", "BsdfGlossy", "Fresnel", "MixShader", "OutputMaterial"))
        tr.inputs["Color"].default_value = (0.93, 0.95, 0.95, 1)
        gl.inputs["Roughness"].default_value = 0.02
        for a, b in ((fr.outputs[0], mx.inputs[0]), (tr.outputs[0], mx.inputs[1]), (gl.outputs[0], mx.inputs[2]), (mx.outputs[0], o.inputs[0])):
            nt.links.new(a, b)
        m.diffuse_color = (0.8, 0.9, 1, 0.3)
    else:
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = col
        b.inputs["Roughness"].default_value = v.get("rough", 0.5)
        b.inputs["Metallic"].default_value = v.get("metal", 0.0)
        b.inputs["Specular IOR Level"].default_value = v.get("spec", 0.5)
        if "tex" in v and os.path.exists(os.path.join(TEX, v["tex"][0])):
            f, su, sv = v["tex"]
            tc, mp, tx, mul = (nt.nodes.new("ShaderNode" + n) for n in ("TexCoord", "Mapping", "TexImage", "Mix"))
            mp.inputs["Scale"].default_value = (1 / (su * IN), 1 / (sv * IN), 1)
            mp.inputs["Rotation"].default_value = (0, 0, 0 if plank == "u" else math.pi / 2)
            tx.image = bpy.data.images.load(os.path.join(TEX, f), check_existing=True)
            mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
            mul.inputs["Factor"].default_value = 1.0
            mul.inputs["B"].default_value = col
            for a, c in ((tc.outputs["UV"], mp.inputs[0]), (mp.outputs[0], tx.inputs[0]), (tx.outputs[0], mul.inputs["A"]),
                         (mul.outputs["Result"], b.inputs["Base Color"])):
                nt.links.new(a, c)
    MATS[name] = m
    return m


# ------------------------------------------------------------------ primitives
def emit(name, bm, material, smooth=False):
    """Turns a bmesh built in local inches into a tagged object. Use this for any custom shape."""
    bmesh.ops.transform(bm, matrix=TO_BLENDER @ _stack[-1], verts=bm.verts)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)   # plan y points down the page, so the transform mirrors
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    for m in material if isinstance(material, (list, tuple)) else [material]:
        if m is not None:
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    t = _tags[-1]
    c = bpy.data.collections.get(t["coll"]) or bpy.data.collections.new(t["coll"])
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    c.objects.link(ob)
    first = me.materials[0].name.split(".")[0] if me.materials else ""
    # glass would block the light being baked and emitters are their own light, so neither is lightmapped
    ob["room"], ob["source"] = t["room"], t["source"]
    ob["group"] = {"glass": "G", "emit": "N"}.get(VOCAB.get(first, {}).get("kind"), t["group"])
    return ob


def box(name, u0, u1, v0, v1, z0, z1, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(abs(u1 - u0), abs(v1 - v0), abs(z1 - z0)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2), verts=bm.verts)
    return emit(name, bm, material)


def cyl(name, c, a0, a1, r, material, axis="z", seg=24, r1=None, smooth=True):
    """Cylinder (or cone, with r1) from a0 to a1 along `axis` ('u', 'v' or 'z'); `c` is its centre in the other two
    coordinates, in (u, v, z) order."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r1 is None else r1, depth=abs(a1 - a0))
    mid = (a0 + a1) / 2
    if axis == "u":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        pos = (mid, c[0], c[1])
    elif axis == "v":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, "X"))
        pos = (c[0], mid, c[1])
    else:
        pos = (c[0], c[1], mid)
    bmesh.ops.translate(bm, vec=pos, verts=bm.verts)
    return emit(name, bm, material, smooth)


def ellipsoid(name, c, radii, material, seg=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
    bmesh.ops.scale(bm, vec=radii, verts=bm.verts)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    return emit(name, bm, material, True)


def prism(name, pts, z0, z1, material, smooth=False):
    """Extrudes a polygon of (u, v) points from z0 to z1."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((u, v, z0)) for u, v in pts])
    top = bmesh.ops.extrude_face_region(bm, geom=[f])["geom"]
    bmesh.ops.translate(bm, vec=(0, 0, z1 - z0), verts=[e for e in top if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return emit(name, bm, material, smooth)


def tube(name, pts, r, material, seg=10):
    """Round tube along a polyline of (u, v, z) points."""
    bm = bmesh.new()
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.orthogonal().normalized()
        b = d.cross(a)
        rings.append([bm.verts.new(p + r * (math.cos(t) * a + math.sin(t) * b)) for t in (2 * math.pi * k / seg for k in range(seg))])
    for i in range(1, len(rings)):   # consecutive rings can be twisted against each other; start from the nearest vertex
        k0 = min(range(seg), key=lambda k: (rings[i][k].co - rings[i - 1][0].co).length)
        rings[i] = rings[i][k0:] + rings[i][:k0]
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return emit(name, bm, material, True)


def cut(ob, cutters):
    """Subtracts the cutter objects from ob and deletes them."""
    for c in cutters:
        md = ob.modifiers.new("cut", "BOOLEAN")
        md.operation, md.object, md.solver = "DIFFERENCE", c, "EXACT"
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(c, do_unlink=True)
    return ob


def finish():
    """Call once after the last part: gives every mesh the texture UVs (metres, projected along each face's
    dominant axis) that both Blender and the viewer map textures with."""
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        mw = ob.matrix_world
        for p in me.polygons:
            n = mw.to_3x3() @ p.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            i, j = ((1, 2), (0, 2), (0, 1))[ax]
            for li in p.loop_indices:
                co = mw @ me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv = (co[i], co[j])
