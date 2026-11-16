"""Check renders. Every view goes through here so lens, sampling and colour are the same in each one.
Eye and target are plan inches (x, y, z)."""
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

from .core import TO_BLENDER

QUALITY = {"preview": ((960, 600), 48, 0.06), "final": ((1920, 1200), 320, 0.01)}


def gpu():
    """Uses the GPU when there is one (Metal on a Mac, OptiX or CUDA on a server); otherwise Cycles stays on CPU."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in (("METAL",) if sys.platform == "darwin" else ("OPTIX", "CUDA")):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = "GPU"
                return kind
        except Exception:
            pass
    sc.cycles.device = "CPU"
    return "CPU"


def hide_ceiling(hide=True):
    c = bpy.data.collections.get("ceiling")
    if c:
        c.hide_render = hide


def shot(name, eye, target, out_dir, quality="preview", exposure=0.7, fov=90.0, ortho=None, up=(0, -1, 0)):
    """ortho: frame width in inches for a straight-down plan view; `up` is then the plan direction at the top of the
    image (default: the top of the drawing)."""
    res, samples, threshold = QUALITY[quality]
    sc = bpy.context.scene
    gpu()
    c = sc.cycles
    c.samples, c.use_adaptive_sampling, c.adaptive_threshold, c.use_denoising = samples, True, threshold, True
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.transparent_max_bounces = 8, 6, 4, 8, 8
    c.sample_clamp_indirect, c.caustics_reflective, c.caustics_refractive = 10.0, False, False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = exposure
    sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGB"
    cam = bpy.data.cameras.new("shot")
    cam.sensor_fit, cam.clip_start, cam.clip_end = "HORIZONTAL", 0.03, 1000.0
    if ortho:
        cam.type, cam.ortho_scale = "ORTHO", ortho * 0.0254
    else:
        cam.angle = math.radians(fov)
    ob = bpy.data.objects.new("shot", cam)
    sc.collection.objects.link(ob)
    e, t = TO_BLENDER @ Vector(eye), TO_BLENDER @ Vector(target)
    f = (t - e).normalized()
    r = f.cross(Vector((0, 0, 1)) if not ortho else (TO_BLENDER.to_3x3() @ Vector(up)).normalized())
    r.normalize()
    ob.matrix_world = Matrix.Translation(e) @ Matrix((r, r.cross(f), -f)).transposed().to_4x4()
    sc.camera = ob
    os.makedirs(out_dir, exist_ok=True)
    sc.render.filepath = os.path.abspath(os.path.join(out_dir, name + ".png"))
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print("[view] %s in %.1fs -> %s" % (name, time.time() - t0, sc.render.filepath))
    bpy.data.objects.remove(ob)
    bpy.data.cameras.remove(cam)
    return sc.render.filepath


def plan_shot(shell, out_dir, name="plan"):
    """Top view of the whole unit with the ceiling off, framed to the walls, north up as on the drawing."""
    x0, x1 = min(w["x0"] for w in shell.walls), max(w["x1"] for w in shell.walls)
    y0, y1 = min(w["y0"] for w in shell.walls), max(w["y1"] for w in shell.walls)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hide_ceiling(True)
    shot(name, (cx, cy, 400), (cx, cy, 0), out_dir, ortho=max(x1 - x0, (y1 - y0) * 1.6) * 1.06, exposure=0)
    hide_ceiling(False)
