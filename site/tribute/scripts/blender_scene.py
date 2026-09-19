"""Import the audited CAD meshes without remodeling or source-photo textures."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mesh_audit import read_stl
from artifact_metadata import sanitize_blender_metadata, strip_png_text


def linear_color(hex_value):
    rgb = [int(hex_value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb) + (1,)


def material(name, color):
    result = bpy.data.materials.new(name)
    result.diffuse_color = linear_color(color)
    return result


def build_scene():
    catalog_path = ROOT / "catalog.json"
    catalog = json.loads(catalog_path.read_text())
    if not catalog["native_reopened"]:
        raise ValueError("Only a verified native assembly may be rendered")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1
    scene["catalog_sha256"] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    scene["source_units"] = "mm, converted exactly to metres for Blender; never resize print STLs"
    scene["message"] = "\n".join(catalog["message"])
    scene["physical_fit"] = "not tested"
    colors = {key: material(key, value["hex"]) for key, value in catalog["colors"].items()}
    parts = {part["id"]: part for part in catalog["parts"]}
    meshes, objects = {}, {}
    for instance in catalog["instances"]:
        part = parts[instance["part"]]
        if part["id"] not in meshes:
            vertices, faces = read_stl(ROOT / part["mesh"])
            mesh = bpy.data.meshes.new(part["id"])
            mesh.from_pydata([tuple(coordinate * .001 for coordinate in p) for p in vertices], [], faces)
            mesh.materials.append(colors[part["color"]])
            if "optional_color_change_z_mm" in part:
                mesh.materials.append(colors["charcoal"])
                threshold = part["optional_color_change_z_mm"] * .001 + .000001
                for polygon in mesh.polygons:
                    if max(mesh.vertices[v].co.z for v in polygon.vertices) > threshold:
                        polygon.material_index = 1
            mesh.update()
            meshes[part["id"]] = mesh
        obj = bpy.data.objects.new(instance["id"], meshes[part["id"]])
        scene.collection.objects.link(obj)
        obj.location = Vector(instance["position_mm"]) * .001
        obj.rotation_euler = [math.radians(angle) for angle in instance["rotation_deg_xyz"]]
        obj["part_id"] = part["id"]
        obj["assembly_step"] = instance["step"]
        obj["print_stl"] = "../" + part["mesh"]
        objects[instance["id"]] = obj
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -.0004))
    floor = bpy.context.object
    floor.name = "Studio floor - not a printable part"
    floor.data.materials.append(material("Warm neutral stage", "#DCE1E0"))
    camera_data = bpy.data.cameras.new("Assembly camera")
    camera = bpy.data.objects.new("Assembly camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (.235, -.70, .38)
    target = Vector((0, 0, .105))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = .280
    camera_data.clip_start = .001
    camera_data.clip_end = 100
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 1
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.fps = 24
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = math.radians(20)
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.1
    scene.display.shading.curvature_valley_factor = 1.0
    scene.display.shading.show_object_outline = True
    scene.display.shading.object_outline_color = (.12, .15, .18)
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.72, .75, .75)
    scene.display.render_aa = "16"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.filepath = "//finished.png"
    scene.frame_set(1)
    return scene, catalog, objects


STAGES = [
    (1, 1, 24, "STAND", "T01 台座。実物の作業では先に嵌合試験片を確認します。"),
    (2, 25, 60, "BACKBOARD", "T02 背板の仮合わせ。色部品の接着は台座から外し、平らに寝かせて行います。"),
    (3, 61, 116, "GREEN PLATFORM", "T03 緑の足場、T17 薄緑の丸タイル。接着剤はごく少量です。"),
    (4, 117, 174, "CLOTHES AND HANDS", "T04 赤い服、T05 つなぎ、T06 足、T13 手、T18 ボタン。"),
    (5, 175, 210, "CAT SILHOUETTE", "T07 耳・輪郭・ひげは一体の厚い支持付き部品です。"),
    (6, 211, 246, "FACE", "T08 顔と鼻。背面の位置決め穴を合わせます。"),
    (7, 247, 318, "EYES AND MOUSTACHE", "T09 白目、T10 青い虹彩、T11 瞳、T12 口ひげを順に重ねます。"),
    (8, 319, 372, "RED CAP", "T14 帽子、T15 白い丸、T16 M。硬化後に背板を台座へ戻します。"),
    (9, 373, 402, "REMOVABLE DOCK", "MSG-DOCK を共通8mmピッチのスタッドへ。無理押し・接着はしません。"),
    (10, 403, 440, "REPLACEABLE MESSAGE", "MSG-CARD を上から差し込みます。動画の黒文字は任意の手動色替え例です。"),
    (11, 441, 504, "SAME ICON, NEW ADVENTURES", "完成形。実物の保持力・転倒確認は未実施です。印刷・接着硬化時間を表す動画ではありません。")
]


def animate(scene, catalog, objects):
    intervals = {step: (start, end) for step, start, end, _, _ in STAGES}
    for instance in catalog["instances"]:
        obj = objects[instance["id"]]
        start, end = intervals[instance["step"]]
        part = instance["part"]
        if part == "T03":
            end = 82
        elif part == "T17":
            start, end = 84, 110
        elif instance["step"] == 4:
            start, end = (145, 170) if part == "T18" else (117, 142)
        elif part in ("T09", "T10", "T11", "T12"):
            start, end = {"T09": (247, 268), "T10": (270, 290),
                          "T11": (292, 314), "T12": (292, 314)}[part]
        elif part in ("T14", "T15", "T16"):
            start, end = {"T14": (319, 340), "T15": (341, 356), "T16": (357, 372)}[part]
        final = obj.location.copy()
        if instance["id"] == "stand":
            initial = final + Vector((-.10, 0, .03))
        elif instance["id"] == "board":
            initial = final + Vector((0, 0, .15))
        elif instance["id"] in ("message-dock", "message-card"):
            initial = final + Vector((0, 0, .065))
        else:
            initial = final + Vector((0, -.075, 0))
        for field in ("hide_render", "hide_viewport"):
            setattr(obj, field, True)
            obj.keyframe_insert(data_path=field, frame=max(1, start - 1))
            setattr(obj, field, False)
            obj.keyframe_insert(data_path=field, frame=start)
        obj.location = initial
        obj.keyframe_insert(data_path="location", frame=start)
        obj.location = final
        obj.keyframe_insert(data_path="location", frame=end)
    scene.frame_start, scene.frame_end = 1, 504
    for step, start, end, title, description in STAGES:
        scene.timeline_markers.new(f"{step:02d} {title}", frame=start)
    scene["assembly_note"] = "Explainer uses upright viewing pose; glue relief flat per the Japanese guide. Animation time is not print/cure time."
    scene.frame_set(scene.frame_end)
    timeline = [{"step": step, "first_frame": start, "last_frame": end,
                 "title": title, "caption_ja": description}
                for step, start, end, title, description in STAGES]
    (ROOT / "media/animation-timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n")
    def stamp(frame):
        milliseconds = round(frame / scene.render.fps * 1000)
        return f"00:{milliseconds // 60000:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}"
    captions = ["WEBVTT", ""]
    for item in timeline:
        captions += [f"{stamp(item['first_frame']-1)} --> {stamp(item['last_frame'])}",
                     f"{item['step']:02d} {item['caption_ja']}", ""]
    (ROOT / "media/assembly.ja.vtt").write_text("\n".join(captions))


def main():
    (ROOT / "media").mkdir(exist_ok=True)
    scene, catalog, objects = build_scene()
    animate(scene, catalog, objects)
    sanitize_blender_metadata(bpy)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "media/character-assembly.blend"), compress=False)
    bpy.ops.render.render(write_still=True)
    strip_png_text(ROOT / "media/finished.png")
    print(f"BLENDER_STILL_SAVED {len(objects)} CAD instances", flush=True)


if __name__ == "__main__":
    main()
