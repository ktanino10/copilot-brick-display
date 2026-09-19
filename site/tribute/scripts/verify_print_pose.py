"""Check real print-local frame sections start on the bed, rather than on remote bosses."""
import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT=Path(__file__).resolve().parents[1]


def section(shape,z):
    wires=shape.slice(App.Vector(0,0,1),z)
    if not wires:
        raise ValueError(f"No material at print layer {z}")
    face=Part.makeFace(wires,"Part::FaceMakerBullseye")
    face.translate(App.Vector(0,0,-z))
    return face


def main():
    catalog=json.loads((ROOT/"catalog.json").read_text())
    results={}
    for pid in ("T02","CAPTURE-FRAME"):
        part=next(p for p in catalog["parts"] if p["id"]==pid)
        if part["print_rotation_deg_xyz"] != [180,0,0]:
            raise ValueError(f"Frame master is not front-face down: {pid}")
        shape=Part.Shape()
        shape.read(str(ROOT/part["step"]))
        bounds=shape.optimalBoundingBox(False,False)
        if abs(bounds.ZMin)>.001:
            raise ValueError(f"Print master does not start at Z=0: {pid}")
        base=section(shape,.1)
        samples=[]
        for z in (1,2.4,3.1,4.5,4.7,6.3,6.5,8,10,12,14.3):
            plane=section(shape,z)
            outside=plane.cut(base).Area
            if outside>.05:
                raise ValueError(f"Unbased frame material at {pid}/{z}: {outside}mm2")
            samples.append({"height_mm":z,"section_area_mm2":plane.Area,
                            "area_outside_first_layer_footprint_mm2":outside})
        results[pid]={"print_rotation_deg_xyz":[180,0,0],"bed_contact_section_z_mm":.1,
                      "bed_contact_area_mm2":base.Area,"layer_samples":samples,
                      "scope":"Detects panel starting above isolated bosses. Does not certify every overhang or real thread printing; inspect slicer and coupons."}
    report={"status":"pass","revision":"T2-R1","source":"Actual normalized print STEP masters; X180 flip with inverse canonical assembly placement",
            "parts":results}
    (ROOT/"validation/print-pose.json").write_text(json.dumps(report,indent=2)+"\n")
    print("PRINT_POSE_PASS",{key:round(value["bed_contact_area_mm2"],2) for key,value in results.items()})


if __name__=="__main__":
    main()
