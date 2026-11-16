"""The fixed finish: bakes daylight and lamplight into lightmaps, denoises them, and writes what the viewer loads
(model.glb, lm_<group>_<day|lamp>.exr, plan.json). No model is involved; every unit goes through the same code."""
import json
import math
import os
import tempfile

import time

import bpy
import numpy as np

from . import core, lights, view

RES = {"A": 4096, "B": 2048, "C": 4096, "D": 2048}   # shell | trim, doors, windows | built-ins | furniture


def _only(obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


def _join(group, obs):
    for o in obs:
        # joined meshes lose their objects' tags, so guessed faces carry the flag themselves
        o.data.attributes.new("guess", "INT", "FACE").data.foreach_set("value", [int(o.get("source") == "guess")] * len(o.data.polygons))
    _only(obs)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "LM_" + group
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.data.uv_layers.active = ob.data.uv_layers.new(name="LM")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def _split_guess(ob):
    """Moves guessed faces to their own object (same lightmap) so the viewer can highlight them."""
    me = ob.data
    flags = [d.value for d in me.attributes["guess"].data]
    if all(flags):
        ob.name += "_guess"
    if not any(flags) or all(flags):
        return [ob]
    for seq in (me.vertices, me.edges):
        seq.foreach_set("select", [False] * len(seq))
    me.polygons.foreach_set("select", [bool(f) for f in flags])
    _only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    other = next(o for o in bpy.context.selected_objects if o is not ob)
    other.name = ob.name + "_guess"
    return [ob, other]


def _denoise(pairs):
    """Cycles does not denoise bakes; OpenImageDenoise through the compositor does, and keeps shadow edges."""
    sc = bpy.data.scenes.new("denoise")
    cam = bpy.data.objects.new("denoise_cam", bpy.data.cameras.new("denoise_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    tree = bpy.data.node_groups.new("denoise", "CompositorNodeTree")
    sc.compositing_node_group = tree
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    img, dn, out = (tree.nodes.new(t) for t in ("CompositorNodeImage", "CompositorNodeDenoise", "NodeGroupOutput"))
    tree.links.new(img.outputs[0], dn.inputs[0])
    tree.links.new(dn.outputs[0], out.inputs[0])
    st = sc.render.image_settings
    # the denoised maps are smooth, so lossy DWAA shrinks them several times over without visible loss
    st.file_format, st.color_depth, st.exr_codec, st.color_mode = "OPEN_EXR", "16", "DWAA", "RGB"
    sc.view_settings.view_transform = "Standard"
    for src, dst in pairs:
        im = bpy.data.images.load(src)
        im.colorspace_settings.name = "Non-Color"
        img.image = im
        sc.render.resolution_x, sc.render.resolution_y = im.size
        sc.render.resolution_percentage = 100
        sc.render.filepath = dst
        bpy.ops.render.render(write_still=True, scene=sc.name)
        bpy.data.images.remove(im)
        os.remove(src)


def bake(out, shell, meta=None, samples=96, res=RES):
    """Call after core.finish(). meta is merged into plan.json (title, scale, ...)."""
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH" and o.data.polygons]
    _only(meshes)
    bpy.ops.object.convert(target="MESH")
    unlit = [o for o in meshes if o.get("group") not in res]
    mirrors = []   # [x0, x1, y0, y1, z0, z1] plan inches; the viewer puts a real reflection in front of each
    for o in meshes:
        idx = [i for i, m in enumerate(o.data.materials) if m and m.name.split(".")[0] == "mirror"]
        pts = [o.matrix_world @ o.data.vertices[v].co for p in o.data.polygons if p.material_index in idx for v in p.vertices]
        if pts:
            lo, hi = [min(p[i] for p in pts) / core.IN for i in range(3)], [max(p[i] for p in pts) / core.IN for i in range(3)]
            mirrors.append([lo[0], hi[0], -hi[1], -lo[1], lo[2], hi[2]])
    groups = {g: [o for o in meshes if o.get("group") == g] for g in res}
    joined = {g: _join(g, obs) for g, obs in groups.items() if obs}

    view.gpu()
    c = sc.cycles
    c.samples, c.use_adaptive_sampling, c.max_bounces, c.diffuse_bounces = samples, False, 8, 6
    c.caustics_reflective = c.caustics_refractive = False
    st = sc.render.image_settings
    st.file_format, st.color_depth, st.exr_codec, st.color_mode = "OPEN_EXR", "32", "ZIP", "RGB"
    sc.view_settings.view_transform = "Standard"
    for o in unlit:   # glass would block the daylight; fixture lenses are stood in for by their lamps
        o.hide_render = True
    tmp, pairs = tempfile.mkdtemp(dir=out), []
    t0, level = time.time(), {"day": [], "lamp": []}
    for which in ("day", "lamp"):
        lights.scenario(which)
        for g, ob in joined.items():
            # a smaller map has fewer texels to average over, so it gets the samples a large one would spread out
            c.samples = samples * (max(res.values()) // res[g]) ** 2
            img = bpy.data.images.new("lm_%s_%s" % (g, which), res[g], res[g], alpha=False, float_buffer=True)
            img.colorspace_settings.name = "Non-Color"
            for m in filter(None, ob.data.materials):
                n = m.node_tree.nodes.get("BakeTarget") or m.node_tree.nodes.new("ShaderNodeTexImage")
                n.name, n.image = "BakeTarget", img
                m.node_tree.nodes.active = n
            _only([ob])
            ob.data.uv_layers.active = ob.data.uv_layers["LM"]
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=max(2, res[g] // 680), use_clear=True)
            px = np.empty(res[g] * res[g] * 4, np.float32)
            img.pixels.foreach_get(px)
            lum = px.reshape(-1, 4)[:, :3].mean(axis=1)
            lum = lum[lum > 1e-5]
            if lum.size:
                level[which].append((g, float(np.minimum(lum, np.percentile(lum, 99)).mean()), lum.size))
            raw = os.path.join(tmp, img.name + ".exr")
            img.save_render(raw, scene=sc)
            bpy.data.images.remove(img)
            pairs.append((raw, os.path.join(out, img_name(g, which))))
            print("[bake] %s %s %.0fs" % (g, which, time.time() - t0), flush=True)
    _denoise(pairs)
    os.rmdir(tmp)
    lights.scenario("both")

    for m in bpy.data.materials:
        n = m.node_tree.nodes.get("BakeTarget") if m.use_nodes else None
        if n:
            m.node_tree.nodes.remove(n)
    parts = [p for ob in joined.values() for p in _split_guess(ob)]
    for o in unlit:
        o.hide_render = False
    _only(parts + unlit)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, "model.glb"), export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                              export_image_format="NONE", export_cameras=False, export_lights=False)
    plan = shell.plan()
    plan["fixtures"] = {"%s#%d" % (f[0], i): [f[1], f[3], f[2], f[4], f[5]] for i, f in enumerate(core.FOOTPRINTS)}
    plan["doorSwings"] = []
    plan["lights"], plan["sunDir"] = lights.LAMPS, lights.SUN
    plan["lightmaps"] = {g: res[g] for g in joined}
    plan["materials"] = {m.name: dict(key=m.name.split(".")[0], rgb=list(m["rgb"]), plank=m["plank"]) for m in core.MATS.values()}
    plan["model"] = "model.glb"
    plan["windows"] = [k for k in plan["openings"] if k not in plan["passable"]]
    plan["mirrors"] = mirrors
    # Units differ tenfold in how much daylight and lamp light they hold (window size, number of fixtures), so the
    # viewer's two gains are set per unit to bring the light on the unit's contents to the level unit 487 was tuned at.
    def mean(which):
        v = [x for x in level[which] if x[0] != "A"] or level[which]   # group A includes the sunlit outside faces
        return sum(m * n for _, m, n in v) / max(1, sum(n for _, _, n in v))
    day, lamp = mean("day"), mean("lamp")
    plan["tune"] = dict(dayGain=min(12.0, max(1.5, 0.43 / day)) if day else 3.0, lampGain=min(1.5, max(0.15, 0.19 / lamp)) if lamp else 0.55)
    plan.update(meta or {})
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"))
    print("[bake] wrote", out)


def img_name(group, which):
    return "lm_%s_%s.exr" % (group, which)
