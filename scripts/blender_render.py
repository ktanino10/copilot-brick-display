"""Rendering entry point for a reopened saved native Blender scene."""

import argparse
import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--probe", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
scene = bpy.context.scene
scene.render.threads_mode = "FIXED"
scene.render.threads = 2
scene.frame_set(scene.frame_end)
folder = ROOT / "site/media"
folder.mkdir(parents=True, exist_ok=True)
scene.render.resolution_percentage = 150
scene.render.filepath = str(folder / f"{args.model}-hero.png")
bpy.ops.render.render(write_still=True)
scene.render.resolution_percentage = 100
catalog = json.loads((ROOT / "design/catalog.json").read_text())
model = next(model for model in catalog["models"] if model["id"] == args.model)
w, d, _ = [value * .001 for value in model["actual_mm"]]
original_camera = scene.camera
comparison = bpy.data.objects.new("Common-scale comparison camera", original_camera.data.copy())
scene.collection.objects.link(comparison)
target = Vector((w / 2, d / 2, .1433))
comparison.location = target + Vector((.21, -.54, .255))
comparison.rotation_euler = (target - comparison.location).to_track_quat("-Z", "Y").to_euler()
comparison.data.ortho_scale = .44
scene.camera = comparison
scene.render.filepath = str(folder / f"{args.model}-compare.png")
bpy.ops.render.render(write_still=True)
scene.camera = original_camera
bpy.data.objects.remove(comparison, do_unlink=True)
front = bpy.data.objects.new("Actual base-front detail", original_camera.data.copy())
scene.collection.objects.link(front)
target = Vector((w / 2, 0, .024))
front.location = target + Vector((0, -.6, 0))
front.rotation_euler = (target - front.location).to_track_quat("-Z", "Y").to_euler()
front.data.ortho_scale = w * 1.05
scene.camera = front
scene.render.resolution_x, scene.render.resolution_y = 1600, 480
scene.render.filepath = str(folder / f"{args.model}-base-front.png")
bpy.ops.render.render(write_still=True)
scene.camera = original_camera
bpy.data.objects.remove(front, do_unlink=True)
scene.render.resolution_x, scene.render.resolution_y = 720, 800
if not args.probe:
    frames = ROOT / "build/frames" / args.model
    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.iterdir():
        if old.is_file() and re.fullmatch(r"frame-\d{4}\.png", old.name):
            old.unlink()
    scene.render.filepath = str(frames / "frame-")
    bpy.ops.render.render(animation=True)
