"""Reopen the delivered .blend, validate its transforms, then render actual keyframes."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def main():
    blend = ROOT / "media/character-assembly.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    catalog = json.loads((ROOT / "catalog.json").read_text())
    digest=hashlib.sha256((ROOT/"catalog.json").read_bytes()).hexdigest()
    scenes={}
    for name in ("Assembly","Disassembly"):
        scene=bpy.data.scenes[name]
        bpy.context.window.scene=scene
        if scene["catalog_sha256"] != digest:
            raise ValueError("Blender scene does not match the current canonical catalog")
        scene.frame_set(scene.frame_end if name=="Assembly" else 1)
        bpy.context.view_layer.update()
        objects={obj["instance_id"]:obj for obj in scene.objects if "part_id" in obj}
        if len(objects)!=len(catalog["instances"]):
            raise ValueError("Blender reopened with missing or extra CAD instances")
        for instance in catalog["instances"]:
            obj=objects[instance["id"]]
            if (obj.location-Vector(instance["position_mm"])*.001).length>1e-7:
                raise ValueError(f"{name} completed-pose mismatch: {instance['id']}")
            if obj.hide_render or not obj.animation_data or not obj.animation_data.action:
                raise ValueError(f"Missing keyed motion: {instance['id']}")
        bounds=[obj.matrix_world@Vector(corner) for obj in objects.values() for corner in obj.bound_box]
        sizes=[(max(p[i] for p in bounds)-min(p[i] for p in bounds))*1000 for i in range(3)]
        if any(abs(a-b)>.06 for a,b in zip(sizes,catalog["assembly_size_mm"])):
            raise ValueError(f"Blender bounds mismatch in {name}: {sizes}")
        visible={}
        for frame in (1,36,180,212,244,272,312,384,440,496,576):
            scene.frame_set(frame)
            visible[str(frame)]=sum(not obj.hide_render for obj in objects.values())
        if name=="Assembly" and (visible["1"]!=1 or visible["576"]!=len(objects)):
            raise ValueError("Assembly does not build to all parts")
        if name=="Disassembly" and (visible["1"]!=len(objects) or visible["576"]!=1):
            raise ValueError("Disassembly does not release every part from the empty frame")
        for frame in (320,340,360,380):
            scene.frame_set(frame if name=="Assembly" else scene.frame_end-frame+1)
            for instance in catalog["instances"]:
                if instance.get("motion")!="helical":
                    continue
                obj=objects[instance["id"]]
                advance=(obj.location.y-instance["position_mm"][1]*.001)*1000
                expected=math.degrees(obj.rotation_euler.y)*instance["pitch_mm"]/360
                if abs(advance-expected)>.001:
                    raise ValueError(f"Animated screw motion lost its pitch relation: {name}/{instance['id']}")
        initial_pushes=0
        if name=="Disassembly":
            for instance in catalog["instances"]:
                if "front_stop" not in instance:
                    continue
                obj=objects[instance["id"]]
                if obj.get("max_initial_push_mm")!=3.5 or "initial_push_hold_frames" not in obj:
                    raise ValueError(f"Missing limited initial-push stage: {instance['id']}")
                first,last=obj["initial_push_hold_frames"]
                for frame in (first,(first+last)//2,last):
                    scene.frame_set(frame)
                    advance=(obj.location.y-instance["position_mm"][1]*.001)*1000
                    if abs(advance-3.5)>.002:
                        raise ValueError(f"Initial push exceeds or misses 3.5mm: {instance['id']}")
                initial_pushes+=1
        scenes[name]={"instances":len(objects),"assembly_size_mm":sizes,"frame_count":scene.frame_end,
                      "fps":scene.render.fps,"visible_part_counts":visible,"helical_motion_relation_verified":True,
                      "verified_3_5_mm_initial_push_holds":initial_pushes}
    report = {"status": "pass", "revision":"T2","blender_version": bpy.app.version_string, "native_reopened": True,
              "instances":len(catalog["instances"]),"assembly_size_mm":scenes["Assembly"]["assembly_size_mm"],
              "frame_count":scenes["Assembly"]["frame_count"],"fps":scenes["Assembly"]["fps"],
              "scenes":scenes,
              "blend_sha256": hashlib.sha256(blend.read_bytes()).hexdigest(),
              "catalog_sha256": digest, "render_engine": scene.render.engine}
    (ROOT / "validation/blender.json").write_text(json.dumps(report, indent=2) + "\n")
    if "--verify-only" in sys.argv:
        print("BLENDER_REOPEN_PASS", flush=True)
        return
    for name in scenes:
        scene=bpy.data.scenes[name]
        bpy.context.window.scene=scene
        folder = ROOT / "media/frames" / name.lower()
        folder.mkdir(parents=True,exist_ok=True)
        scene.render.resolution_x = 640
        scene.render.resolution_y = 640
        scene.render.threads_mode = "FIXED"
        scene.render.threads = 1
        scene.display.render_aa = "8"
        scene.render.filepath = str(folder / "frame_")
        bpy.ops.render.render(animation=True,scene=name)
    print("BLENDER_ANIMATION_RENDER_PASS", flush=True)


if __name__ == "__main__":
    main()
