"""Focused read-only STL section sampling; not a slicer or physical fit test."""

import hashlib
import json

import trimesh
from trimesh.intersections import mesh_plane

from design import ROOT, write_json


def material_at(lines, x, y):
    crossings = 0
    for a, b in lines:
        if (a[1] > y) != (b[1] > y) and a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) > x:
            crossings += 1
    return crossings % 2 == 1


def main():
    manifest = json.loads((ROOT / "site/downloads/trial-subset/manifest.json").read_text())
    records = []
    for part in manifest["parts"]:
        path = ROOT / "site/downloads" / part["stl"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == part["sha256"]
        mesh = trimesh.load_mesh(path)
        assert mesh.is_watertight and mesh.is_volume and mesh.bounds[0, 2] >= -1e-6
        assert abs(mesh.extents[0] - (part["bounds_mm"][1][0] - part["bounds_mm"][0][0])) < .001
        keeper = part["id"] == "NP3-KEEPER"
        base = part["id"].startswith("BASE3-")
        point = [4.01, 12.01] if keeper or base else [4.01, 4.01]
        low = mesh_plane(mesh, [0, 0, 1], [0, 0, .2])
        roof_z = 2.4 if keeper else 8.2
        roof = mesh_plane(mesh, [0, 0, 1], [0, 0, roof_z])
        assert not material_at(low, *point), f"Expected digital cavity sample is blocked: {part['id']}"
        assert material_at(roof, *point), f"Expected modeled roof is missing: {part['id']}"
        footprint = (mesh.extents[:2] + 12).tolist()
        assert max(footprint) < 256
        records.append({
            "part": part["id"], "stl_sha256": part["sha256"],
            "bounds_mm": mesh.bounds.tolist(), "orientation": part["orientation"],
            "positive_mesh_volume_mm3": float(mesh.volume), "watertight": True,
            "reference_xy_mm": point, "z0p2_sample_is_void": True,
            "roof_sample_z_mm": roof_z, "roof_sample_is_material": True,
            "individual_footprint_with_6mm_external_brim_mm": footprint,
        })
    write_json(ROOT / "validation/trial-subset.json", {
        "status": "PASS_UNCHANGED_SELECTION_AND_DIGITAL_SECTION_SAMPLES",
        "geometry_revision": manifest["geometry_revision"], "guidance_revision": manifest["guidance_revision"],
        "selected_masters": len(records), "quantity_per_one_selected_variant": 7,
        "sliced": False, "physical_trial_performed": False,
        "interpretation": "A few digital section points distinguish modeled cavities from roofs. They do not prove all toolpaths, first-layer openings, physical grip, fit or printing success.",
        "records": records,
    })
    print(f"PASS {len(records)} unchanged trial STL; limited cavity/roof samples and individual bed envelopes checked. NOT_SLICED.")


if __name__ == "__main__":
    main()
