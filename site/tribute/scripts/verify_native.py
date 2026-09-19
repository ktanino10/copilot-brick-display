"""Reopen the saved native assembly in a fresh, GUI-free FreeCAD process."""
import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    parts = {item["id"]: item for item in catalog["parts"]}
    instances = {item["id"]: item for item in catalog["instances"]}
    doc = App.openDocument(str(ROOT / "native/character-tribute.FCStd"))
    objects = [obj for obj in doc.Objects if hasattr(obj, "InstanceID")]
    if len(objects) != len(instances):
        raise ValueError("Native document lost assembly instances")
    for obj in objects:
        instance = instances[obj.InstanceID]
        part = parts[instance["part"]]
        if not obj.Shape.isValid() or len(obj.Shape.Solids) != 1:
            raise ValueError(f"Native reopen invalid shape: {obj.InstanceID}")
        if abs(obj.Shape.Volume - part["cad_volume_mm3"]) > 1e-4:
            raise ValueError(f"Native reopen changed volume: {obj.InstanceID}")
        if (obj.Placement.Base - App.Vector(*instance["position_mm"])).Length > 1e-6:
            raise ValueError(f"Native reopen changed placement: {obj.InstanceID}")
        expected = App.Rotation(App.Vector(1, 0, 0), instance["rotation_deg_xyz"][0])
        if not obj.Placement.Rotation.isSame(expected, 1e-7):
            raise ValueError(f"Native reopen changed orientation: {obj.InstanceID}")
    assembly = Part.makeCompound([obj.Shape for obj in objects])
    bounds = assembly.BoundBox
    data = json.loads((ROOT / "parameters.json").read_text())
    target = [data["stand"]["width"], data["stand"]["depth"],
              data["board"]["bottom_z"] + data["board"]["height"]]
    actual = [bounds.XLength, bounds.YLength, bounds.ZLength]
    if any(abs(a - b) > 1e-4 for a, b in zip(actual, target)):
        raise ValueError(f"Native envelope {actual} differs from designed envelope {target}")
    report = {
        "status": "pass", "freecad_version": ".".join(App.Version()[:3]),
        "native_reopened": True, "instance_count": len(objects),
        "assembly_bounds_mm": [[bounds.XMin, bounds.YMin, bounds.ZMin],
                                [bounds.XMax, bounds.YMax, bounds.ZMax]],
        "assembly_size_mm": [bounds.XLength, bounds.YLength, bounds.ZLength],
        "physical_fit_tested": False
    }
    step = Part.Shape()
    step.read(str(ROOT / "native/character-tribute.step"))
    if len(step.Solids) != len(objects):
        raise ValueError("STEP reread solid count does not match the native assembly")
    volume_delta = abs(step.Volume - assembly.Volume)
    if volume_delta > .1 or volume_delta / assembly.Volume > 1e-6:
        raise ValueError("STEP reread volume differs from native geometry")
    report["step_reopened_solids"] = len(step.Solids)
    report["step_volume_difference_mm3"] = abs(step.Volume - assembly.Volume)
    report["step_volume_difference_fraction"] = volume_delta / assembly.Volume
    report["step_numerical_tolerance"] = {"absolute_mm3": .1, "relative": 1e-6,
                                         "note":"Numerical BRep/STEP integration tolerance, not a print-fit allowance."}
    part_reports = {}
    for part in parts.values():
        master = Part.Shape()
        master.read(str(ROOT / part["step"]))
        if not master.isValid() or len(master.Solids) != 1:
            raise ValueError(f"Invalid individual STEP: {part['id']}")
        delta = abs(master.Volume-part["cad_volume_mm3"])
        if delta > .05 or delta/part["cad_volume_mm3"] > 1e-5:
            raise ValueError(f"Individual STEP volume mismatch: {part['id']}")
        b = master.optimalBoundingBox(False,False)
        if any(abs(x-y) > .001 for x,y in zip([b.XLength,b.YLength,b.ZLength],part["bounds_mm"])):
            raise ValueError(f"Individual STEP bounds mismatch: {part['id']}")
        part_reports[part["id"]] = {"valid_solid":True,"volume_difference_mm3":delta}
    report["individual_steps"] = part_reports
    (ROOT / "validation/native.json").write_text(json.dumps(report, indent=2) + "\n")
    catalog["native_reopened"] = True
    catalog["assembly_size_mm"] = report["assembly_size_mm"]
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    App.closeDocument(doc.Name)
    print("NATIVE_AND_STEP_REOPEN_PASS", report["assembly_size_mm"], flush=True)


if __name__ == "__main__":
    main()
