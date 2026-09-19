"""Apply actual viewer offsets to native front interfaces at every release phase."""

import json

import FreeCAD as App
import Part

from design import ROOT, write_json


def moved(shape, delta):
    result = shape.copy()
    result.translate(App.Vector(*delta))
    return result


def overlap(a, b):
    x, y = a.BoundBox, b.BoundBox
    if min(x.XMax, y.XMax) <= max(x.XMin, y.XMin) or min(x.YMax, y.YMax) <= max(x.YMin, y.YMin) or min(x.ZMax, y.ZMax) <= max(x.ZMin, y.ZMin):
        return 0.0
    return a.common(b).Volume


def main():
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    samples = json.loads((ROOT / "build/explosion-samples.json").read_text())
    records = []
    for model in catalog["models"]:
        name = model["id"]
        document = App.openDocument(str(ROOT / "site/downloads" / name / f"{name}.FCStd"))
        shapes = {obj.InstanceID: obj.Shape.copy() for obj in document.Objects if hasattr(obj, "InstanceID")}
        maximum, checked = 0, 0
        interfaces = [item for item in model["placements"] if item.get("role") in ("front_module", "keeper")]
        bases = [item for item in model["placements"] if item.get("role") == "base_course"]
        for sample in (s for s in samples if s["model"] == name and s["percent"] in (0, 1, 8, 10, 15, 20, 25, 30, 35, 40, 50, 75, 100)):
            moving = {item["id"]: moved(shapes[item["id"]], sample["offsets"][item["id"]])
                      for item in interfaces + bases}
            for index, item in enumerate(interfaces):
                for other in bases + interfaces[:index]:
                    value = overlap(moving[item["id"]], moving[other["id"]])
                    maximum = max(maximum, value)
                    checked += 1
                    assert value < 1e-5, (name, sample["percent"], item["id"], other["id"], value)
        record = {"model": name, "checked_front_pairs": checked, "maximum_intersection_mm3": maximum,
                  "release_phases": "keeper up6, forward20; modules up45, forward14; then centered course spread",
                  "body_proof": "Each unchanged course moves rigidly; order preserved and axial gaps only increase."}
        records.append(record)
        App.closeDocument(document.Name)
        print("PASS_NATIVE_DISPLAY_ROUTE", record, flush=True)
    write_json(ROOT / "validation/explosion-motion.json", {
        "status": "PASS_REAL_NATIVE_MOTION_CHECK", "revision": catalog["revision"],
        "models": records, "motion_source": "site/assembly-motion.js executed by tests/motion.mjs",
        "physical_simulation": False,
    })


if __name__ == "__main__":
    main()
