"""Export print-local masters and the assembled native document from one catalog."""
import json
from pathlib import Path

import FreeCAD as App
import Import
import MeshPart
import Part


def rgb(hex_color):
    return tuple(int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5))


def export_artifacts(root, data, specs, raw_shapes, instance_specs):
    for folder in ("meshes", "native/parts", "validation"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("CharacterTribute")
    doc.Label = "Character tribute / T1 / mm"
    assembly = doc.addObject("App::Part", "Assembly")
    inputs = doc.addObject("App::FeaturePython", "DesignInputs")
    inputs.addProperty("App::PropertyString", "CanonicalSource").CanonicalSource = "parameters.json"
    inputs.addProperty("App::PropertyString", "ParametersJSON").ParametersJSON = json.dumps(data, ensure_ascii=False)
    print_shapes, parts = {}, []
    for part_id, raw_shape in raw_shapes.items():
        print(f"CAD_EXPORT_PART {part_id}", flush=True)
        shape = raw_shape.copy()
        b = shape.BoundBox
        origin = [b.XMin, b.YMin, b.ZMin]
        shape.translate(-App.Vector(*origin))
        # Preserve analytic faces, but put the translated shell inside an identity-location solid.
        if len(shape.Shells) != 1:
            raise ValueError(f"Expected one connected boundary shell: {part_id}")
        shape = Part.makeSolid(shape.Shells[0])
        if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
            raise ValueError(f"Invalid export solid: {part_id}")
        mesh = MeshPart.meshFromShape(
            Shape=shape, LinearDeflection=data["print"]["linear_deflection"],
            AngularDeflection=data["print"]["angular_deflection"], Relative=False)
        if not mesh.isSolid():
            raise ValueError(f"Open mesh: {part_id}")
        mesh.write(str(root / "meshes" / f"{part_id}.stl"))
        shape.exportStep(str(root / "native/parts" / f"{part_id}.step"))
        print_shapes[part_id] = shape
        parts.append({
            **specs[part_id], "id": part_id, "print_origin_mm": origin,
            "bounds_mm": [b.XLength, b.YLength, b.ZLength],
            "cad_volume_mm3": shape.Volume, "facets": mesh.CountFacets,
            "mesh": f"meshes/{part_id}.stl", "step": f"native/parts/{part_id}.step",
            "quantity": sum(item["part"] == part_id for item in instance_specs)
        })
    catalog_parts = {part["id"]: part for part in parts}
    instances, objects = [], []
    for item in instance_specs:
        part = catalog_parts[item["part"]]
        rotation = App.Rotation(App.Vector(1, 0, 0), item.get("rotation_x_deg", 0))
        translation = App.Vector(*item["position_mm"])
        translation += rotation.multVec(App.Vector(*part["print_origin_mm"]))
        placement = App.Placement(translation, rotation)
        obj = doc.addObject("PartDesign::Feature", item["id"].replace("-", "_"))
        obj.Label = f"{part['id']} {part['name_ja']} ({item['id']})"
        obj.Shape = print_shapes[part["id"]]
        obj.Placement = placement
        for name, value in (("PartID", part["id"]), ("InstanceID", item["id"]),
                            ("PrintFile", part["mesh"]), ("ColorName", part["color"]),
                            ("ParentID", item.get("parent") or "")):
            obj.addProperty("App::PropertyString", name, "Fabrication")
            setattr(obj, name, value)
        obj.addProperty("App::PropertyInteger", "AssemblyStep", "Fabrication").AssemblyStep = item["step"]
        obj.ViewObject.ShapeColor = rgb(data["colors"][part["color"]]["hex"])
        obj.ViewObject.LineColor = (0.1, 0.12, 0.14)
        assembly.addObject(obj)
        objects.append(obj)
        instances.append({**item, "position_mm": list(translation),
                          "rotation_deg_xyz": [item.get("rotation_x_deg", 0), 0, 0]})
    doc.recompute()
    print("CAD_SAVE_NATIVE", flush=True)
    doc.saveAs(str(root / "native/character-tribute.FCStd"))
    print("CAD_EXPORT_ASSEMBLY_STEP", flush=True)
    Import.export(objects, str(root / "native/character-tribute.step"))
    print("CAD_CLOSE_NATIVE", flush=True)
    App.closeDocument(doc.Name)
    catalog = {"schema_version": 1, "project": data["project"], "revision": data["revision"],
               "units": "mm", "axes": "X right, Y rear, Z up; front camera looks toward +Y",
               "message": data["message"], "colors": data["colors"],
               "parts": parts, "instances": instances,
               "native_reopened": False, "native_instance_count": len(objects)}
    (root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    return catalog
