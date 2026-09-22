"""Measure the actual revised generic letter faces and saved native plate, not font-size proxies."""

import argparse
import hashlib
import html
import json
from pathlib import Path

import FreeCAD as App
import Part

from design import ROOT, load_parameters, write_json
from freecad_geometry import bounds_list
from legible_lettering import face_data
from legible_metrics import ink_shape, contour_polygon, central_chords, aperture_width, material_core_split
from nameplate_lettering import revised_rows


def paths_for_faces(faces):
    paths = []
    for shape in faces:
        for face in face_data(shape):
            rings = []
            for ring in [face["outer"], *face["holes"]]:
                rings.append("M " + " L ".join(f"{x:.5f},{-y:.5f}" for x, y in ring) + " Z")
            paths.append(f'<path d="{" ".join(rings)}" fill="#f5f3eb" fill-rule="evenodd"/>')
    return "".join(paths)


def cap_faces(shape, z):
    return [face for face in shape.Faces if face.BoundBox.ZLength < 1e-5 and abs(face.BoundBox.ZMin - z) < 1e-5]


def preview(new_shape, old_shape, width, model, folder):
    old = paths_for_faces(cap_faces(old_shape, 3.2))
    new = paths_for_faces(cap_faces(new_shape, 3.6))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1280" viewBox="0 0 {width + 12} 108">
<rect width="100%" height="100%" fill="#f3f5f1"/>
<g font-family="sans-serif" font-size="3" fill="#152637">
<text x="6" y="5">{model} / BEFORE: 4.0 public template (historical comparison only)</text>
<text x="6" y="58">{model} / AFTER: 5.0 legible plaques - actual CAD face outlines</text></g>
<rect x="6" y="8" width="{width}" height="40" rx="1" fill="#171d28"/>
<g transform="translate(6 48)">{old}</g>
<rect x="6" y="61" width="{width}" height="40" rx="1" fill="#171d28"/>
<g transform="translate(6 101)">{new}</g>
<text x="6" y="106" font-family="sans-serif" font-size="2.5" fill="#536778">Rear carrier unchanged / relief 0.8 to 1.2 mm / contour sampling 0.002 mm / NOT PRINT TESTED</text></svg>'''
    path = folder / f"{model}-lettering-before-after.svg"
    path.write_text(svg)
    return path


def inspect_model(model, catalog, parameters, downloads, baseline_cache, preview_folder):
    part_id = f"NP3-TEXT-{model['id']}"
    spec = catalog["parts"][part_id]
    document = App.openDocument(str(downloads / model["id"] / f"{model['id']}.FCStd"))
    objects = [obj for obj in document.Objects if hasattr(obj, "PartID")]
    target = next(obj for obj in objects if obj.PartID == part_id)
    if json.loads(target.MessageLines) != parameters["message"]["lines"]:
        raise ValueError("Saved native text does not match the exact current public input.")
    native = target.Shape.copy()
    native.Placement = App.Placement()
    if not native.isValid() or len(native.Solids) != 1 or native.Volume <= 0:
        raise ValueError("Invalid reopened native plaque.")
    old = Part.Shape()
    old.read(str(baseline_cache / f"{part_id}.brep"))
    cutter = Part.makeBox(spec["width"] + 2, 42, 2.4, App.Vector(-1, -1, 0))
    before, after = old.common(cutter), native.common(cutter)
    difference = before.cut(after).Volume + after.cut(before).Volume
    if difference > 1e-6:
        raise ValueError("The black carrier or rear attachment changed.")
    rows = revised_rows(spec, parameters)
    actual_caps = cap_faces(native, 3.6)
    expected_area = sum(face.Area for row in rows for _, _, shape in row["glyphs"] for face in shape.Faces)
    if abs(sum(face.Area for face in actual_caps) - expected_area) > 1e-4:
        raise ValueError("Native cap faces differ from regenerated exact glyphs.")
    expected_shape = before.multiFuse([
        shape.extrude(App.Vector(0, 0, parameters["message"]["relief"]))
        for row in rows for _, _, shape in row["glyphs"]
    ]).removeSplitter()
    geometry_difference = native.cut(expected_shape).Volume + expected_shape.cut(native).Volume
    if geometry_difference > 1e-5:
        raise ValueError("Saved native geometry differs from the current checked lettering implementation.")
    results = []
    for row, goals in zip(rows, spec["lettering_goals"]):
        glyphs = []
        for index, character, shape in row["glyphs"]:
            contours = face_data(shape)
            ink = ink_shape({"faces": contours})
            counters = [central_chords(contour_polygon(hole)) for face in contours for hole in face["holes"]]
            neck = material_core_split(ink)
            if neck is not None and neck < .84 - 1e-8:
                raise ValueError(f"Undersized persistent material neck in {part_id}, row{row['number']}, glyph{index}.")
            if counters and min(n for pair in counters for n in pair) < goals["counter_central_half_chord"] - .008:
                raise ValueError("Native counter measurement is below its documented sampled target.")
            glyphs.append({"index": index, "character": character, "closed_counter_chords_xy_mm": counters,
                           "open_pocket_escape_mm": aperture_width(ink) if character in "ce" else None,
                           "persistent_core_split_neck_mm": neck})
        results.append({
            "row": row["number"], "text": row["text"], "actual_width_mm": row["width_mm"],
            "actual_height_mm": row["height_mm"], "minimum_actual_gap_mm": row["minimum_gap_mm"],
            "minimum_parallel_straight_stroke_mm": min(g["width_mm"] for g in row["gauges"]),
            "targets": goals, "glyphs": glyphs,
        })
    comparison = preview(native, old, spec["width"], model["id"], preview_folder)
    native_path = downloads / model["id"] / f"{model['id']}.FCStd"
    result = {"model": model["id"], "part": part_id, "bounds_mm": bounds_list(native),
              "assembly_actual_mm": model["actual_mm"], "native_sha256": hashlib.sha256(native_path.read_bytes()).hexdigest(),
              "carrier_symmetric_difference_mm3": difference, "reopened_valid_solids": len(native.Solids),
              "current_lettering_symmetric_difference_mm3": geometry_difference,
              "exact_native_text": True, "cap_area_consistent": True, "rows": results,
              "comparison": comparison.name, "physical_trial": "NOT_PERFORMED"}
    App.closeDocument(document.Name)
    print("MEASURED_PUBLIC_LETTERING", model["id"], [(row["actual_width_mm"], row["actual_height_mm"],
          row["minimum_actual_gap_mm"], row["minimum_parallel_straight_stroke_mm"]) for row in results], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "design/catalog.json")
    parser.add_argument("--downloads", type=Path, default=ROOT / "site/downloads")
    parser.add_argument("--baseline-cache", type=Path, required=True)
    parser.add_argument("--preview-folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "validation/lettering.json")
    args = parser.parse_args()
    args.preview_folder.mkdir(parents=True, exist_ok=True)
    parameters = load_parameters()
    catalog = json.loads(args.catalog.read_text())
    records = [inspect_model(model, catalog, parameters, args.downloads, args.baseline_cache,
                             args.preview_folder) for model in catalog["models"]]
    write_json(args.output, {
        "status": "PASS_REOPENED_NATIVE_LETTERING_CANDIDATE", "revision": catalog["revision"],
        "parameters_sha256": catalog["parameters_sha256"], "models": records,
        "lettering_source_sha256": {name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
                                    for name in ("nameplate_lettering.py", "legible_lettering.py", "legible_metrics.py")},
        "measurement_definitions": {
            "contour_deflection_mm": .002, "counter": "Minimum of101 horizontal and101 vertical chords in central25–75% bands.",
            "aperture": "Widest escape on0.01mm grid, approximate uncertainty±0.03mm; not a maximum-inscribed-circle guarantee.",
            "spacing": "Exact BRep adjacent visible-glyph distance; planner's sampled spacing may differ by0.006mm.",
            "positive_stroke": "Parallel straight gauges and first erosion splitting two cores≥0.05mm² at0.005mm radius increments.",
            "limits": "Does not guarantee every mathematical curve tip, extrusion path, mechanical strength or successful print.",
        },
        "sliced": False, "physical_trial": "NOT_PERFORMED",
    })


if __name__ == "__main__":
    main()
