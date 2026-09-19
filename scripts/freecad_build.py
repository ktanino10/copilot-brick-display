"""Run with FreeCAD's Python and lib directory on PYTHONPATH; see docs/rebuild.md."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import struct
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part
import TechDraw

from design import ROOT, build_catalog, load_parameters, write_json
from freecad_geometry import bounds_list, placement_for, shape_for


def stl_write(mesh, path):
    points, faces = mesh.Topology
    with path.open("wb") as stream:
        stream.write(b"Copilot Brick Display | millimetres | real FreeCAD tessellation".ljust(80, b"\0"))
        stream.write(struct.pack("<I", len(faces)))
        for face in faces:
            a, b, c = [points[index] for index in face]
            normal = (b - a).cross(c - a)
            if normal.Length:
                normal.normalize()
            stream.write(struct.pack("<12fH", *normal, *a, *b, *c, 0))
    return len(faces)


def html_color(hex_value):
    return tuple(int(hex_value[index:index + 2], 16) / 255 for index in (1, 3, 5))


def setup_gui():
    import FreeCADGui as Gui
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    return Gui


def generate_part(spec, p, cache, output):
    cache_path = cache / f"{spec['id']}.brep"
    if cache_path.exists():
        shape = Part.Shape()
        shape.read(str(cache_path))
    else:
        shape = shape_for(spec, p, ROOT)
        shape.exportBrep(str(cache_path))
    if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
        raise ValueError(f"Invalid cached solid: {spec['id']}")
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025,
                                  AngularDeflection=math.radians(12), Relative=False)
    filename = output / spec["stl"]
    filename.parent.mkdir(parents=True, exist_ok=True)
    triangles = stl_write(mesh, filename)
    spec.update({
        "bounds": bounds_list(shape), "volume_mm3": round(shape.Volume, 6),
        "mesh_triangles": triangles, "mesh_linear_deflection_mm": 0.025,
        "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
    })
    return shape


def save_assembly(model, c, shapes, output, gui):
    import Import
    document = App.newDocument(f"BrickPortrait_{model['id']}")
    document.Label = f"{model['id']} / {model['name']}"
    document.Author = "Copilot Brick Display contributors"
    document.Comment = "Digital prototype. Commercial and printed physical fit is unverified."
    root = document.addObject("App::DocumentObjectGroup", "Design")
    root.addProperty("App::PropertyString", "ParametersSHA256")
    root.ParametersSHA256 = c["parameters_sha256"]
    root.addProperty("App::PropertyString", "Units")
    root.Units = "mm"
    root.addProperty("App::PropertyString", "Status")
    root.Status = "Physical fit, stability, and printer settings NOT verified"
    groups = {}
    for step in model["steps"]:
        group = document.addObject("App::DocumentObjectGroup", f"Step_{step['number']:02d}")
        group.Label = f"{step['number']:02d} | {step['title']}"
        root.addObject(group)
        groups[step["number"]] = group
    objects = []
    assembled = []
    for item in model["placements"]:
        obj = document.addObject("Part::Feature", item["id"].replace("-", "_"))
        obj.Label = f"{item['id']} | {item['part']} | {item['color']}"
        obj.Shape = shapes[item["part"]]
        obj.Placement = placement_for(item)
        for name, value in (("PartID", item["part"]), ("InstanceID", item["id"]),
                            ("ColorName", item["color"]), ("PrintUnits", "mm")):
            obj.addProperty("App::PropertyString", name)
            setattr(obj, name, value)
        obj.addProperty("App::PropertyInteger", "AssemblyStep")
        obj.AssemblyStep = item["step"]
        obj.ViewObject.ShapeColor = html_color(c["colors"][item["color"]]["hex"])
        obj.ViewObject.LineColor = (0.1, 0.15, 0.2)
        if item["part"] == "MSG-CARD":
            base_color = html_color(c["colors"]["cyan"]["hex"])
            text_color = html_color(c["colors"]["black"]["hex"])
            obj.ViewObject.DiffuseColor = [
                text_color if face.CenterOfMass.z > c["message"]["card_thickness"] + 0.001
                else base_color for face in shapes["MSG-CARD"].Faces
            ]
        groups[item["step"]].addObject(obj)
        objects.append(obj)
        assembled.append(obj.Shape.copy())
    document.recompute()
    folder = output / model["id"]
    folder.mkdir(parents=True, exist_ok=True)
    document.saveAs(str(folder / f"{model['id']}.FCStd"))
    Import.export(objects, str(folder / f"{model['id']}.step"))
    compound = Part.makeCompound(assembled)
    model["bounds"] = bounds_list(compound)
    model["actual_mm"] = [round(high - low, 3) for low, high in zip(*model["bounds"])]
    model["cad_solid_volume_mm3"] = round(sum(s.Volume for s in assembled), 3)
    model["center_of_material_mm"] = [
        round(sum(s.Volume * tuple(s.CenterOfMass)[axis] for s in assembled) /
              sum(s.Volume for s in assembled), 4) for axis in range(3)
    ]
    model["center_note"] = "Uniform solid-CAD material only; not sliced mass or proven stability."
    with (folder / "bom.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, ["part", "color", "quantity", "stl"])
        writer.writeheader()
        writer.writerows(model["bom"])
    write_json(folder / "assembly.json", {
        "model": model["id"], "units": "mm", "bounds": model["bounds"],
        "placements": model["placements"], "steps": model["steps"], "bom": model["bom"],
    })
    projections = ROOT / "build/projections" / model["id"]
    projections.mkdir(parents=True, exist_ok=True)
    for name, vector in (("front", App.Vector(0, -1, 0)),
                         ("side", App.Vector(1, 0, 0)),
                         ("top", App.Vector(0, 0, 1))):
        svg = TechDraw.projectToSVG(compound, vector)
        (projections / f"{name}.svg").write_text(svg)
    App.closeDocument(document.Name)
    print(f"NATIVE {model['id']} {model['actual_mm']} / {model['part_count']} parts", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts", nargs="*", help="Generate only named parts; no assemblies.")
    args = parser.parse_args()
    p = load_parameters()
    c = build_catalog(p)
    output = ROOT / "site/downloads"
    fingerprint = hashlib.sha256(
        (ROOT / "design/parameters.json").read_bytes() +
        (ROOT / "scripts/freecad_geometry.py").read_bytes()).hexdigest()[:16]
    cache = ROOT / "build/brep" / fingerprint
    cache.mkdir(parents=True, exist_ok=True)
    shapes = {}
    for key, spec in c["parts"].items():
        if args.parts and key not in args.parts:
            continue
        print(f"PART {key}", flush=True)
        shapes[key] = generate_part(spec, p, cache, output)
    if args.parts:
        write_json(ROOT / "build/interface-proof.json",
                   {key: c["parts"][key] for key in shapes})
        return
    gui = setup_gui()
    for model in c["models"]:
        save_assembly(model, c, shapes, output, gui)
    write_json(ROOT / "design/catalog.json", c)
    write_json(ROOT / "site/assets/catalog.json", c)
    write_json(ROOT / "site/downloads/parameters.json", p)
    write_json(ROOT / "build/freecad-build.json", {
        "freecad_version": App.Version(), "parameters_sha256": c["parameters_sha256"],
        "part_count": len(shapes), "models": [x["id"] for x in c["models"]],
        "cache_fingerprint": fingerprint, "status": "native_saved_not_yet_independently_reopened",
    })


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Offscreen Qt has no OpenGL teardown surface; all files are synchronously saved above.
    os._exit(0)
