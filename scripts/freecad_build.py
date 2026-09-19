"""Run with FreeCAD's Python and lib directory on PYTHONPATH; see docs/rebuild.md."""

from __future__ import annotations

import argparse
import ast
import csv
import faulthandler
import hashlib
import json
import math
import os
import shutil
import struct
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part
import TechDraw

from design import ROOT, build_catalog, interface_contract, load_parameters, write_json
from freecad_geometry import bounds_list, build_brick, placement_for, shape_for


def log(*values):
    print(*values, file=sys.__stdout__, flush=True)


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
    App.ParamGet("User parameter:BaseApp/Preferences/Document").SetBool("SaveThumbnail", False)
    App.ParamGet("User parameter:BaseApp/Preferences/General").SetString("AutoloadModule", "PartWorkbench")
    log("GUI_INIT")
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    log("GUI_READY")
    return Gui


MEASURED_FIELDS = ("bounds", "volume_mm3", "mesh_triangles", "mesh_linear_deflection_mm", "sha256", "local_center_mm")


def brick_functions(source):
    tree = ast.parse(source)
    names = {"socket_cutter", "supports", "stud_shape", "build_brick"}
    return {node.name: ast.dump(node, include_attributes=False)
            for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names}


def front_geometry_functions(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            node.exc.args = [ast.Constant(value="diagnostic message")]
    return [ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, ast.FunctionDef)]


def front_geometry_parameters(parameters):
    message = {key: value for key, value in parameters["message"].items()
               if key not in {"lines", "frozen_legacy_interface", "legacy_variant_distribution"}}
    return {"interface": parameters["interface"], "message": message, "logo": parameters.get("logo")}


def generate_part(spec, p, cache, output, reuse):
    cache_path = cache / f"{spec['id']}.brep"
    previous = reuse.get("parts", {}).get(spec["id"])
    reusable = (reuse["brick_unchanged"] and spec["kind"] in ("brick", "male_coupon", "female_coupon")) or (
        reuse.get("front_unchanged") and spec["kind"] in
        ("front_base", "front_logo", "front_keeper", "front_fit_socket", "front_fit_plaque"))
    if previous and reusable:
        geometry_keys = tuple(key for key in spec if key not in MEASURED_FIELDS)
        if all(spec.get(key) == previous.get(key) for key in geometry_keys):
            old_brep = reuse["cache"] / f"{spec['id']}.brep"
            filename = output / spec["stl"]
            source_mesh = filename if filename.is_file() else reuse.get("meshes", ROOT / "site/downloads") / spec["stl"]
            if old_brep.exists() and source_mesh.exists() and hashlib.sha256(source_mesh.read_bytes()).hexdigest() == previous["sha256"]:
                if old_brep != cache_path:
                    shutil.copyfile(old_brep, cache_path)
                filename.parent.mkdir(parents=True, exist_ok=True)
                if source_mesh != filename:
                    shutil.copyfile(source_mesh, filename)
                shape = Part.Shape()
                shape.read(str(cache_path))
                spec.update({key: previous[key] for key in MEASURED_FIELDS})
                reuse["reused"].append(spec["id"])
                return shape
    if cache_path.exists():
        shape = Part.Shape()
        shape.read(str(cache_path))
    else:
        if spec["kind"].startswith("front_"):
            from front_nameplate import shape_for_front
            shape = shape_for_front(spec, p, lambda raw, parameters: cached_brick(raw, parameters, reuse))
        else:
            shape = shape_for(spec, p, ROOT)
        shape.exportBrep(str(cache_path))
    if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
        raise ValueError(f"Invalid cached solid: {spec['id']}")
    cached_stl, cached_meta = cache / f"{spec['id']}.stl", cache / f"{spec['id']}.json"
    filename = output / spec["stl"]
    filename.parent.mkdir(parents=True, exist_ok=True)
    if cached_stl.is_file() and cached_meta.is_file():
        metadata = json.loads(cached_meta.read_text())
        if hashlib.sha256(cached_stl.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Corrupt cached mesh: {spec['id']}")
        shutil.copyfile(cached_stl, filename)
        spec.update(metadata)
        reuse["reused"].append(spec["id"])
        return shape
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025,
                                  AngularDeflection=math.radians(12), Relative=False)
    triangles = stl_write(mesh, filename)
    spec.update({
        "bounds": bounds_list(shape), "volume_mm3": round(shape.Volume, 6),
        "mesh_triangles": triangles, "mesh_linear_deflection_mm": 0.025,
        "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
        "local_center_mm": list(shape.Solids[0].CenterOfMass),
    })
    shutil.copyfile(filename, cached_stl)
    write_json(cached_meta, {key: spec[key] for key in MEASURED_FIELDS})
    return shape


def cached_brick(spec, parameters, reuse):
    recipe = {"interface": parameters["interface"], "functions": brick_functions((ROOT / "scripts/freecad_geometry.py").read_text())}
    folder = ROOT / "build/brick-primitives" / hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:16]
    folder.mkdir(parents=True, exist_ok=True)
    nx, ny = spec["studs"]
    key = f"BR-{nx:02}x{ny:02}-H{round(spec['height'] * 10):03}"
    identity = {field: spec[field] for field in ("studs", "height", "top_studs", "socket")}
    identity["id"] = key
    path = folder / (hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16] + ".brep")
    if path.is_file():
        shape = Part.Shape()
        shape.read(str(path))
        return shape
    old = reuse.get("cache", folder) / f"{key}.brep"
    if reuse.get("brick_unchanged") and spec["top_studs"] and spec["socket"] and old.is_file():
        shape = Part.Shape()
        shape.read(str(old))
    else:
        shape = build_brick(spec, parameters)
    shape.exportBrep(str(path))
    return shape


def save_assembly(model, c, shapes, output, gui):
    import Import
    log("NATIVE_BEGIN", model["id"])
    document = App.newDocument(f"BrickPortrait_{model['id']}")
    document.Label = f"{model['id']} / {model['name']}"
    document.Meta = {"Author": "Copilot Brick Display contributors"}
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
        part_spec = c["parts"][item["part"]]
        if part_spec["kind"] in ("front_plaque", "front_logo"):
            if part_spec["kind"] == "front_plaque":
                obj.addProperty("App::PropertyString", "MessageLines")
                obj.MessageLines = json.dumps(c["message"]["lines"])
            base_color = html_color(c["colors"]["black"]["hex"])
            text_color = html_color(c["colors"][part_spec["letter_color"]]["hex"])
            obj.ViewObject.DiffuseColor = [
                text_color if face.CenterOfMass.z > part_spec["optional_color_change_z"] + 0.001
                else base_color for face in shapes[item["part"]].Faces
            ]
        groups[item["step"]].addObject(obj)
        objects.append(obj)
        assembled.append(obj.Shape.copy())
    document.recompute()
    # View commands require an active GUI window and can open a modal dialog offscreen.
    # Saving real geometry/view-provider colors does not require them; use V,F on open.
    folder = output / model["id"]
    folder.mkdir(parents=True, exist_ok=True)
    document.saveAs(str(folder / f"{model['id']}.FCStd"))
    log("FCSTD_SAVED", model["id"])
    Import.export(objects, str(folder / f"{model['id']}.step"))
    log("STEP_SAVED", model["id"])
    log(f"NATIVE {model['id']} {model['actual_mm']} / {model['part_count']} parts")


def measure_assembly(model, c, shapes, output):
    assembled, centers, volumes = [], [], []
    for item in model["placements"]:
        shape = shapes[item["part"]].copy()
        transform = placement_for(item)
        shape.Placement = transform
        assembled.append(shape)
        part = c["parts"][item["part"]]
        centers.append(transform.multVec(App.Vector(*part["local_center_mm"])))
        volumes.append(part["volume_mm3"])
    compound = Part.makeCompound(assembled)
    model["bounds"] = bounds_list(compound)
    model["actual_mm"] = [round(high - low, 3) for low, high in zip(*model["bounds"])]
    model["cad_solid_volume_mm3"] = round(sum(volumes), 3)
    model["center_of_material_mm"] = [
        round(sum(volume * tuple(center)[axis] for volume, center in zip(volumes, centers)) /
              sum(volumes), 4) for axis in range(3)
    ]
    model["center_note"] = "Uniform solid-CAD material only; not sliced mass or proven stability."
    folder = output / model["id"]
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "bom.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, ["part", "color", "quantity", "stl", "finish_color", "color_change_z_mm"])
        writer.writeheader()
        writer.writerows(model["bom"])
    write_json(folder / "assembly.json", {
        "model": model["id"], "units": "mm", "bounds": model["bounds"],
        "placements": model["placements"], "steps": model["steps"], "bom": model["bom"],
    })
    log("MEASURED", model["id"], model["actual_mm"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts", nargs="*", help="Generate only named parts; no assemblies.")
    parser.add_argument("--native-only", action="store_true", help="Use measured catalogue and BREP cache to save native files.")
    parser.add_argument("--models", nargs="+", choices=["A", "B", "C"], default=["A", "B", "C"])
    parser.add_argument("--reuse-baseline", type=Path, help="Frozen original source/catalog folder for verified unchanged-part reuse.")
    parser.add_argument("--baseline-cache", type=Path)
    parser.add_argument("--preview-model", choices=["A", "B", "C"])
    parser.add_argument("--reuse-preview", type=Path, help="Reuse byte-verified parts from a matching native prototype.")
    parser.add_argument("--reuse-measured-cache", action="store_true",
                        help="Reuse the last measured cache for metadata/presentation-only changes with identical geometry inputs.")
    args = parser.parse_args()
    p = load_parameters()
    c = build_catalog(p)
    part_inputs = c["parts"]
    output_root = ROOT / "build/np3-preview" if args.preview_model else ROOT
    output = output_root / "downloads" if args.preview_model else ROOT / "site/downloads"
    if args.preview_model:
        c["models"] = [model for model in c["models"] if model["id"] == args.preview_model]
        needed = {item["part"] for model in c["models"] for item in model["placements"]}
        c["parts"] = {key: spec for key, spec in c["parts"].items() if key in needed}
    fingerprint = hashlib.sha256(json.dumps(
        {"recipe": geometry_recipe(p), "part_inputs": part_inputs, "logo": p["logo"]},
        sort_keys=True).encode()).hexdigest()[:16]
    cache = ROOT / "build/brep" / fingerprint
    cache.mkdir(parents=True, exist_ok=True)
    shapes = {}
    reuse = {"reused": [], "brick_unchanged": False}
    if args.reuse_measured_cache:
        previous_catalog = json.loads((ROOT / "design/catalog.json").read_text())
        previous_build = json.loads((ROOT / "build/freecad-build.json").read_text())
        assert previous_catalog["interface"] == p["interface"]
        assert previous_catalog["message"] == p["message"]
        assert previous_build["geometry_recipe"] == geometry_recipe(p), "Mechanical code changed; regenerate affected solids."
        old_cache = ROOT / "build/brep" / previous_build["cache_fingerprint"]
        for key, spec in c["parts"].items():
            old_part = previous_catalog["parts"][key]
            assert all(spec.get(k) == old_part.get(k) for k in spec if k not in MEASURED_FIELDS)
            target = cache / f"{key}.brep"
            if old_cache != cache:
                shutil.copyfile(old_cache / f"{key}.brep", target)
            shapes[key] = Part.Shape()
            shapes[key].read(str(target))
            assert hashlib.sha256((output / spec["stl"]).read_bytes()).hexdigest() == old_part["sha256"]
            spec.update({field: old_part[field] for field in MEASURED_FIELDS})
            spec["bounds"] = bounds_list(shapes[key])
            reuse["reused"].append(key)
    if args.reuse_baseline:
        old = args.reuse_baseline
        old_parameters = json.loads((old / "design/parameters.json").read_text())
        previous_catalog = json.loads((old / "design/catalog.json").read_text())
        previous_build = json.loads((ROOT / "build/freecad-build.json").read_text())
        reuse.update({
            "parts": previous_catalog["parts"],
            "meshes": old / "site/downloads" if (old / "site/downloads").exists() else ROOT / "site/downloads",
            "cache": args.baseline_cache or ROOT / "build/brep" / previous_build["cache_fingerprint"],
            "brick_unchanged": old_parameters["interface"] == p["interface"] and
                brick_functions((old / "scripts/freecad_geometry.py").read_text()) ==
                brick_functions((ROOT / "scripts/freecad_geometry.py").read_text()),
            "front_unchanged": front_geometry_parameters(old_parameters) == front_geometry_parameters(p) and
                front_geometry_functions((old / "scripts/front_nameplate.py").read_text()) ==
                front_geometry_functions((ROOT / "scripts/front_nameplate.py").read_text()),
        })
    if args.reuse_preview:
        previous_catalog = json.loads((args.reuse_preview / "catalog.json").read_text())
        previous_build = json.loads((args.reuse_preview / "freecad-build.json").read_text())
        assert previous_build["geometry_recipe"] == geometry_recipe(p)
        assert previous_catalog["logo"] == p["logo"]
        for key, old_part in previous_catalog["parts"].items():
            if key not in c["parts"]:
                continue
            spec = c["parts"][key]
            assert all(spec.get(field) == old_part.get(field) for field in spec if field not in MEASURED_FIELDS)
            source_mesh = args.reuse_preview / "downloads" / old_part["stl"]
            assert hashlib.sha256(source_mesh.read_bytes()).hexdigest() == old_part["sha256"]
            source_brep = ROOT / "build/brep" / previous_build["cache_fingerprint"] / f"{key}.brep"
            if source_brep != cache / f"{key}.brep":
                shutil.copyfile(source_brep, cache / f"{key}.brep")
            shutil.copyfile(source_mesh, cache / f"{key}.stl")
            write_json(cache / f"{key}.json", {field: old_part[field] for field in MEASURED_FIELDS})
    if args.native_only:
        c = json.loads((ROOT / "design/catalog.json").read_text())
        assert c["parameters_sha256"] == build_catalog(p)["parameters_sha256"]
    for key, spec in c["parts"].items():
        if key in shapes:
            continue
        if args.parts and key not in args.parts:
            continue
        log(f"PART {key}")
        if args.native_only:
            shapes[key] = Part.Shape()
            shapes[key].read(str(cache / f"{key}.brep"))
            assert shapes[key].isValid()
        else:
            shapes[key] = generate_part(spec, p, cache, output, reuse)
    if args.parts:
        write_json(ROOT / "build/interface-proof.json",
                   {key: c["parts"][key] for key in shapes})
        return
    if not args.native_only:
        for model in c["models"]:
            measure_assembly(model, c, shapes, output)
    write_json(output_root / "catalog.json" if args.preview_model else ROOT / "design/catalog.json", c)
    if not args.preview_model:
        write_json(ROOT / "design/interface.json", interface_contract(p))
        write_json(ROOT / "site/assets/catalog.json", c)
        write_json(ROOT / "site/downloads/parameters.json", p)
    gui = setup_gui()
    for model in c["models"]:
        if model["id"] in args.models:
            save_assembly(model, c, shapes, output, gui)
    write_json(output_root / "freecad-build.json" if args.preview_model else ROOT / "build/freecad-build.json", {
        "freecad_version": App.Version(), "parameters_sha256": c["parameters_sha256"],
        "part_count": len(shapes), "models": [x["id"] for x in c["models"]],
        "cache_fingerprint": fingerprint, "status": "native_saved_not_yet_independently_reopened",
        "unchanged_parts_reused_without_meshing": reuse["reused"],
        "brick_function_ast_and_interface_equal": reuse["brick_unchanged"],
        "geometry_recipe": geometry_recipe(p),
    })


def geometry_recipe(parameters):
    return {
        "interface": parameters["interface"], "message": parameters["message"],
        "brick_functions": brick_functions((ROOT / "scripts/freecad_geometry.py").read_text()),
        "front_geometry_sha256": hashlib.sha256((ROOT / "scripts/front_nameplate.py").read_bytes()).hexdigest(),
        "font_sha256": hashlib.sha256((ROOT / parameters["message"]["font"]).read_bytes()).hexdigest(),
        "logo_sha256": hashlib.sha256((ROOT / parameters["logo"]["outline"]).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    faulthandler.dump_traceback_later(180, repeat=True)
    main()
    faulthandler.cancel_dump_traceback_later()
    sys.stdout.flush()
    sys.stderr.flush()
    # Offscreen Qt has no OpenGL teardown surface; all files are synchronously saved above.
    os._exit(0)
