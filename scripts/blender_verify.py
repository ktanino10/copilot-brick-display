"""Run in a freshly reopened .blend; verify all actual mesh bounds and transforms."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    model = next(m for m in catalog["models"] if m["id"] == args.model)
    scene = bpy.context.scene
    assert scene["parameters_sha256"] == catalog["parameters_sha256"]
    assert scene.unit_settings.system == "METRIC"
    scene.frame_set(scene.frame_end)
    bpy.context.view_layer.update()
    objects = {obj["instance_id"]: obj for obj in bpy.data.objects if "instance_id" in obj}
    assert set(objects) == {item["id"] for item in model["placements"]}
    used_meshes = {obj.data for obj in objects.values()}
    assert set(bpy.data.meshes) == used_meshes, "Unexpected orphan or hidden mesh data in the public native scene."
    allowed_hashes = {catalog["parts"][item["part"]]["sha256"] for item in model["placements"]}
    assert all(mesh.get("source_stl_sha256") in allowed_hashes for mesh in used_meshes)
    for item in model["placements"]:
        obj = objects[item["id"]]
        assert obj["part_id"] == item["part"] and obj["color_name"] == item["color"]
        assert obj["assembly_step"] == item["step"] and not obj.hide_render
        assert obj.data["source_stl_sha256"] == catalog["parts"][item["part"]]["sha256"]
        for actual, mm in zip(obj.location, item["position"]):
            assert abs(actual * 1000 - mm) < 0.001
        for actual, degrees in zip(obj.rotation_euler, item["rotation"]):
            assert abs(math.degrees(actual) - degrees) < 0.001
        coordinates = [tuple(v.co) for v in obj.data.vertices]
        bounds = [[min(v[axis] for v in coordinates) * 1000 for axis in range(3)],
                  [max(v[axis] for v in coordinates) * 1000 for axis in range(3)]]
        assert max(abs(a - b) for left, right in zip(bounds, catalog["parts"][item["part"]]["bounds"])
                   for a, b in zip(left, right)) < 0.031
    scene.frame_set(1)
    assert all(obj.hide_render for obj in objects.values()), "Not an assembly sequence"
    for step in model["steps"]:
        frame = 2 + (step["number"] - 1) * 8 + 5
        scene.frame_set(frame)
        actual = {key for key, obj in objects.items() if not obj.hide_render}
        expected = {item["id"] for item in model["placements"] if item["step"] <= step["number"]}
        assert actual == expected, f"Wrong assembly stage {step['number']}"
    output = ROOT / "validation" / f"blender-{args.model}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "model": args.model, "status": "PASS_NATIVE_REOPEN",
        "blender_version": bpy.app.version_string,
        "instances": len(objects), "assembly_stages": len(model["steps"]),
        "frames": scene.frame_end, "fps": scene.render.fps,
        "parameters_sha256": catalog["parameters_sha256"],
        "native_sha256": hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
        "geometry": "same delivered STL; local bounds, units, IDs, colors and final transforms checked",
        "no_orphan_or_hidden_mesh_data": True,
        "animation": "all numbered stages checked after fresh native reopen",
        "physics": "not simulated; physical fit and stability untested",
    }, indent=2) + "\n")
    print(f"PASS_NATIVE_REOPEN {args.model} {len(objects)} objects; all stages agree")


if __name__ == "__main__":
    main()
