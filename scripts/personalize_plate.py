"""Generate a real replacement plate privately; never modify tracked public inputs or outputs."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part
import TechDraw

from design import ROOT, build_catalog, load_parameters
from freecad_build import setup_gui, stl_write
from freecad_geometry import bounds_list
from front_nameplate import plaque_shape, message_faces
from personalization import load_private, private_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".private/generated")
    parser.add_argument("--assembly", action="store_true", help="Also save a private copy of the existing public native assembly with only its plate replaced.")
    args = parser.parse_args()
    private = load_private(args.config)
    folder = private_output(args.output) / private["model"]
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError("Private output already contains files; choose a new ignored output directory rather than overwrite or mix recipients.")
    folder.mkdir(exist_ok=True)
    parameters = load_parameters()
    catalog = build_catalog(parameters)
    key = f"NP3-TEXT-{private['model']}"
    spec = {**catalog["parts"][key], "text": private["lines"]}
    parameters["message"]["lines"] = private["lines"]
    measured = message_faces(spec, parameters)
    shape = plaque_shape(spec, parameters)
    if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
        raise ValueError("Private plate generation produced an invalid solid; no public output was changed.")
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=.025, AngularDeflection=.2094395102, Relative=False)
    stl_write(mesh, folder / "plate.stl")
    shape.exportStep(str(folder / "plate.step"))
    svg = TechDraw.projectToSVG(shape, App.Vector(0, 0, 1))
    width, height = spec["width"], parameters["message"]["height"]
    (folder / "plate.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
        f'viewBox="0 {-height} {width} {height}">{svg}</svg>')
    gui = setup_gui()
    document = App.newDocument("PrivateReplacementPlate")
    obj = document.addObject("Part::Feature", "ReplacementPlate")
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "PartID")
    obj.PartID = key
    obj.addProperty("App::PropertyString", "PrivateDisplayLines")
    obj.PrivateDisplayLines = json.dumps(private["lines"])
    color_faces = [(0.96, .95, .92) if face.CenterOfMass.z > 2.401 else (.09, .11, .15)
                   for face in shape.Faces]
    obj.ViewObject.ShapeColor = (.09, .11, .15)
    obj.ViewObject.DiffuseColor = color_faces
    document.recompute()
    document.saveAs(str(folder / "plate.FCStd"))
    if args.assembly:
        source = ROOT / "site/downloads" / private["model"] / f"{private['model']}.FCStd"
        if not source.is_file():
            raise FileNotFoundError("Build the generic public native assembly before requesting a private assembly copy.")
        assembly = App.openDocument(str(source))
        root = assembly.getObject("Design")
        if root:
            root.addProperty("App::PropertyString", "PrivatePersonalizationSHA256")
            root.PrivatePersonalizationSHA256 = hashlib.sha256(
                json.dumps(private, sort_keys=True).encode()).hexdigest()
        targets = [item for item in assembly.Objects if getattr(item, "PartID", "") == key]
        if len(targets) != 1:
            raise ValueError("The selected assembly must contain exactly one matching message plate.")
        target = targets[0]
        placement = App.Placement(target.Placement)
        target.Shape = shape
        target.Placement = placement
        if hasattr(target, "MessageLines"):
            target.MessageLines = json.dumps(private["lines"])
        target.ViewObject.DiffuseColor = color_faces
        assembly.recompute()
        assembly.saveAs(str(folder / "assembly.FCStd"))
        objects = [item for item in assembly.Objects if hasattr(item, "PartID")]
        import Import
        Import.export(objects, str(folder / "assembly.step"))
    manifest = {
        "visibility": "private", "model": private["model"], "lines": private["lines"],
        "part": key, "bounds_mm": bounds_list(shape), "units": "mm",
        "minimum_measured_straight_strokes_mm": [
            min(gauge["width_mm"] for gauge in gauges) for _, _, gauges in measured
        ],
        "manual_black_to_white_change_after_mm": 2.4,
        "public_files_modified": False, "physical_fit_tested": False,
        "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in folder.iterdir() if path.is_file() and path.suffix in (".stl", ".step", ".FCStd", ".svg")},
        "warning": "These files contain the private display values. Do not upload them to public Issues, PRs, CI artifacts, Pages or screenshots.",
    }
    (folder / "private-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("PRIVATE_PLATE_GENERATED: real native/STEP/STL/SVG; values were not echoed; public files unchanged.",
          file=sys.__stdout__, flush=True)


if __name__ == "__main__":
    main()
    sys.__stdout__.flush()
    sys.__stderr__.flush()
    os._exit(0)
