"""Independent binary-STL topology, orientation, volume and print-envelope checks."""
from collections import defaultdict
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def read_stl(path):
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError(f"Truncated STL: {path}")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError(f"STL is not the expected binary length: {path}")
    vertices, faces, indices = [], [], {}
    for offset in range(84, len(data), 50):
        record = struct.unpack_from("<12fH", data, offset)
        face = []
        for start in (3, 6, 9):
            vertex = tuple(record[start:start + 3])
            if not all(math.isfinite(value) for value in vertex):
                raise ValueError(f"Nonfinite vertex in {path}")
            if vertex not in indices:
                indices[vertex] = len(vertices)
                vertices.append(vertex)
            face.append(indices[vertex])
        faces.append(tuple(face))
    return vertices, faces


def audit(path):
    vertices, faces = read_stl(path)
    edges, links, terms = defaultdict(list), defaultdict(list), []
    for index, (a, b, c) in enumerate(faces):
        if len({a, b, c}) != 3:
            raise ValueError(f"Degenerate triangle in {path}")
        p, q, r = [vertices[v] for v in (a, b, c)]
        u, v = [q[i] - p[i] for i in range(3)], [r[i] - p[i] for i in range(3)]
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        if sum(value * value for value in cross) < 1e-18:
            raise ValueError(f"Zero-area triangle in {path}")
        terms.append((p[0]*(q[1]*r[2]-q[2]*r[1]) +
                      p[1]*(q[2]*r[0]-q[0]*r[2]) +
                      p[2]*(q[0]*r[1]-q[1]*r[0])) / 6)
        for start, end in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((start, end)))].append((index, 1 if start < end else -1))
        links[a].append((b, c))
        links[b].append((c, a))
        links[c].append((a, b))
    neighbors = defaultdict(list)
    for incident in edges.values():
        if len(incident) != 2 or sum(direction for _, direction in incident):
            raise ValueError(f"Open/nonmanifold/inconsistently oriented edge in {path}")
        a, b = [index for index, _ in incident]
        neighbors[a].append(b)
        neighbors[b].append(a)
    pending, reached = [0], set()
    while pending:
        face = pending.pop()
        if face not in reached:
            reached.add(face)
            pending.extend(neighbors[face])
    if len(reached) != len(faces):
        raise ValueError(f"Multiple disconnected mesh shells in {path}")
    for vertex, pairs in links.items():
        ring = defaultdict(set)
        for a, b in pairs:
            ring[a].add(b)
            ring[b].add(a)
        if any(len(value) != 2 for value in ring.values()):
            raise ValueError(f"Nonmanifold vertex link at {vertex} in {path}")
        seen, queue = set(), [next(iter(ring))]
        while queue:
            node = queue.pop()
            if node not in seen:
                seen.add(node)
                queue.extend(ring[node] - seen)
        if len(seen) != len(ring):
            raise ValueError(f"Pinched vertex link in {path}")
    volume = math.fsum(terms)
    if volume <= 0:
        raise ValueError(f"Nonpositive signed volume in {path}")
    minimum = [min(point[i] for point in vertices) for i in range(3)]
    maximum = [max(point[i] for point in vertices) for i in range(3)]
    return {"vertices": len(vertices), "triangles": len(faces), "shells": 1,
            "closed_2_manifold": True, "consistent_winding": True,
            "signed_volume_mm3": volume, "bounds_mm": [minimum, maximum]}


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    data = json.loads((ROOT / "parameters.json").read_text())
    reports = {}
    bound_tolerance = data["print"]["linear_deflection"] + 2e-4
    for part in catalog["parts"]:
        report = audit(ROOT / part["mesh"])
        minimum, maximum = report["bounds_mm"]
        if any(abs(value) > bound_tolerance for value in minimum):
            raise ValueError(f"STL print origin is not zero: {part['id']}")
        if any(abs(a - b) > bound_tolerance for a, b in zip(maximum, part["bounds_mm"])):
            raise ValueError(f"CAD/STL bounds mismatch: {part['id']}")
        error = abs(report["signed_volume_mm3"] / part["cad_volume_mm3"] - 1)
        if error > .02:
            raise ValueError(f"Excessive tessellation volume error: {part['id']}")
        envelope = [maximum[0] + 2*data["print"]["brim"],
                    maximum[1] + 2*data["print"]["brim"], maximum[2]]
        if any(a > b for a, b in zip(envelope, data["print"]["bed"])):
            raise ValueError(f"Part plus brim exceeds the bed: {part['id']}")
        report.update({"cad_volume_relative_error": error, "brim_envelope_mm": envelope,
                       "bed_bounds_pass": True, "tessellation_bounds_tolerance_mm": bound_tolerance})
        reports[part["id"]] = report
    result = {"status": "pass", "units": "mm", "parts_checked": len(reports),
              "method": "Independent binary STL parser; edge and vertex-link manifoldness; signed tetrahedral volume.",
              "bed_scope": "Axis-aligned part plus 8 mm brim inside nominal 256 mm cube; slicer exclusion regions still need checking.",
              "parts": reports}
    (ROOT / "validation/meshes.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"MESH_AUDIT_PASS {len(reports)} parts")


if __name__ == "__main__":
    main()
