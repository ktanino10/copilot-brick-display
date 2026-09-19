"""Actual per-part projections, exploded projections, and interface sections."""

import json

import FreeCAD as App
import Part
import TechDraw

from design import ROOT, load_parameters
from freecad_geometry import placement_for, shape_for


def project(shape, direction, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TechDraw.projectToSVG(shape, App.Vector(*direction)))


def main():
    c = json.loads((ROOT / "design/catalog.json").read_text())
    build = json.loads((ROOT / "build/freecad-build.json").read_text())
    cache = ROOT / "build/brep" / build["cache_fingerprint"]
    shapes = {}
    for key in c["parts"]:
        shape = Part.Shape()
        shape.read(str(cache / f"{key}.brep"))
        shapes[key] = shape
        for view, direction in [("front", (0, -1, 0)), ("side", (1, 0, 0)), ("top", (0, 0, 1)),
                                ("bottom", (0, 0, -1))]:
            project(shape, direction, ROOT / "build/projections/parts" / key / f"{view}.svg")
        print("PART_DRAWING", key, flush=True)
    for model in c["models"]:
        final = []
        for item in model["placements"]:
            shape = shapes[item["part"]].copy()
            shape.Placement = placement_for(item)
            final.append(shape)
        compound = Part.makeCompound(final)
        for view, direction in [("front", (0, -1, 0)), ("side", (1, 0, 0)), ("top", (0, 0, 1))]:
            print("MODEL_DRAWING", model["id"], view, flush=True)
            project(compound, direction, ROOT / "build/projections" / model["id"] / f"{view}.svg")
        exploded = []
        for item in model["placements"]:
            if item["part"].startswith("MSG-"):
                continue
            shape = shapes[item["part"]].copy()
            shape.Placement = placement_for(item)
            shape.translate(App.Vector(0, 0, (item["step"] - 1) * 6.4))
            exploded.append(shape)
        compound = Part.makeCompound(exploded)
        model["exploded_height_mm"] = compound.BoundBox.ZLength
        project(compound, (0, -1, 0), ROOT / "build/projections" / model["id"] / "exploded.svg")
    p = load_parameters()
    lower = shape_for({"id": "SECTION", "kind": "brick", "studs": [2, 2],
                       "height": 9.6, "top_studs": True, "socket": True}, p, ROOT)
    upper = lower.copy()
    upper.translate(App.Vector(0, 0, 9.6))
    section_plane = Part.Face(Part.makePolygon([
        App.Vector(-10, 4, -10), App.Vector(40, 4, -10), App.Vector(40, 4, 40),
        App.Vector(-10, 4, 40), App.Vector(-10, 4, -10),
    ]))
    joint_plane = Part.makePlane(50, 50, App.Vector(-10, -10, 10.5), App.Vector(0, 0, 1))
    folder = ROOT / "build/projections/interface"
    for label, shape in [("lower", lower), ("upper", upper)]:
        project(shape.section(section_plane), (0, -1, 0), folder / f"{label}-section.svg")
        project(shape.section(joint_plane), (0, 0, 1), folder / f"{label}-plan.svg")
    (ROOT / "build/drawing-metadata.json").write_text(json.dumps({
        "exploded_heights": {model["id"]: model["exploded_height_mm"] for model in c["models"]},
        "section_y_mm": 4, "joint_section_z_mm": 10.5,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
