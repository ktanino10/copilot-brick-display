"""Apply actual viewer offsets to native front interfaces at every release phase."""

import json
import hashlib

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
    native_audit = json.loads((ROOT / "validation/cad.json").read_text())
    assert native_audit["parameters_sha256"] == catalog["parameters_sha256"]
    pair_cache = {}
    for model in catalog["models"]:
        name = model["id"]
        path = ROOT / "site/downloads" / name / f"{name}.FCStd"
        audited = next(item for item in native_audit["models"] if item["model"] == name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == audited["fcstd_sha256"]
        assert audited["maximum_intersection_mm3"] < 1e-5
        document = App.openDocument(str(path))
        shapes = {obj.InstanceID: obj.Shape.copy() for obj in document.Objects if hasattr(obj, "InstanceID")}
        maximum, checked = 0, 0
        interfaces = [item for item in model["placements"] if item.get("role") in ("front_module", "keeper")]
        bases = [item for item in model["placements"] if item.get("role") == "base_course"]
        def key_for(item, other, offsets):
            return (item["part"], other["part"],
                    tuple(round(item["position"][axis] + offsets[item["id"]][axis]
                                - other["position"][axis] - offsets[other["id"]][axis], 6)
                          for axis in range(3)))
        zero = {item["id"]: [0, 0, 0] for item in model["placements"]}
        for index, item in enumerate(interfaces):
            for other in bases + interfaces[:index]:
                pair_cache[key_for(item, other, zero)] = 0.0
        for sample in (s for s in samples if s["model"] == name and s["percent"] in (0, 1, 8, 10, 15, 20, 25, 30, 35, 40, 50, 75, 100)):
            moving = {item["id"]: moved(shapes[item["id"]], sample["offsets"][item["id"]])
                      for item in interfaces + bases}
            for index, item in enumerate(interfaces):
                for other in bases + interfaces[:index]:
                    key = key_for(item, other, sample["offsets"])
                    if key not in pair_cache:
                        pair_cache[key] = overlap(moving[item["id"]], moving[other["id"]])
                    value = pair_cache[key]
                    maximum = max(maximum, value)
                    checked += 1
                    assert value < 1e-5, (name, sample["percent"], item["id"], other["id"], value)
        sample35 = next(s for s in samples if s["model"] == name and s["percent"] == 35)
        old_overlap = 0
        for keeper in (item for item in interfaces if item["role"] == "keeper"):
            old_offset = list(sample35["offsets"][keeper["id"]])
            old_offset[1] = -20
            for module in (item for item in interfaces if item["role"] == "front_module"):
                old_overlap = max(old_overlap, overlap(moved(shapes[keeper["id"]], old_offset),
                                                       moved(shapes[module["id"]], sample35["offsets"][module["id"]])))
        assert old_overlap > 1
        record = {"model": name, "checked_front_pairs": checked, "maximum_intersection_mm3": maximum,
                  "regression_old_20mm_keeper_escape_overlap_mm3": old_overlap,
                  "release_phases": "keeper up6, forward32 (16mm depth +14mm module travel +2mm gap); modules up45, forward14; then centered course spread",
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
