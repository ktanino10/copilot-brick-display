"""Small supported glyph trials copied at actual scale from the revised generic plaque faces."""

import hashlib
import json
from pathlib import Path
import sys
import zipfile

import FreeCAD as App
import MeshPart
import Part
import trimesh

from design import ROOT, load_parameters, write_json
from freecad_build import setup_gui, stl_write
from freecad_geometry import bounds_list
from nameplate_lettering import revised_rows
from package_prints import write_3mf
from verify_lettering import paths_for_faces


def place_next(shape, previous, gap):
    shape.translate(App.Vector(-shape.BoundBox.XMin, 0, 0))
    if previous is None:
        shape.translate(App.Vector(2, 0, 0))
        return shape
    right = previous.BoundBox.XMax + gap
    left = right
    probe = shape.copy()
    probe.translate(App.Vector(left, 0, 0))
    while probe.distToShape(previous)[0] > gap:
        right = left
        left -= .05
        if left < previous.BoundBox.XMin:
            raise ValueError("Cannot set the coupon glyph clearance without guessing.")
        probe = shape.copy()
        probe.translate(App.Vector(left, 0, 0))
    for _ in range(32):
        middle = (left + right) / 2
        probe = shape.copy()
        probe.translate(App.Vector(middle, 0, 0))
        if probe.distToShape(previous)[0] < gap:
            left = middle
        else:
            right = middle
    shape.translate(App.Vector(right, 0, 0))
    return shape


def main():
    p = load_parameters()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    folder = ROOT / "site/downloads/lettering-coupons"
    folder.mkdir(parents=True, exist_ok=True)
    setup_gui()
    records = []
    for model in c["models"]:
        part = c["parts"][f"NP3-TEXT-{model['id']}"]
        rows = revised_rows(part, p)
        selected, row_records = [], []
        for row, chars, goal in zip(rows, ("aeod", "gbo./R"), part["lettering_goals"]):
            previous, glyph_records = None, []
            for char in chars:
                index, _, original = next(glyph for glyph in row["glyphs"] if glyph[1] == char)
                placed = place_next(original.copy(), previous, goal["adjacent_glyph_clearance"])
                if abs(placed.Area - original.Area) > 1e-8:
                    raise ValueError("Coupon glyph changed scale or shape.")
                actual_gap = placed.distToShape(previous)[0] if previous else None
                selected.append(placed)
                glyph_records.append({"character": char, "source_index": index, "source_row": row["number"],
                                      "shape_area_mm2": original.Area, "actual_gap_to_previous_mm": actual_gap,
                                      "scale_changed": False})
                previous = placed
            row_records.append({"row": row["number"], "sample": chars, "actual_source_height_mm": row["height_mm"],
                                "glyphs": glyph_records, "spacing_target_mm": goal["adjacent_glyph_clearance"]})
        width = max(shape.BoundBox.XMax for shape in selected) + 2
        height = 40
        body = Part.makeBox(width, height, p["message"]["thickness"])
        full = body.multiFuse([shape.extrude(App.Vector(0, 0, p["message"]["relief"])) for shape in selected]).removeSplitter()
        if not full.isValid() or len(full.Solids) != 1:
            raise ValueError("Invalid connected glyph coupon.")
        stem = f"GLYPH-{model['id']}"
        document = App.newDocument(stem.replace("-", "_"))
        obj = document.addObject("Part::Feature", "GlyphTrial")
        obj.Shape = full
        obj.addProperty("App::PropertyString", "SourcePlate")
        obj.SourcePlate = part["id"]
        obj.addProperty("App::PropertyString", "Purpose")
        obj.Purpose = "Trial only, not installed and not part of the completed model BOM."
        obj.ViewObject.ShapeColor = (.09, .11, .15)
        obj.ViewObject.DiffuseColor = [(.96, .95, .92) if face.CenterOfMass.z > 2.401 else (.09, .11, .15) for face in full.Faces]
        document.recompute()
        document.saveAs(str(folder / f"{stem}.FCStd"))
        mesh = MeshPart.meshFromShape(Shape=full, LinearDeflection=.025, AngularDeflection=.2094395102, Relative=False)
        stl_write(mesh, folder / f"{stem}.stl")
        loaded = trimesh.load_mesh(folder / f"{stem}.stl")
        if not loaded.is_watertight or not loaded.is_winding_consistent or loaded.volume <= 0 or loaded.body_count != 1:
            raise ValueError("Coupon mesh is not one closed positive-volume component.")
        plate = [{"part": stem, "position": [(256 - width) / 2, 108, 0]}]
        write_3mf(folder / f"{stem}.3mf", "black", plate, c, {stem: loaded}, ("white", 2.4))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="40mm" viewBox="0 -40 {width} 40">'
               f'<rect x="0" y="-40" width="{width}" height="40" fill="#171d28"/>'
               + paths_for_faces(selected) + "</svg>")
        (folder / f"{stem}.svg").write_text(svg)
        App.closeDocument(document.Name)
        reopened = App.openDocument(str(folder / f"{stem}.FCStd"))
        if abs(reopened.getObject("GlyphTrial").Shape.Volume - full.Volume) > 1e-6:
            raise ValueError("Reopened coupon differs from generated solid.")
        App.closeDocument(reopened.Name)
        records.append({"model": model["id"], "coupon": stem, "quantity": 1, "source_plate": part["id"],
                        "source_plate_sha256": part["sha256"], "bounds_mm": bounds_list(full), "rows": row_records,
                        "manual_color_boundary_mm": 2.4, "relief_mm": 1.2, "installed_quantity": 0,
                        "hashes": {suffix: hashlib.sha256((folder / f"{stem}.{suffix}").read_bytes()).hexdigest()
                                   for suffix in ("FCStd", "stl", "3mf", "svg")}})
        print("SAVED_ACTUAL_GLYPH_TRIAL", stem, bounds_list(full), flush=True)
    write_json(folder / "manifest.json", {
        "revision": c["revision"], "models": records, "sliced": False, "physical_trial_performed": False,
        "instructions": "Choose only your model; flat black backing down. After the2.4mm support, pause before first white paths. No pause/profile/G-code encoded. Do not add trial pieces to the assembly.",
        "method": "Glyph faces copied without scale changes from actual model rows; rearranged using the same minimum-clearance targets.",
    })
    with zipfile.ZipFile(ROOT / "site/downloads/lettering-coupons.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            if path.suffix in (".json", ".stl", ".3mf", ".svg", ".FCStd"):
                archive.write(path, path.name)
    write_json(ROOT / "validation/lettering-coupons.json", {
        "status": "PASS_NATIVE_REOPEN_AND_CLOSED_TRIAL_MESH", "revision": c["revision"], "models": records,
        "completed_bom_changed": False, "sliced": False, "physical_trial_performed": False,
    })


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    import os
    os._exit(0)
