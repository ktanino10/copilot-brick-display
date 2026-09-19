"""Actual per-part projections, exploded projections, and interface sections."""

import json
import hashlib
import argparse
from pathlib import Path

import FreeCAD as App
import Part
import TechDraw

from design import ROOT, load_parameters
from freecad_geometry import bounds_list, placement_for, shape_for


def project(shape, direction, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TechDraw.projectToSVG(shape, App.Vector(*direction)))


def project_coarse(shape, direction, x_direction, path, mirror_x=False):
    document = App.newDocument("DerivedDrawing")
    source = document.addObject("Part::Feature", "ActualSolid")
    shape.tessellate(.025)
    source.Shape = shape
    page = document.addObject("TechDraw::DrawPage", "Page")
    template = document.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = str(ROOT / "resources/orthographic-template.svg")
    page.Template = template
    view = document.addObject("TechDraw::DrawViewPart", "Projection")
    view.Source = [source]
    view.Direction = App.Vector(*direction)
    view.XDirection = App.Vector(*x_direction)
    view.CoarseView = True
    view.Scale = 1
    page.addView(view)
    document.recompute()
    svg = TechDraw.viewPartAsSvg(view)
    if not svg:
        raise ValueError(f"Empty native coarse HLR: {path.name}")
    center = view.projectPoint(view.getGeometricCenter())
    mirror = 'transform="scale(-1,1)"' if mirror_x else ""
    svg = (f'<g data-coordinate-system="screen" {mirror}><g transform="translate({center.x},{-center.y})">'
           f"{svg}</g></g>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg)
    App.closeDocument(document.Name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-baseline", type=Path, help="Optional local previous catalogue for byte-identical part projection reuse.")
    args = parser.parse_args()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    build = json.loads((ROOT / "build/freecad-build.json").read_text())
    cache = ROOT / "build/brep" / build["cache_fingerprint"]
    shapes = {}
    previous_file = args.reuse_baseline / "design/catalog.json" if args.reuse_baseline else None
    previous = json.loads(previous_file.read_text()) if previous_file and previous_file.is_file() else {"parts": {}}
    reused = []
    for key in c["parts"]:
        shape = Part.Shape()
        shape.read(str(cache / f"{key}.brep"))
        shapes[key] = shape
        for view, direction in [("front", (0, -1, 0)), ("side", (1, 0, 0)), ("top", (0, 0, 1)),
                                ("bottom", (0, 0, -1))]:
            path = ROOT / "build/projections/parts" / key / f"{view}.svg"
            if previous["parts"].get(key, {}).get("sha256") == c["parts"][key]["sha256"] and path.exists():
                reused.append({"part": key, "view": view, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                continue
            if c["parts"][key]["kind"].startswith("front_"):
                x_direction = (0, 1, 0) if view == "side" else (-1, 0, 0) if view == "bottom" else (1, 0, 0)
                project_coarse(shape, direction, x_direction, path, view == "bottom")
            else:
                project(shape, direction, path)
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
            project_coarse(compound, direction, (0, 1, 0) if view == "side" else (1, 0, 0),
                           ROOT / "build/projections" / model["id"] / f"{view}.svg")
        exploded = []
        display = next(state for state in json.loads((ROOT / "build/display-states.json").read_text())
                       if state["model"] == model["id"] and state["percent"] == 100)
        for item in model["placements"]:
            shape = shapes[item["part"]].copy()
            shape.Placement = placement_for(item)
            shape.translate(App.Vector(*display["offsets"][item["id"]]))
            exploded.append(shape)
        compound = Part.makeCompound(exploded)
        model["exploded_bounds"] = bounds_list(compound)
        model["exploded_height_mm"] = model["exploded_bounds"][1][2] - model["exploded_bounds"][0][2]
        project_coarse(compound, (0, -1, 0), (1, 0, 0),
                       ROOT / "build/projections" / model["id"] / "exploded.svg")
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
    model = next(m for m in c["models"] if m["id"] == "B")
    groups = {"base": [], "modules": []}
    for item in model["placements"]:
        if item.get("role") not in ("base_course", "front_module", "keeper"):
            continue
        shape = shapes[item["part"]].copy()
        shape.Placement = placement_for(item)
        groups["modules" if item["role"] == "front_module" else "base"].append(shape)
    plane = Part.makePlane(194, 8, App.Vector(-1, -1, 24), App.Vector(0, 0, 1))
    side_plane = Part.Face(Part.makePolygon([
        App.Vector(40, -1, -1), App.Vector(40, 8, -1), App.Vector(40, 8, 54),
        App.Vector(40, -1, 54), App.Vector(40, -1, -1)]))
    for name, group in groups.items():
        shape = Part.makeCompound(group)
        project(shape.section(plane), (0, 0, 1), folder / f"front-{name}-plan.svg")
        project(shape.section(side_plane), (1, 0, 0), folder / f"front-{name}-side.svg")
    (ROOT / "build/drawing-metadata.json").write_text(json.dumps({
        "exploded_heights": {model["id"]: model["exploded_height_mm"] for model in c["models"]},
        "exploded_bounds": {model["id"]: model["exploded_bounds"] for model in c["models"]},
        "assembly_projection": "Real FreeCAD TechDraw coarse HLR; exact BREP dimensions; tessellation requested0.025mm",
        "unchanged_part_projections_reused": reused,
        "section_y_mm": 4, "joint_section_z_mm": 10.5,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
