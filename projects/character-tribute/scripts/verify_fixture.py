"""Check the actual printed rests support the front-down frame without touching the relief."""
import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = json.loads((ROOT/"parameters.json").read_text())
    doc = App.openDocument(str(ROOT/"native/character-tribute.FCStd"))
    plaque = {}
    for obj in doc.Objects:
        if not hasattr(obj,"InstanceID") or obj.InstanceID in ("stand","message-dock","message-card"):
            continue
        shape=obj.Shape.copy()
        shape.translate(App.Vector(0,-p["board"]["back_y"],-p["board"]["bottom_z"]))
        shape.rotate(App.Vector(),App.Vector(1,0,0),-90)
        shape.rotate(App.Vector(),App.Vector(1,0,0),180)
        shape.translate(App.Vector(0,0,18.4))
        plaque[obj.InstanceID]=shape
    rest=Part.Shape()
    rest.read(str(ROOT/"native/parts/ASSEMBLY-REST.step"))
    rests=[]
    for x in (-84,68):
        placed=rest.copy()
        placed.translate(App.Vector(x,-136,0))
        rests.append(placed)
    for support in rests:
        for name,shape in plaque.items():
            if support.BoundBox.intersect(shape.BoundBox) and support.common(shape).Volume>1e-5:
                raise ValueError(f"Assembly rest collides with {name}")
        if support.distToShape(plaque["capture-frame"])[0]>1e-5:
            raise ValueError("Assembly rest does not contact the structural frame")
    minimum=min(shape.optimalBoundingBox(False,False).ZMin for shape in plaque.values())
    if minimum<5.5:
        raise ValueError("The front-down relief is not clear of the table")
    report={"status":"pass","revision":"T2","source":"Actual saved native assembly and ASSEMBLY-REST STEP",
            "rest_quantity":2,"rest_print_origins_on_table_mm":[[-84,-136,0],[68,-136,0]],
            "front_frame_plane_above_table_mm":12,"minimum_relief_table_clearance_mm":minimum,
            "frame_contacts_verified":True,"rest_part_intersections":0,
            "note":"Rigid CAD clearance only; use a level table, support the frame and prototype physical stability."}
    (ROOT/"validation/fixture.json").write_text(json.dumps(report,indent=2)+"\n")
    App.closeDocument(doc.Name)
    print("ASSEMBLY_REST_CLEARANCE_PASS",minimum)


if __name__=="__main__":
    main()
