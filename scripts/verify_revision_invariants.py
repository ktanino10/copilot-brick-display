"""Check the public template's mechanical contract without private historical inputs."""

import hashlib
import json

from design import ROOT, load_parameters, write_json


def main():
    expected = json.loads((ROOT / "design/public-template-invariants.json").read_text())
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    parameters = load_parameters()
    assert catalog["message"]["lines"] == parameters["message"]["lines"]
    assert catalog["revision"] == parameters["revision"]
    for key, digest in expected["unchanged_nontext_stl_sha256"].items():
        part = catalog["parts"][key]
        assert part["kind"] != "front_plaque"
        data = (ROOT / "site/downloads" / part["stl"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest == part["sha256"], key
    fields = ("id", "part", "color", "position", "rotation", "step", "role", "module", "course")
    for baseline in expected["models"]:
        model = next(model for model in catalog["models"] if model["id"] == baseline["id"])
        assert model["actual_mm"] == baseline["actual_mm"] and model["part_count"] == baseline["part_count"]
        assert [{key: item[key] for key in fields if key in item} for item in model["placements"]] == baseline["placements"]
    policy = json.loads((ROOT / "design/publication-policy.json").read_text())
    write_json(ROOT / "validation/public-template-invariants.json", {
        "status": "PASS_PUBLIC_TEMPLATE_GEOMETRY_BOUNDARIES",
        "revision": catalog["revision"], "parameters_sha256": catalog["parameters_sha256"],
        "unchanged_nontext_masters": len(expected["unchanged_nontext_stl_sha256"]),
        "model_dimensions_and_poses_preserved": True, "public_mode": policy["mode"],
        "unselected_individual_variant": "not_distributed",
        "physical_validation": "NOT_PERFORMED",
    })
    print("PASS public-template geometry boundary: unchanged non-text masters, dimensions and placements.")


if __name__ == "__main__":
    main()
