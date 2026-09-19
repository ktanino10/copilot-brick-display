"""Independent native reopen and final-shape checks, not physical qualification."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict

import FreeCAD as App
import Part

from design import ROOT, write_json
from freecad_geometry import bounds_list, placement_for


def overlap_xy(a, b):
    return min(a.XMax, b.XMax) - max(a.XMin, b.XMin) > 1e-7 and (
        min(a.YMax, b.YMax) - max(a.YMin, b.YMin) > 1e-7)


def overlap_xyz(a, b):
    return overlap_xy(a, b) and min(a.ZMax, b.ZMax) - max(a.ZMin, b.ZMin) > 1e-7


def studs(item, spec, pitch):
    if not spec.get("top_studs"):
        return set()
    nx, ny = spec["studs"]
    x, y, _ = item["position"]
    return {(round(x + (a + 0.5) * pitch, 6), round(y + (b + 0.5) * pitch, 6))
            for a in range(nx) for b in range(ny) if b not in spec.get("reserved_rows", [])}


def socket_grid(item, spec, pitch):
    if not spec.get("socket"):
        return set()
    dx, dy = spec.get("socket_grid_offset", [0, 0])
    translated = {**item, "position": [item["position"][0] + dx,
                                       item["position"][1] + dy, item["position"][2]]}
    return studs(translated, {**spec, "top_studs": True}, pitch)


def verify_model(model, c, pair_cache):
    path = ROOT / "site/downloads" / model["id"] / f"{model['id']}.FCStd"
    doc = App.openDocument(str(path))
    by_id = {o.InstanceID: o for o in doc.Objects if hasattr(o, "InstanceID")}
    expected = {item["id"]: item for item in model["placements"]}
    assert set(by_id) == set(expected), "Native instance set differs from catalogue"
    shapes = {}
    for key, item in expected.items():
        obj = by_id[key]
        assert obj.PartID == item["part"]
        assert obj.ColorName == item["color"] and obj.AssemblyStep == item["step"]
        assert obj.PrintUnits == "mm"
        assert obj.Shape.isValid() and len(obj.Shape.Solids) == 1
        matrix = list(obj.Placement.toMatrix().A)
        target = list(placement_for(item).toMatrix().A)
        assert max(abs(a - b) for a, b in zip(matrix, target)) < 1e-7
        assert abs(obj.Shape.Volume - c["parts"][item["part"]]["volume_mm3"]) < 1e-3
        local = obj.Shape.copy()
        local.Placement = App.Placement()
        expected_bounds = c["parts"][item["part"]]["bounds"]
        assert max(abs(a - b) for left, right in zip(bounds_list(local), expected_bounds)
                   for a, b in zip(left, right)) < 1e-5
        shapes[key] = obj.Shape.copy()
    boxes = {key: shape.optimalBoundingBox(False, False) for key, shape in shapes.items()}
    with zipfile.ZipFile(path) as archive:
        assert "GuiDocument.xml" in archive.namelist(), "Native colors were not saved"
        gui = archive.read("GuiDocument.xml")
        providers = {node.get("name"): node for node in ET.fromstring(gui).iter("ViewProvider")}
        for key, item in expected.items():
            provider = providers[key.replace("-", "_")]
            material = provider.find(".//Property[@name='ShapeAppearance']/MaterialList")
            assert material is not None and material.get("version") == "3"
            data = archive.read(material.get("file"))
            count = struct.unpack_from("<I", data)[0]
            assert len(data) == 4 + 36 * count, "Unexpected native material record schema"
            # v3 stores 24-byte material scalars first, followed by three string lists.
            assert data[4 + 24 * count:] == b"\0" * (12 * count), "Unexpected image/UUID references"
            palette = {struct.unpack_from("<I", data, 8 + 24 * n)[0] for n in range(count)}
            color = (int(c["colors"][item["color"]]["hex"][1:], 16) << 8) | 255
            expected_palette = {color}
            finish = c["parts"][item["part"]].get("letter_color")
            if finish:
                expected_palette.add((int(c["colors"][finish]["hex"][1:], 16) << 8) | 255)
            assert palette == expected_palette, f"Wrong saved native appearance: {key}"
        for name in archive.namelist():
            content = archive.read(name)
            for private in (b"/Users/", b".copilot/attachments", b"session-state/"):
                assert private not in content, f"Private local path in {name}"
    ordered = model["placements"]
    contacts = []
    graph = defaultdict(set)
    pitch = c["interface"]["pitch"]
    for upper in ordered:
        upper_spec = c["parts"][upper["part"]]
        for lower in ordered:
            lower_spec = c["parts"][lower["part"]]
            if not lower_spec.get("top_studs") or not upper_spec.get("socket"):
                continue
            if abs(lower["position"][2] + lower_spec["height"] - upper["position"][2]) > 1e-7:
                continue
            engaged = studs(lower, lower_spec, pitch) & socket_grid(upper, upper_spec, pitch)
            if engaged:
                graph[upper["id"]].add(lower["id"])
                graph[lower["id"]].add(upper["id"])
                contacts.append({"lower": lower["id"], "upper": upper["id"], "studs": len(engaged)})
    modules = [i for i in ordered if i.get("role") == "front_module"]
    bases = [i for i in ordered if i.get("role") == "base_course"]
    for module in modules:
        for base in bases:
            if overlap_xyz(boxes[module["id"]], boxes[base["id"]]):
                graph[base["id"]].add(module["id"])
                graph[module["id"]].add(base["id"])
    visited, todo = set(), [ordered[0]["id"]]
    while todo:
        key = todo.pop()
        if key not in visited:
            visited.add(key)
            todo.extend(graph[key] - visited)
    assert visited == set(expected), f"Disconnected components: {set(expected) - visited}"
    checked_pairs = 0
    unique_booleans = 0
    max_intersection = 0.0
    for index, item in enumerate(ordered):
        shape = shapes[item["id"]]
        for previous in ordered[:index]:
            other = shapes[previous["id"]]
            if overlap_xyz(boxes[item["id"]], boxes[previous["id"]]):
                cache_key = (
                    item["part"], previous["part"], tuple(item["rotation"]), tuple(previous["rotation"]),
                    tuple(round(a - b, 6) for a, b in zip(item["position"], previous["position"])),
                )
                if cache_key not in pair_cache:
                    pair_cache[cache_key] = shape.common(other).Volume
                    unique_booleans += 1
                common = pair_cache[cache_key]
                checked_pairs += 1
                max_intersection = max(max_intersection, common)
                assert common < 1e-5, f"Interference {previous['id']}/{item['id']}: {common}"
            # Earlier tall items may block a downward approach, even without final overlap.
            if previous in bases and item in modules:
                continue
            if overlap_xy(boxes[item["id"]], boxes[previous["id"]]):
                assert (boxes[previous["id"]].ZMax <= boxes[item["id"]].ZMin +
                        c["interface"]["stud_height"] + 1e-6), (
                            f"Vertical insertion obstruction: {previous['id']} -> {item['id']}")
    step_path = path.with_suffix(".step")
    reopened_step = Part.read(str(step_path))
    assert len(reopened_step.Solids) == model["part_count"]
    assert reopened_step.isValid()
    target_bounds = model["bounds"]
    assert max(abs(a - b) for left, right in zip(bounds_list(reopened_step), target_bounds)
               for a, b in zip(left, right)) < 1e-4
    center = model["center_of_material_mm"]
    base_width, base_depth = [value * pitch for value in model["base_studs"]]
    margins = [center[0], base_width - center[0], center[1], base_depth - center[1]]
    assert min(margins) > 0
    result = {
        "model": model["id"], "native_reopened_instances": len(expected),
        "step_reopened_solids": len(reopened_step.Solids), "units": "mm",
        "actual_mm": model["actual_mm"], "appearance_saved": True,
        "connected_components": 1, "stud_engagement_edges": len(contacts),
        "card_connection": "Independent base-front text/logo dovetails with two text keepers and one logo keeper; physical fit untested.",
        "brep_boolean_pairs": checked_pairs, "maximum_intersection_mm3": max_intersection,
        "new_unique_boolean_evaluations": unique_booleans,
        "boolean_cache": "Only identical part IDs, rotations and relative translations; every native local bound was checked.",
        "downward_assembly_access": "analytic bounding sweep + exact final socket/slot solids",
        "cad_material_center_projection_margin_mm": min(margins),
        "physical_fit_and_stability": "NOT TESTED",
        "fcstd_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "step_sha256": hashlib.sha256(step_path.read_bytes()).hexdigest(),
        "contacts": contacts,
    }
    App.closeDocument(doc.Name)
    print(json.dumps({k: v for k, v in result.items() if k != "contacts"}), flush=True)
    return result


def main():
    from verify_revision_invariants import main as verify_invariants
    verify_invariants()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    pair_cache = {}
    baseline = json.loads((ROOT / "design/revision3-invariants.json").read_text())
    report = json.loads(subprocess.check_output([
        "git", "show", f"{baseline['original_commit']}:validation/cad.json"], cwd=ROOT))
    assert report["status"] == "PASS_DIGITAL_ONLY"
    assert all(item["maximum_intersection_mm3"] < 1e-5 for item in report["models"])
    for model in c["models"]:
        face = [item for item in model["placements"] if item.get("role") == "face"]
        for index, item in enumerate(face):
            assert c["parts"][item["part"]]["sha256"] == baseline["unchanged_stl_sha256"][item["part"]]
            for previous in face[:index]:
                key = (item["part"], previous["part"], tuple(item["rotation"]), tuple(previous["rotation"]),
                       tuple(round(a - b, 6) for a, b in zip(item["position"], previous["position"])))
                pair_cache[key] = 0.0
    reused_face_configurations = len(pair_cache)
    results = [verify_model(model, c, pair_cache) for model in c["models"]]
    write_json(ROOT / "validation/cad.json", {
        "status": "PASS_DIGITAL_ONLY", "parameters_sha256": c["parameters_sha256"],
        "freecad": App.Version(), "models": results,
        "unchanged_face_pair_configurations_reused": reused_face_configurations,
        "reuse_basis": "Accepted prior native audit plus byte-identical face meshes and invariant relative poses; revision3-invariants.json is checked separately.",
        "not_claimed": ["physical clutch", "FDM strength", "sliced time/mass",
                        "toy safety", "commercial compatibility certification"],
    })


if __name__ == "__main__":
    main()
