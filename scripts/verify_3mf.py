"""Reopen generic 3MF deliverables in an independent mesh reader."""

import json
import hashlib

import trimesh

from design import ROOT, write_json


def main():
    results = []
    for name in "ABC":
        folder = ROOT / "site/downloads" / name / "plates"
        manifest = json.loads((folder / "manifest.json").read_text())
        total = 0
        files = []
        for plate in manifest["plates"]:
            path = folder / plate["file"]
            scene = trimesh.load_scene(path)
            count = len(scene.graph.nodes_geometry)
            assert count == len(plate["items"]), plate["file"]
            assert min(scene.bounds[0]) >= -0.001
            assert max(scene.bounds[1][:2]) <= 256
            total += count
            files.append({"file": plate["file"], "instances": count,
                          "bounds_mm": scene.bounds.tolist(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        results.append({"model": name, "plate_count": len(files), "instances": total, "files": files})
    write_json(ROOT / "validation/3mf.json", {
        "status": "PASS_INDEPENDENT_3MF_REOPEN", "reader": f"trimesh {trimesh.__version__}",
        "sliced": False, "models": results,
        "note": "Reader, transforms and counts verified; no printer profile, sliced paths, print mass or time validated.",
    })
    count = sum(result["plate_count"] for result in results)
    print(f"PASS all {count} generic 3MF files reopened with exact instance counts and mm bounds.")


if __name__ == "__main__":
    main()
