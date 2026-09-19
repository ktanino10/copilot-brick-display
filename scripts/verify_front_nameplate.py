"""Read the actual native model: front envelope, keyed retention, removal and print facts."""

import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App
import Part

from design import ROOT, write_json
from freecad_geometry import bounds_list
from letter_metrics import straight_strokes


def shifted(shape, dx=0, dy=0, dz=0):
    result = shape.copy()
    result.translate(App.Vector(dx, dy, dz))
    return result


def measure(model, catalog, downloads):
    doc = App.openDocument(str(downloads / model["id"] / f"{model['id']}.FCStd"))
    objects = [obj for obj in doc.Objects if hasattr(obj, "PartID")]
    by_id = {obj.InstanceID: obj for obj in objects}
    modules = [item for item in model["placements"] if item.get("role") == "front_module"]
    keeper_items = [item for item in model["placements"] if item.get("role") == "keeper"]
    bases = [obj.Shape.copy() for obj in objects if obj.PartID.startswith("BASE3-")]
    base = Part.makeCompound(bases)
    assert len(keeper_items) == 3
    records = []
    for item in modules:
        plaque_obj = by_id[item["id"]]
        plaque = plaque_obj.Shape.copy()
        keepers = [by_id[k["id"]].Shape.copy() for k in keeper_items if k["module"] == item["module"]]
        other_module = next(by_id[i["id"]].Shape for i in modules if i != item)
        stops = Part.makeCompound(keepers)
        lo, hi = bounds_list(plaque)
        assert lo[2] >= 0 and hi[2] <= 48 and lo[1] >= .099999
        assert abs(lo[2] - 4) < 1e-5 and abs(hi[2] - 44) < 1e-5
        assert plaque.common(base).Volume < 1e-5
        assert plaque.common(stops).Volume < 1e-5
        retained = {}
        for name, delta in [("front", (0, -.8, 0)), ("rear", (0, .4, 0)),
                            ("left", (-.5, 0, 0)), ("right", (.5, 0, 0)), ("down", (0, 0, -.2))]:
            overlap = shifted(plaque, *delta).common(base).Volume
            assert overlap > 1e-4, (model["id"], item["module"], name, overlap)
            retained[name] = overlap
        retained["up_with_keepers"] = shifted(plaque, dz=4.4).common(stops).Volume
        assert retained["up_with_keepers"] > 1e-4
        maximum_removal = 0
        for dz in (.05, .2, 1, 5, 9.6, 19.2, 28.8, 38.4, 44, 45, 55):
            moving = shifted(plaque, dz=dz)
            value = max(moving.common(base).Volume, moving.common(other_module).Volume)
            maximum_removal = max(maximum_removal, value)
            assert value < 1e-5, (model["id"], item["module"], dz, value)
        records.append({"module": item["module"], "part": item["part"], "bounds_mm": [lo, hi],
                        "blocked_translation_volume_mm3": retained,
                        "keeper_removed_vertical_extraction_max_overlap_mm3": maximum_removal})
    text_obj = next(by_id[item["id"]] for item in modules if item["module"] == "text")
    assert json.loads(text_obj.MessageLines) == ["Same icon, New adventures", "github.com/YOUR-USERNAME"]
    local = text_obj.Shape.copy()
    local.Placement = App.Placement()
    cap_z = catalog["message"]["thickness"] + catalog["message"]["relief"]
    faces = [face for face in local.Faces if face.BoundBox.ZLength < 1e-5 and abs(face.BoundBox.ZMin - cap_z) < 1e-5]
    gauges = straight_strokes(faces)
    minimum = min(g["width_mm"] for g in gauges)
    assert minimum >= .84
    lines = []
    for index, content in enumerate(catalog["message"]["lines"]):
        selected = [face for face in faces if (face.CenterOfMass.y >= 21) == (index == 0)]
        line_shape = Part.makeCompound(selected)
        lo, hi = bounds_list(line_shape)
        lines.append({"text": content, "width_mm": hi[0] - lo[0], "height_mm": hi[1] - lo[1],
                      "assembled_z_range_mm": [4 + lo[1], 4 + hi[1]]})
    result = {
        "model": model["id"], "native_instances": len(objects), "base_courses": 5,
        "base_body_height_mm": 48, "modules_inside_base_front": True, "modules": records,
        "lines": lines, "minimum_actual_parallel_straight_stroke_mm": minimum,
        "stroke_boundary": "Measured cap-face straight sections; mathematical curve/corner tips are not claimed as constant-width walls.",
        "mechanism": "Independent dovetail slides, shaped bottom seats, two text keepers and one logo keeper.",
        "print": "Rear face on bed; manual black-to-white swap at text2.4mm/logo2.8mm; no AMS required.",
        "physical_fit_clutch_strength": "NOT_TESTED",
    }
    App.closeDocument(doc.Name)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["A", "B", "C"])
    parser.add_argument("--catalog", type=Path, default=ROOT / "design/catalog.json")
    parser.add_argument("--downloads", type=Path, default=ROOT / "site/downloads")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    records = [measure(model, catalog, args.downloads) for model in catalog["models"] if model["id"] in args.models]
    write_json(ROOT / "validation/front-nameplate.json", {
        "revision": catalog["revision"], "parameters_sha256": catalog["parameters_sha256"],
        "status": "PASS_NATIVE_FRONT_CAPTURE_AND_EXTRACTION",
        "models": records, "frozen_tribute": "separate BRICK-8-MSG-SLOT-1; no source or public asset changed",
    })


if __name__ == "__main__":
    main()
