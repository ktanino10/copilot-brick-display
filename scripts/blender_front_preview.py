"""Actual native-scene front and base-front close-up renders for the placement revision."""

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--label", default="new")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
scene = bpy.context.scene
scene.frame_set(scene.frame_end)
bpy.context.view_layer.update()
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.threads_mode = "FIXED"
scene.render.threads = 2
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.use_stamp = False
scene.render.use_stamp_filename = False
scene.display.render_aa = "16"
camera = bpy.data.objects.new("Front placement preview", bpy.data.cameras.new("Front placement preview"))
scene.collection.objects.link(camera)
camera.data.type = "ORTHO"
camera.data.clip_start = .001
camera.data.clip_end = 10
scene.camera = camera
output = ROOT / "build/front-base-preview"
output.mkdir(parents=True, exist_ok=True)
for name, center, scale, size in [
    ("front", (.096, 0, .1193), .265, (1100, 1200)),
    ("iso", (.096, .04, .1193), .30, (1200, 1200)),
    ("base", (.096, 0, .024), .202, (1600, 450)),
]:
    target = Vector(center)
    camera.location = target + (Vector((.2, -.5, .22)) if name == "iso" else Vector((0, -.5, 0)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = scale
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = str(output / f"B-{args.label}-{name}.png")
    bpy.ops.render.render(write_still=True)
print("RENDERED_NATIVE_FRONT", args.label)
