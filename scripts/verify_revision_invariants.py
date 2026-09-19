"""Prove unchanged faces, approved B geometry, exact text and the untouched tribute."""

import hashlib
import json
from collections import Counter

from design import ROOT, write_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = json.loads((ROOT / "design/revision3-invariants.json").read_text())
    approval = json.loads((ROOT / "design/revision3-approval.json").read_text())
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    face_counts = {}
    for model in catalog["models"]:
        expected = Counter((item["part"], item["color"], tuple(item["rotation"]),
                            tuple(round(x + d, 6) for x, d in zip(item["position"], frozen["face_translation_mm"])))
                           for item in frozen["faces"][model["id"]])
        actual = Counter((item["part"], item["color"], tuple(item["rotation"]), tuple(item["position"]))
                         for item in model["placements"] if item.get("role") == "face")
        assert actual == expected, f"Face changed beyond approved translation: {model['id']}"
        face_counts[model["id"]] = sum(actual.values())
    for key, expected in frozen["unchanged_stl_sha256"].items():
        assert catalog["parts"][key]["sha256"] == expected
        assert sha(ROOT / "site/downloads" / catalog["parts"][key]["stl"]) == expected
    for relative, expected in frozen["frozen_tribute"].items():
        assert sha(ROOT / relative) == expected, f"Frozen tribute changed: {relative}"
    b = next(model for model in catalog["models"] if model["id"] == "B")
    assert b["actual_mm"] == approval["actual_mm"]
    assert [{k: item[k] for k in ("id", "part", "color", "position", "rotation")}
            for item in b["placements"]] == approval["B_placements"]
    for key, expected in approval["B_part_sha256"].items():
        assert catalog["parts"][key]["sha256"] == expected, f"Approved B shape changed: {key}"
    assert catalog["message"]["lines"] == approval["lines"]
    assert all(not key.startswith(("MSG-", "NP2-")) for key in catalog["parts"])
    write_json(ROOT / "validation/revision3-invariants.json", {
        "status": "PASS_APPROVED_B_AND_UNCHANGED_FACES_TRIBUTE",
        "revision": catalog["revision"], "parameters_sha256": catalog["parameters_sha256"],
        "face_only_translation_mm": [0, 0, 38.4], "face_instances": face_counts,
        "unchanged_face_meshes": len(frozen["unchanged_stl_sha256"]),
        "frozen_tribute_files": len(frozen["frozen_tribute"]),
        "approved_B_geometry": "All instance poses, colors, part mesh hashes and exterior dimensions unchanged from approved preview.",
        "message_lines": catalog["message"]["lines"], "physical_validation": "NOT_PERFORMED",
    })
    print("PASS approved B, translated-but-unchanged faces and all frozen tribute files.")


if __name__ == "__main__":
    main()
