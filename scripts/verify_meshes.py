"""Validate delivered binary STL meshes using an independent mesh library."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

from design import ROOT, write_json


def vertex_links_are_cycles(mesh):
    links = defaultdict(list)
    for a, b, c in mesh.faces:
        links[a].append((b, c))
        links[b].append((a, c))
        links[c].append((a, b))
    for edges in links.values():
        graph = defaultdict(set)
        for a, b in edges:
            graph[a].add(b)
            graph[b].add(a)
        if any(len(neighbors) != 2 for neighbors in graph.values()):
            return False
        seen, queue = set(), [next(iter(graph))]
        while queue:
            vertex = queue.pop()
            if vertex not in seen:
                seen.add(vertex)
                queue.extend(graph[vertex] - seen)
        if len(seen) != len(graph):
            return False
    return True


def main():
    c = json.loads((ROOT / "design/catalog.json").read_text())
    records = []
    for key, part in c["parts"].items():
        path = ROOT / "site/downloads" / part["stl"]
        mesh = trimesh.load_mesh(path, process=True)
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume, key
        assert np.isfinite(mesh.vertices).all(), key
        assert mesh.volume > 0 and len(mesh.split()) == 1, key
        assert vertex_links_are_cycles(mesh), f"Non-manifold vertex fan: {key}"
        assert np.max(np.abs(mesh.bounds - np.asarray(part["bounds"]))) < 0.03, key
        assert abs(mesh.volume - part["volume_mm3"]) / part["volume_mm3"] < 0.004, key
        assert hashlib.sha256(path.read_bytes()).hexdigest() == part["sha256"], key
        assert mesh.bounds[0, 2] >= -1e-6, key
        footprint_with_brim = mesh.extents[:2] + 12
        assert np.max(footprint_with_brim) <= 256, key
        records.append({
            "part": key, "watertight": True, "winding_consistent": True,
            "connected_bodies": 1, "positive_volume_mm3": round(float(mesh.volume), 4),
            "vertex_manifold": True,
            "bounds_mm": mesh.bounds.tolist(), "triangles": len(mesh.faces),
            "bed_envelope_with_6mm_brim_mm": footprint_with_brim.tolist(),
        })
    write_json(ROOT / "validation/meshes.json", {
        "status": "PASS_DIGITAL_ONLY", "library": f"trimesh {trimesh.__version__}",
        "units": "mm (STL has no intrinsic unit tag; catalogue and header specify mm)",
        "parameters_sha256": c["parameters_sha256"], "parts": records,
    })
    print(f"PASS: {len(records)} unique STL meshes, manifold, positive, connected, mm bounds")


if __name__ == "__main__":
    main()
