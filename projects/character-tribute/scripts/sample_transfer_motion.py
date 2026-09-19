"""Sample actual saved Blender trajectories and their interpolation control points."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]


def curves(obj):
    animation=obj.animation_data
    for layer in animation.action.layers:
        for strip in layer.strips:
            bag=strip.channelbag(animation.action_slot)
            if bag:
                yield from bag.fcurves


def main():
    baseline="--baseline" in sys.argv
    blend=ROOT/"media/character-assembly.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False)
    catalog=json.loads((ROOT/"catalog.json").read_text())
    canonical={i["id"]:i for i in catalog["instances"]}
    results={}
    for name,critical,first,last in (("Assembly",392,384,441),("Disassembly",185,136,193)):
        scene=bpy.data.scenes[name]
        bpy.context.window.scene=scene
        objects={o["instance_id"]:o for o in scene.objects if "instance_id" in o}
        frames=[critical] if baseline else sorted(set(range(first,last+1)) |
                  {critical+x for x in (-.75,-.5,-.25,.25,.5,.75)})
        samples=[]
        for frame in frames:
            whole=math.floor(frame)
            scene.frame_set(whole,subframe=frame-whole)
            bpy.context.view_layer.update()
            matrices={}
            for key in ("stand","capture-frame"):
                matrix=objects[key].matrix_world.copy()
                matrix.translation*=1000
                matrices[key]=[list(row) for row in matrix]
            deltas=[]
            for key,obj in objects.items():
                if key in ("stand","message-dock","message-card"):
                    continue
                deltas.append(tuple((obj.location-Vector(canonical[key]["position_mm"])*.001)*1000))
            samples.append({"frame":frame,"matrices_mm":matrices,
                            "plaque_translation_min_mm":[min(d[i] for d in deltas) for i in range(3)],
                            "plaque_translation_max_mm":[max(d[i] for d in deltas) for i in range(3)]})
        tracks={}
        for key,obj in objects.items():
            if key in ("message-dock","message-card"):
                continue
            records=[]
            for curve in curves(obj):
                if curve.data_path not in ("location","rotation_euler"):
                    continue
                records.append({"data_path":curve.data_path,"axis":curve.array_index,
                                "keys":[{"frame":p.co.x,"value":p.co.y,
                                         "left":list(p.handle_left),"right":list(p.handle_right),
                                         "interpolation":p.interpolation} for p in curve.keyframe_points]})
            tracks[key]=records
        results[name]={"samples":samples,"tracks":tracks}
    out={"source":"Actual saved Blender native animation, not a proposed path",
         "blend_sha256":hashlib.sha256(blend.read_bytes()).hexdigest(),"scenes":results}
    target=ROOT/"validation"/("transfer-before.json" if baseline else "transfer-samples.json")
    target.write_text(json.dumps(out,indent=2)+"\n")
    print("NATIVE_TRANSFER_SAMPLED",target.name)


if __name__=="__main__":
    main()
