"""Reopen the delivered .blend, validate its transforms, then render actual keyframes."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def main():
    blend = ROOT / "media/character-assembly.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    scene = bpy.context.scene
    catalog = json.loads((ROOT / "catalog.json").read_text())
    if scene["catalog_sha256"] != hashlib.sha256((ROOT / "catalog.json").read_bytes()).hexdigest():
        raise ValueError("Blender scene does not match the current canonical catalog")
    scene.frame_set(scene.frame_end)
    objects = {obj.name: obj for obj in scene.objects if "part_id" in obj}
    if len(objects) != len(catalog["instances"]):
        raise ValueError("Blender reopened with missing or extra CAD instances")
    for instance in catalog["instances"]:
        obj = objects[instance["id"]]
        expected = Vector(instance["position_mm"]) * .001
        if (obj.location - expected).length > .0000001:
            raise ValueError(f"Blender transform mismatch: {instance['id']}")
        if obj.hide_render or not obj.animation_data or not obj.animation_data.action:
            raise ValueError(f"Missing assembly animation: {instance['id']}")
    bounds = [obj.matrix_world @ Vector(corner) for obj in objects.values() for corner in obj.bound_box]
    sizes = [(max(point[i] for point in bounds) - min(point[i] for point in bounds)) * 1000
             for i in range(3)]
    if any(abs(a - b) > .06 for a, b in zip(sizes, catalog["assembly_size_mm"])):
        raise ValueError(f"Blender size mismatch: {sizes}")
    visible = {}
    for frame in (1, 60, 116, 174, 210, 246, 318, 372, 402, 440, 504):
        scene.frame_set(frame)
        visible[str(frame)] = sum(not obj.hide_render for obj in objects.values())
    if visible["1"] >= visible["440"] or visible["440"] != len(objects):
        raise ValueError("Assembly visibility does not progress to all parts")
    report = {"status": "pass", "blender_version": bpy.app.version_string, "native_reopened": True,
              "instances": len(objects), "assembly_size_mm": sizes, "frame_count": scene.frame_end,
              "fps": scene.render.fps, "visible_part_counts": visible,
              "blend_sha256": hashlib.sha256(blend.read_bytes()).hexdigest(),
              "catalog_sha256": scene["catalog_sha256"], "render_engine": scene.render.engine}
    (ROOT / "validation/blender.json").write_text(json.dumps(report, indent=2) + "\n")
    if "--verify-only" in sys.argv:
        print("BLENDER_REOPEN_PASS", flush=True)
        return
    folder = ROOT / "media/frames"
    folder.mkdir(exist_ok=True)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 1
    scene.display.render_aa = "8"
    scene.render.filepath = str(folder / "frame_")
    bpy.ops.render.render(animation=True)
    print("BLENDER_ANIMATION_RENDER_PASS", flush=True)


if __name__ == "__main__":
    main()
