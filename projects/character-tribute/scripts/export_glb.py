"""Create a standard, static glTF preview from the verified native Blender assembly."""
import hashlib
import json
from pathlib import Path
import struct

import bpy

ROOT = Path(__file__).resolve().parents[1]


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / "media/character-assembly.blend"), load_ui=False)
    bpy.context.scene.frame_set(bpy.context.scene.frame_end)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if "part_id" in obj:
            obj.select_set(True)
    path = ROOT / "media/model.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                             export_animations=False, export_current_frame=True,
                             export_extras=True, export_yup=True)
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    if (magic, version, length) != (b"glTF", 2, len(data)):
        raise ValueError("Invalid exported GLB container")
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON":
        raise ValueError("Missing GLB scene description")
    model = json.loads(data[20:20+chunk_length])
    nodes = [node for node in model["nodes"] if "mesh" in node]
    catalog = json.loads((ROOT / "catalog.json").read_text())
    expected = {item["id"]: item["part"] for item in catalog["instances"]}
    actual = {node["name"]: node.get("extras", {}).get("part_id") for node in nodes}
    if actual != expected:
        raise ValueError("GLB part IDs or instances differ from the canonical assembly")
    by_name = {node["name"]: node for node in nodes}
    for instance in catalog["instances"]:
        x, y, z = instance["position_mm"]
        expected_position = [x*.001, z*.001, -y*.001]
        position = by_name[instance["id"]].get("translation", [0, 0, 0])
        if any(abs(a-b) > 1e-7 for a, b in zip(position, expected_position)):
            raise ValueError(f"GLB captured the wrong animation pose: {instance['id']}")
    report = {"status": "pass", "format": "glTF 2.0 binary", "units": "m", "up_axis": "+Y",
              "instances": len(nodes), "meshes": len(model["meshes"]),
              "sha256": hashlib.sha256(data).hexdigest(), "embedded_buffers": True,
              "note": "Static display preview; print the mm STL masters, not the glTF."}
    (ROOT / "validation/glb.json").write_text(json.dumps(report, indent=2) + "\n")
    print("GLB_EXPORT_PASS", len(nodes), "instances")


if __name__ == "__main__":
    main()
