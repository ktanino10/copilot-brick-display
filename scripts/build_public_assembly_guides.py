"""Build only generic A/B/C guide derivatives; never regenerate manufacturing or Blender files."""

import json
from pathlib import Path
import shutil
import zipfile

from build_assembly_guide import ROOT, GUIDE_REVISION, build_mapping, digest, read_json, write_guide


def main():
    policy = read_json(ROOT / "design/publication-policy.json")
    if policy["mode"] != "generic" or policy["public_text_approved"] is not False:
        raise ValueError("This public-project wrapper only builds the explicit generic default.")
    catalog_path = ROOT / "design/catalog.json"
    catalog = read_json(catalog_path)
    if catalog["message"]["lines"] != policy["generic_lines"]:
        raise ValueError("Generic message and publication policy differ")
    output = ROOT / "site/assembly-guide"
    output.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "build/assembly-guide/runtime.js"
    results = []
    for model in ("A", "B", "C"):
        folder = ROOT / "site/downloads" / model
        assembly_path, plates_path = folder / "assembly.json", folder / "plates/manifest.json"
        data, meshes = build_mapping(catalog, read_json(assembly_path), read_json(plates_path),
                                    ROOT / "site/downloads", folder / "plates")
        data["inputs_sha256"] = {"catalog": digest(catalog_path.read_bytes()),
                                "assembly": digest(assembly_path.read_bytes()), "plates": digest(plates_path.read_bytes())}
        write_guide(data, meshes, output / f"{model}.html", runtime, ROOT / "web/assembly-guide")
        standalone = ROOT / "build/assembly-guide" / f"{model}-offline.html"
        write_guide(data, meshes, standalone, runtime, ROOT / "web/assembly-guide", standalone=True)
        with zipfile.ZipFile(output / f"{model}-offline.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in (
                ("index.html", standalone.read_bytes()),
                ("mapping.json", standalone.with_suffix(".mapping.json").read_bytes()),
                ("THREE-LICENSE.txt", (ROOT / "site/vendor/THREE-LICENSE.txt").read_bytes()),
            ):
                info = zipfile.ZipInfo(name, date_time=(2026, 9, 20, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        results.append({"model": model, "occurrences": data["part_count"], "plates": len(data["plates"]),
                        "first_source": data["first_source"], "base_source_files": data["base_source_files"],
                        "mesh_hashes": {key: value["sha256"] for key, value in data["parts"].items()}})
        print(f"{model}: {data['part_count']} exact occurrences / {len(data['plates'])} plates / offline HTML ready", flush=True)
    shutil.copyfile(ROOT / "web/assembly-guide/index.html", output / "index.html")
    (ROOT / "validation/assembly-guide-mapping.json").write_text(json.dumps({
        "status": "PASS_REAL_STL_3MF_PLACEMENT_MAPPING", "guide_revision": GUIDE_REVISION,
        "geometry_revision": catalog["revision"], "models": results,
        "manufacturing_inputs_changed": False, "sliced": False, "physical_fit_tested": False,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
