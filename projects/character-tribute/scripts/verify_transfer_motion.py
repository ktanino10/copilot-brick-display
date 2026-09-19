"""Reproduce or guard transfer-path collisions with actual Blender poses and saved BReps."""
import hashlib
import json
import math
from pathlib import Path
import sys

import FreeCAD as App
import Part

ROOT=Path(__file__).resolve().parents[1]


def at_matrix(shape,rows):
    matrix=App.Matrix(*[value for row in rows for value in row])
    result=shape.copy()
    result.Placement=App.Placement(matrix)
    return result


def channel(records,path,axis):
    return next(record["keys"] for record in records if record["data_path"]==path and record["axis"]==axis)


def constant_span(keys,first,last,value,tolerance=1e-7):
    for a,b in zip(keys,keys[1:]):
        if b["frame"]<=first or a["frame"]>=last:
            continue
        if a["interpolation"]=="BEZIER":
            values=[a["value"],a["right"][1],b["left"][1],b["value"]]
        elif a["interpolation"]=="LINEAR":
            values=[a["value"],b["value"]]
        else:
            values=[a["value"]]
        if any(abs(x-value)>tolerance for x in values):
            raise ValueError("A supposedly stationary axis has a nonconstant interpolation hull")


def main():
    baseline="--baseline" in sys.argv
    sample_path=ROOT/"validation"/("transfer-before.json" if baseline else "transfer-samples.json")
    source=json.loads(sample_path.read_text())
    catalog=json.loads((ROOT/"catalog.json").read_text())
    items={item["id"]:item for item in catalog["instances"]}
    doc=App.openDocument(str(ROOT/"native/character-tribute.FCStd"))
    shapes={o.InstanceID:o.Shape.copy() for o in doc.Objects if hasattr(o,"InstanceID")}
    records=[]
    for name,scene in source["scenes"].items():
        for sample in scene["samples"]:
            stand=at_matrix(shapes["stand"],sample["matrices_mm"]["stand"])
            frame=at_matrix(shapes["capture-frame"],sample["matrices_mm"]["capture-frame"])
            volume=stand.common(frame).Volume if stand.BoundBox.intersect(frame.BoundBox) else 0
            records.append({"scene":name,"frame":sample["frame"],"intersection_mm3":volume})
            if not baseline:
                if volume>1e-5:
                    raise ValueError(f"Animated stand/tongue collision: {records[-1]}")
                if any(abs(a-b)>.001 for a,b in zip(sample["plaque_translation_min_mm"],
                                                  sample["plaque_translation_max_mm"])):
                    raise ValueError("Closed plaque components are not moving as a rigid group")
    if baseline:
        if any(record["intersection_mm3"]<200 for record in records):
            raise ValueError("Reported original transfer collision was not reproduced")
        report={"status":"reproduced","source_blend_sha256":source["blend_sha256"],"samples":records}
        name="transfer-regression.json"
    else:
        for name,scene in source["scenes"].items():
            first,last=(385,408) if name=="Assembly" else (169,192)
            lower_start,lower_end=(408,440) if name=="Assembly" else (137,169)
            stand=scene["tracks"]["stand"]
            constant_span(channel(stand,"location",2),first,last,items["stand"]["position_mm"][2]*.001)
            for record in stand:
                if record["data_path"]=="rotation_euler":
                    constant_span(record["keys"],first,last,0)
            for key,tracks in scene["tracks"].items():
                if key=="stand":
                    continue
                for axis in (0,1):
                    constant_span(channel(tracks,"location",axis),min(first,lower_start),max(last,lower_end),
                                  items[key]["position_mm"][axis]*.001)
                for record in tracks:
                    if record["data_path"]=="rotation_euler":
                        constant_span(record["keys"],min(first,lower_start),max(last,lower_end),
                                      math.radians(items[key]["rotation_deg_xyz"][record["axis"]]))
                constant_span(channel(tracks,"location",2),first,last,items[key]["position_mm"][2]*.001+.05)
                zkeys=channel(tracks,"location",2)
                a=next(k for k in zkeys if abs(k["frame"]-lower_start)<1e-7)
                b=next(k for k in zkeys if abs(k["frame"]-lower_end)<1e-7)
                if a["interpolation"]!="LINEAR":
                    raise ValueError("Socket engagement is not a common rigid linear translation")
                expected=[0,.05] if name=="Disassembly" else [.05,0]
                base=items[key]["position_mm"][2]*.001
                if any(abs(value-offset)>1e-7 for value,offset in zip([a["value"]-base,b["value"]-base],expected)):
                    raise ValueError("Vertical socket-entry endpoints do not match the canonical pose")
            for axis in range(3):
                constant_span(channel(stand,"location",axis),lower_start,lower_end,
                              items["stand"]["position_mm"][axis]*.001)
        tongue=shapes["capture-frame"].common(Part.makeBox(300,300,41.6,App.Vector(-150,-150,0)))
        tb=tongue.optimalBoundingBox(False,False)
        if abs(tongue.Volume-80*6.4*32)>.01:
            raise ValueError("The only low part of the front frame is not the expected rectangular tongue")
        for key,shape in shapes.items():
            if key not in ("stand","capture-frame","message-dock","message-card") and shape.optimalBoundingBox(False,False).ZMin<41.6-.001:
                raise ValueError(f"A non-tongue part enters the stand-height region: {key}")
        sweep=Part.makeBox(80,6.4,82,App.Vector(tb.XMin,tb.YMin,tb.ZMin))
        swept_overlap=sweep.common(shapes["stand"]).Volume
        if swept_overlap>1e-5:
            raise ValueError("Continuous vertical tongue sweep collides with the stand")
        report={"status":"pass","source_blend_sha256":source["blend_sha256"],"samples":records,
                "sampled_max_intersection_mm3":max(r["intersection_mm3"] for r in records),
                "continuous_conditions":{"horizontal_slide":"Stand stays on table; plaque tongue held +50mm; X/Y alignment fixed",
                                         "minimum_slide_vertical_separation_mm":9.6+50-41.6,
                                         "socket_engagement":"Stand fixed; whole plaque moves linearly and rigidly along Z only",
                                         "vertical_tongue_sweep_intersection_mm3":swept_overlap,
                                         "tongue_sweep_mm":[80,6.4,82]},
                "native_cad_sha256":hashlib.sha256((ROOT/"native/character-tribute.FCStd").read_bytes()).hexdigest(),
                "scope":"Animation path verification; printed fit, strength and real human motion remain untested."}
        name="transfer-motion.json"
    (ROOT/"validation"/name).write_text(json.dumps(report,indent=2)+"\n")
    App.closeDocument(doc.Name)
    print("TRANSFER_MOTION",report["status"],records[:2])


if __name__=="__main__":
    main()
