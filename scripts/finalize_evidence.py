"""Combine completed evidence and verify artifact hashes; never infer physical success."""

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

from design import ROOT, write_json


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    c = read("design/catalog.json")
    cad = read("validation/cad.json")
    mesh = read("validation/meshes.json")
    packages = read("validation/print-packages.json")
    three_mf = read("validation/3mf.json")
    web = read("validation/web.json")
    assert cad["status"] == mesh["status"] == "PASS_DIGITAL_ONLY"
    assert packages["status"] == "PASS_GEOMETRY_AND_QUANTITIES_ONLY"
    assert three_mf["status"] == "PASS_INDEPENDENT_3MF_REOPEN"
    assert web["status"] == "PASS_REAL_BROWSER"
    assert cad["parameters_sha256"] == mesh["parameters_sha256"] == c["parameters_sha256"]
    records = []
    for model in c["models"]:
        key = model["id"]
        folder = ROOT / "site/downloads" / key
        scene = read(f"validation/blender-{key}.json")
        video = read(f"validation/video-{key}.json")
        privacy = read(f"validation/privacy-{key}.json")
        assert scene["status"] == "PASS_NATIVE_REOPEN" and scene["instances"] == model["part_count"]
        assert scene["parameters_sha256"] == c["parameters_sha256"]
        assert scene["native_sha256"] == sha(folder / f"{key}.blend")
        assert video["status"] == "PASS_ACTUAL_RENDER_ENCODE_DECODE"
        assert video["sha256"] == sha(ROOT / "site/media" / f"{key}-assembly.mp4")
        assert privacy["native_private_path_scan"] == "PASS"
        native = next(item for item in cad["models"] if item["model"] == key)
        assert native["fcstd_sha256"] == sha(folder / f"{key}.FCStd")
        assert native["step_sha256"] == sha(folder / f"{key}.step")
        reader = PdfReader(folder / "drawings.pdf")
        assert len(reader.pages) >= len(model["steps"]) + 3
        assert all(page.extract_text().strip() for page in reader.pages)
        records.append({
            "model": key, "cad": native, "blender": scene, "video": video,
            "drawings_pdf_pages": len(reader.pages), "privacy": privacy,
        })
    part_pdf = PdfReader(ROOT / "site/downloads/part-drawings.pdf")
    assert len(part_pdf.pages) == len(c["parts"])
    review = ROOT / "validation/mechanical-review.md"
    assert review.is_file(), "Independent review must be persisted before publication"
    result = {
        "scope": "A/B/C original brick portraits and common message module",
        "digital_checks_passed": True,
        "physical_testing": "NOT_PERFORMED",
        "parameters_sha256": c["parameters_sha256"],
        "mechanical_source_sha256": sha(ROOT / "scripts/freecad_geometry.py"),
        "parts": len(c["parts"]), "mesh_checks": mesh,
        "models": records, "print_packages": packages, "three_mf_reopen": three_mf, "browser": web,
        "independent_review": "See repository validation/mechanical-review.md; physical gates remain open.",
        "not_claimed": ["Commercial compatibility guarantee", "Physical clutch/strength/tip testing",
                        "Slicer-measured print mass/time", "Toy safety or manufacturing certification",
                        "Official LEGO/GitHub/Bambu product"],
    }
    write_json(ROOT / "site/downloads/validation.json", result)
    print(f"Aggregated genuine checks for {len(records)} models and {len(c['parts'])} unique meshes.")


if __name__ == "__main__":
    main()
