"""Replace only the plaque mesh in an existing genuine scene, preserving animation and all other meshes."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_scene import mesh_from_stl, material

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", choices=["A", "B", "C"], required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
catalog = json.loads((ROOT / "design/catalog.json").read_text())
model = next(m for m in catalog["models"] if m["id"] == args.model)
objects = {obj["instance_id"]: obj for obj in bpy.data.objects if "instance_id" in obj}
assert set(objects) == {item["id"] for item in model["placements"]}
part_id = f"NP3-TEXT-{args.model}"
target = next(obj for obj in objects.values() if obj["part_id"] == part_id)
preserved = {}
for item in model["placements"]:
    obj = objects[item["id"]]
    if item["part"] != part_id:
        assert obj.data["source_stl_sha256"] == catalog["parts"][item["part"]]["sha256"]
        preserved[item["part"]] = obj.data["source_stl_sha256"]
colors = {key: material("Plaque revision / " + key, value["hex"]) for key, value in catalog["colors"].items()}
target.data = mesh_from_stl(catalog["parts"][part_id], colors, ROOT / "site/downloads")
bpy.context.scene["parameters_sha256"] = catalog["parameters_sha256"]
bpy.context.scene["plaque_only_revision"] = catalog["revision"]
bpy.context.scene["unchanged_meshes_reused"] = sorted(preserved)
for mesh in list(bpy.data.meshes):
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
scene = bpy.context.scene
scene.frame_set(scene.frame_end)
scene.render.filepath = "//frames/"
bpy.context.preferences.filepaths.save_version = 0
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type == "FILE_BROWSER" and space.params:
                space.params.directory = b"//"
output = ROOT / "site/downloads" / args.model / f"{args.model}.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False, compress=False)
print("SAVED_PLAQUE_ONLY_NATIVE", args.model, part_id, len(preserved), "unchanged masters; no body or camera regenerated")
