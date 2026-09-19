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
    scene.name = "Assembly"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1
    scene["catalog_sha256"] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    scene["source_units"] = "mm, converted exactly to metres for Blender; never resize print STLs"
    scene["message"] = "\n".join(catalog["message"])
    scene["physical_fit"] = "not tested"
    scene["revision"] = catalog["revision"]
    scene["manufacturing_revision"] = catalog["manufacturing_revision"]
    scene["adhesive_required"] = False
    scene["all_parts_removable"] = True
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
        obj["instance_id"] = instance["id"]
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
    (1,1,36,"CAPTURE FRAME","T2 無接着。実作業は前面を下にして支持台へ。まず粗ねじ・捕捉試験片を確認します。"),
    (2,37,180,"REAR-LOADED INSERTS","前枠の後ろから色インサートを入れます。背面フランジが前方への抜けを止めます。"),
    (3,181,212,"WHITE DETAIL CASSETTES","白目と帽子の白い丸を背面から差し込みます。"),
    (4,213,244,"IRISES AND M","青い虹彩とMを背面から。小部品もフランジで捕捉する構造です。"),
    (5,245,272,"REMOVABLE PUPILS","瞳を最後に差し込みます。小部品にも接着剤は使いません。"),
    (6,273,312,"REMOVABLE BACK COVER","裏蓋の段差が各フランジを後ろから支持し、後方への抜けを止めます。"),
    (7,313,384,"PRINTED COARSE SCREWS","交換可能な印刷粗ねじ4本を手で締めます。ねじは回転と送りを対応させます。"),
    (8,385,440,"STAND","閉じたレリーフを台座へ。動画は説明用姿勢で、実際の重力・作業速度の再現ではありません。"),
    (9,441,464,"COMMON DOCK","共通8mmピッチのドックを装着。無理押ししません。"),
    (10,465,496,"REMOVABLE MESSAGE","固定の交換カードを差し込みます。黒文字は任意の手動色替え表示例です。"),
    (11,497,576,"T2 COMPLETE","全パーツ無接着・取り外し可能な設計候補。実物保持・ねじ耐久・転倒は試作待ちです。")
]


def apply_track(obj, records):
    for frame, position, spin, hidden in sorted(records):
        obj.location = position
        obj.rotation_euler.y = spin
        obj.keyframe_insert(data_path="location",frame=frame)
        obj.keyframe_insert(data_path="rotation_euler",index=1,frame=frame)
        for field in ("hide_render","hide_viewport"):
            setattr(obj,field,hidden)
            obj.keyframe_insert(data_path=field,frame=frame)


def write_captions(name, stages, fps):
    timeline = [{"step":step,"first_frame":start,"last_frame":end,"title":title,"caption_ja":caption}
                for step,start,end,title,caption in stages]
    (ROOT/f"media/{name}-timeline.json").write_text(json.dumps(timeline,ensure_ascii=False,indent=2)+"\n")
    def stamp(frame):
        ms=round(frame/fps*1000)
        return f"00:{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}"
    lines=["WEBVTT",""]
    for item in timeline:
        lines += [f"{stamp(item['first_frame']-1)} --> {stamp(item['last_frame'])}",
                  f"{item['step']:02d} {item['caption_ja']}",""]
    (ROOT/f"media/{name}.ja.vtt").write_text("\n".join(lines))
    return timeline


def disassembly_scene(source, objects, tracks, camera_track, catalog):
    scene=bpy.data.scenes.new("Disassembly")
    scene.world=source.world
    scene.unit_settings.system="METRIC"
    scene.unit_settings.length_unit="MILLIMETERS"
    for key in ("engine","threads_mode","threads","resolution_x","resolution_y","resolution_percentage","fps","film_transparent"):
        setattr(scene.render,key,getattr(source.render,key))
    scene.render.image_settings.file_format="PNG"
    scene.render.filepath="//disassembly.png"
    for key in ("light","studiolight_rotate_z","color_type","show_shadows","show_cavity","cavity_type",
                "curvature_ridge_factor","curvature_valley_factor","show_object_outline","object_outline_color","background_type"):
        setattr(scene.display.shading,key,getattr(source.display.shading,key))
    scene.display.render_aa=source.display.render_aa
    for key in ("view_transform","look","exposure","gamma"):
        setattr(scene.view_settings,key,getattr(source.view_settings,key))
    for key in source.keys():
        scene[key]=source[key]
    scene.frame_start,scene.frame_end=1,source.frame_end
    for original in source.objects:
        obj=original.copy()
        obj.animation_data_clear()
        obj.name="disassembly__"+original.name
        scene.collection.objects.link(obj)
        if original.type=="CAMERA":
            scene.camera=obj
            obj.data=original.data.copy()
            obj.data.animation_data_clear()
            for frame,position,rotation,scale in camera_track:
                obj.location=position
                obj.rotation_euler=rotation
                obj.data.ortho_scale=scale
                obj.keyframe_insert(data_path="location",frame=source.frame_end-frame+1)
                obj.keyframe_insert(data_path="rotation_euler",frame=source.frame_end-frame+1)
                obj.data.keyframe_insert(data_path="ortho_scale",frame=source.frame_end-frame+1)
        elif original.name in tracks:
            reversed_track=[(source.frame_end-frame+1,pos,spin,hidden)
                            for frame,pos,spin,hidden in tracks[original.name]]
            item=next(i for i in catalog["instances"] if i["id"]==original.name)
            if "front_stop" in item:
                ordered=sorted(reversed_track)
                for a,b in zip(ordered,ordered[1:]):
                    if not a[3] and not b[3] and b[1].y-a[1].y>.01:
                        initial_push=a[1]+Vector((0,item["max_tool_push_mm"]*.001,0))
                        reversed_track += [(a[0]+6,initial_push,0,False),
                                           (a[0]+10,initial_push,0,False)]
                        obj["max_initial_push_mm"]=item["max_tool_push_mm"]
                        obj["initial_push_hold_frames"]=[a[0]+6,a[0]+10]
                        break
            apply_track(obj,reversed_track)
    captions=[
        "分解は支持できる場所で。まずカードとドックを取り外します。",
        "カードを上へ抜きます。",
        "ドックを外します。無理にこじりません。",
        "閉じたレリーフを台座から持ち上げ、支持台と受け皿を用意します。",
        "背面から見て反時計回りに4本を外します。ねじは同じ部品へ交換できます。",
        "裏蓋を後ろへ外します。色部品をこぼさないよう支持します。",
        "瞳：工具の初期押出は最大3.5mmで停止。次に背面フランジを指でつかみ、残りを引き抜きます。",
        "虹彩とM：3.5mmの初期押出で工具を止め、フランジを引きます。工具で最後まで押しません。",
        "白目と白い丸も初期押出→停止→背面フランジの引抜き。強い力は使いません。",
        "色インサートも最大3.5mmの初期押出後、受け皿の上でフランジを指で引き抜きます。",
        "再組立はAssemblyシーンと手順書の順序へ。不可逆な固定は行いません。"]
    stages=[]
    for index,(step,start,end,title,_) in enumerate(reversed(STAGES),1):
        stages.append((index,source.frame_end-end+1,source.frame_end-start+1,"REMOVE "+title,captions[index-1]))
    for step,start,end,title,caption in stages:
        scene.timeline_markers.new(f"{step:02d} {title}",frame=start)
    write_captions("disassembly",stages,scene.render.fps)
    scene.frame_set(1)
    return scene


def animate(scene, catalog, objects):
    intervals = {step: (start, end) for step, start, end, _, _ in STAGES}
    tracks={}
    tile_number=0
    for instance in catalog["instances"]:
        obj = objects[instance["id"]]
        start, end = intervals[instance["step"]]
        if instance["step"]==2:
            start=37+tile_number*2
            end=start+20
            tile_number+=1
        final = obj.location.copy()
        early=final+Vector((0,0,.05)) if instance["step"]<=7 else final.copy()
        spin=0
        if instance["id"] == "stand":
            end=408
            initial = final + Vector((-.10, 0, .03))
        elif instance["id"] in ("message-dock", "message-card"):
            initial = final + Vector((0, 0, .065))
        elif instance.get("motion")=="helical":
            initial=early+Vector((0,.0128,0))
            spin=math.radians(360*12.8/instance["pitch_mm"])
        else:
            initial=early+Vector((0,.065,0))
        values={1:(initial,spin,True),max(1,start-1):(initial,spin,True),
                start:(initial,spin,False),end:(early,0,False)}
        if instance["step"]<=7:
            values[408]=(early,0,False)
            values[440]=(final,0,False)
        values[576]=(final,0,False)
        records=[(frame,*value) for frame,value in sorted(values.items())]
        apply_track(obj,records)
        tracks[instance["id"]]=records
    scene.frame_start, scene.frame_end = 1, 576
    for step, start, end, title, description in STAGES:
        scene.timeline_markers.new(f"{step:02d} {title}", frame=start)
    scene["assembly_note"] = "Fully removable T2. Upright explanatory viewing pose; build front-down on printed rests. Animation time is not manufacturing time."
    target=Vector((0,0,.135))
    camera_track=[]
    for frame,position,scale in [(1,(.235,.70,.38),.34),(408,(.235,.70,.38),.34),
                                  (496,(.235,-.70,.38),.28),(576,(.235,-.70,.38),.28)]:
        point=Vector(position)
        aim=target if frame<=408 else Vector((0,0,.105))
        rotation=(aim-point).to_track_quat("-Z","Y").to_euler()
        scene.camera.location=point
        scene.camera.rotation_euler=rotation
        scene.camera.data.ortho_scale=scale
        scene.camera.keyframe_insert(data_path="location",frame=frame)
        scene.camera.keyframe_insert(data_path="rotation_euler",frame=frame)
        scene.camera.data.keyframe_insert(data_path="ortho_scale",frame=frame)
        camera_track.append((frame,point.copy(),rotation.copy(),scale))
    scene.frame_set(scene.frame_end)
    timeline=write_captions("assembly",STAGES,scene.render.fps)
    (ROOT / "media/animation-timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n")
    disassembly_scene(scene,objects,tracks,camera_track,catalog)
    bpy.context.window.scene=scene
    scene.frame_set(scene.frame_end)


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
