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
target = Vector((w / 2, d / 2, .124))
comparison.location = target + Vector((.21, -.54, .255))
comparison.rotation_euler = (target - comparison.location).to_track_quat("-Z", "Y").to_euler()
comparison.data.ortho_scale = .38
scene.camera = comparison
scene.render.filepath = str(folder / f"{args.model}-compare.png")
bpy.ops.render.render(write_still=True)
scene.camera = original_camera
bpy.data.objects.remove(comparison, do_unlink=True)
if not args.probe:
    frames = ROOT / "build/frames" / args.model
    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.iterdir():
        if old.is_file() and re.fullmatch(r"frame-\d{4}\.png", old.name):
            old.unlink()
    scene.render.filepath = str(frames / "frame-")
    bpy.ops.render.render(animation=True)
