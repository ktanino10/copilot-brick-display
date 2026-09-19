"""Refresh non-geometric publication metadata only after confirming unchanged measured inputs."""

import hashlib
import json

from design import ROOT, build_catalog, interface_contract, load_parameters, write_json


def main():
    parameters = load_parameters()
    current = json.loads((ROOT / "design/catalog.json").read_text())
    assert current["parameters_sha256"] == hashlib.sha256((ROOT / "design/parameters.json").read_bytes()).hexdigest(), "Regenerate changed CAD inputs before refreshing metadata."
    generated = build_catalog(parameters)
    for key, spec in generated["parts"].items():
        for field, value in spec.items():
            assert current["parts"][key][field] == value, f"Changed geometric part input: {key}/{field}"
    for model in generated["models"]:
        measured = next(item for item in current["models"] if item["id"] == model["id"])
        assert measured["placements"] == model["placements"] and measured["bom"] == model["bom"]
    current["publication"] = generated["publication"]
    write_json(ROOT / "design/catalog.json", current)
    write_json(ROOT / "site/assets/catalog.json", current)
    write_json(ROOT / "design/interface.json", interface_contract(parameters))
    write_json(ROOT / "site/downloads/parameters.json", parameters)
    print("Refreshed publication metadata; measured inputs, geometry, poses and BOM are unchanged.")


if __name__ == "__main__":
    main()
