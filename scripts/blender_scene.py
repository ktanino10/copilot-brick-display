"""Create and save actual Blender scenes from the delivered millimetre STL meshes."""

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SCALE = 0.001


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["A", "B", "C"], required=True)
    parser.add_argument("--reuse-scene", action="store_true")
    parser.add_argument("--catalog", type=Path, default=ROOT / "design/catalog.json")
    parser.add_argument("--downloads", type=Path, default=ROOT / "site/downloads")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def mesh_from_stl(part, colors, downloads):
    data = (downloads / part["stl"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == part["sha256"]
    count = struct.unpack_from("<I", data, 80)[0]
    vertices, faces, lookup = [], [], {}
    for face in range(count):
        values = struct.unpack_from("<12fH", data, 84 + 50 * face)
        triangle = []
        for vertex in range(3):
            point = tuple(values[3 + 3 * vertex:6 + 3 * vertex])
            if point not in lookup:
                lookup[point] = len(vertices)
                vertices.append(tuple(value * SCALE for value in point))
            triangle.append(lookup[point])
        faces.append(triangle)
    mesh = bpy.data.meshes.new(part["id"])
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh["source_stl_sha256"] = part["sha256"]
    mesh["source_units"] = "mm"
    mesh["conversion_to_metres"] = SCALE
    mesh.materials.append(colors["black"])
    if part["kind"] in ("front_plaque", "front_logo"):
        mesh.materials.append(colors[part["letter_color"]])
        for polygon in mesh.polygons:
            if polygon.center.z > (part["optional_color_change_z"] + .001) * SCALE:
                polygon.material_index = 1
    return mesh


def material(name, hex_value):
    mat = bpy.data.materials.new(name)
    rgb = tuple(int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mat.diffuse_color = (*rgb, 1)
    mat.roughness = 0.4
    return mat


def point_camera(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def key_visibility(obj, start):
    obj.hide_render = True
    obj.hide_viewport = True
    obj.keyframe_insert("hide_render", frame=1)
    obj.keyframe_insert("hide_viewport", frame=1)
    obj.hide_render = False
    obj.hide_viewport = False
    obj.keyframe_insert("hide_render", frame=start)
    obj.keyframe_insert("hide_viewport", frame=start)


def main():
    args = arguments()
    catalog = json.loads(args.catalog.read_text())
    model = next(m for m in catalog["models"] if m["id"] == args.model)
    previous_meshes = {mesh.name: mesh for mesh in bpy.data.meshes
                       if mesh.get("source_stl_sha256")} if args.reuse_scene else {}
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x = 720
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.fps = 20
    scene.render.film_transparent = False
    scene.render.use_stamp = False
    scene.render.use_stamp_filename = False
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_shadows = True
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = 1.4
    shading.curvature_valley_factor = 1.1
    shading.show_specular_highlight = True
    shading.background_type = "WORLD"
    scene.world.color = (0.84, 0.9, 0.96)
    scene.view_settings.view_transform = "Standard"
    scene["model_id"] = args.model
    scene["parameters_sha256"] = catalog["parameters_sha256"]
    scene["source_catalog"] = "design/catalog.json"
    scene["physical_simulation"] = False
    scene["color_finish"] = "Black message / logo modules; manual white filament change at each part's documented layer."
    scene["assembly_step_frames"] = 8
    colors = {key: material(key, spec["hex"]) for key, spec in catalog["colors"].items()}
    collection = bpy.data.collections.new(f"CAD / {args.model}")
    scene.collection.children.link(collection)
    cache = {key: mesh for key, mesh in previous_meshes.items()
             if key in catalog["parts"] and mesh["source_stl_sha256"] == catalog["parts"][key]["sha256"]}
    scene["unchanged_meshes_reused"] = sorted(cache)
    for item in model["placements"]:
        key = item["part"]
        if key not in cache:
            cache[key] = mesh_from_stl(catalog["parts"][key], colors, args.downloads)
        obj = bpy.data.objects.new(item["id"], cache[key])
        collection.objects.link(obj)
        obj["instance_id"] = item["id"]
        obj["part_id"] = key
        obj["color_name"] = item["color"]
        obj["assembly_step"] = item["step"]
        obj["final_position_mm"] = item["position"]
        obj["final_rotation_degrees"] = item["rotation"]
        obj.rotation_euler = [math.radians(v) for v in item["rotation"]]
        if catalog["parts"][key]["kind"] not in ("front_plaque", "front_logo"):
            obj.material_slots[0].link = "OBJECT"
            obj.material_slots[0].material = colors[item["color"]]
        position = Vector(tuple(v * SCALE for v in item["position"]))
        start = 2 + (item["step"] - 1) * 8
        key_visibility(obj, start)
        lift = .046 if item.get("role") == "front_module" else .035
        obj.location = position + Vector((0, 0, lift))
        obj.keyframe_insert("location", frame=start)
        obj.location = position
        obj.keyframe_insert("location", frame=start + 5)
    finish = 2 + len(model["steps"]) * 8
    scene["assembly_complete_frame"] = finish
    scene.frame_start = 1
    scene.frame_end = finish + 100

    w, d, h = (v * SCALE for v in model["actual_mm"])
    center = Vector((w / 2, d / 2, h * 0.48))
    camera_data = bpy.data.cameras.new("Presentation camera")
    camera = bpy.data.objects.new("Presentation camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = center + Vector((h * 0.7, -h * 1.8, h * 0.85))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(h * 1.44, w * 1.5)
    camera_data.clip_start = 0.001
    camera_data.clip_end = 20
    point_camera(camera, center)
    orbit = bpy.data.objects.new("Completed-object turntable camera", None)
    scene.collection.objects.link(orbit)
    orbit.location = center
    bpy.context.view_layer.update()
    camera.parent = orbit
    camera.matrix_parent_inverse = orbit.matrix_world.inverted()
    orbit.rotation_euler.z = 0
    orbit.keyframe_insert("rotation_euler", frame=finish + 20)
    orbit.rotation_euler.z = 2 * math.pi
    orbit.keyframe_insert("rotation_euler", frame=scene.frame_end)
    scene.frame_set(scene.frame_end)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    # A saved native scene always opens on the complete model, not the empty first frame.
    scene.render.filepath = "//frames/"
    bpy.context.preferences.filepaths.save_version = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "FILE_BROWSER" and space.params:
                    space.params.directory = b"//"
    output = args.downloads / args.model / f"{args.model}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False, compress=False)
    print(f"SAVED_NATIVE {args.model} {len(model['placements'])} instances {scene.frame_end} frames")


if __name__ == "__main__":
    main()
