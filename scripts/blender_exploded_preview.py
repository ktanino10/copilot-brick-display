"""Render the real native meshes at the exact viewer offsets; no printable geometry changes."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--model", choices=["A", "B", "C"], required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
states = json.loads((ROOT / "build/display-states.json").read_text())
scene = bpy.context.scene
scene.frame_set(scene.frame_end)
for obj in bpy.data.objects:
    if "instance_id" in obj:
        obj.animation_data_clear()
        obj.hide_render = False
        obj.hide_viewport = False
scene.render.resolution_x, scene.render.resolution_y = 1100, 1400
scene.render.resolution_percentage = 100
scene.render.use_stamp = False
scene.render.use_stamp_filename = False
scene.render.threads_mode, scene.render.threads = "FIXED", 2
camera = bpy.data.objects.new("Vertical explosion preview", bpy.data.cameras.new("Vertical explosion preview"))
scene.collection.objects.link(camera)
camera.data.type = "ORTHO"
camera.data.clip_start, camera.data.clip_end = .001, 20
scene.camera = camera
output = ROOT / "build/front-base-preview"
output.mkdir(parents=True, exist_ok=True)
for state in states:
    if state["model"] != args.model:
        continue
    for obj in bpy.data.objects:
        if "instance_id" in obj:
            obj.location = Vector([(a + b) / 1000 for a, b in
                                   zip(obj["final_position_mm"], state["offsets"][obj["instance_id"]])])
    low, high = [Vector([v / 1000 for v in xyz]) for xyz in state["bounds"]]
    target = (low + high) / 2
    extent = high - low
    camera.location = target + Vector((.20, -1.4, .25))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = max(extent.z * 1.22, extent.x * 1.35)
    scene.render.filepath = str(output / f"{args.model}-vertical-{state['percent']:03}.png")
    bpy.ops.render.render(write_still=True)
print("RENDERED_VIEWER_POSES", args.model)
