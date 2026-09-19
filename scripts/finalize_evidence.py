"""Combine completed evidence and verify artifact hashes; never infer physical success."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from pypdf import PdfReader

from design import ROOT, write_json


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-browser", action="store_true")
    args = parser.parse_args()
    c = read("design/catalog.json")
    cad = read("validation/cad.json")
    mesh = read("validation/meshes.json")
    packages = read("validation/print-packages.json")
    three_mf = read("validation/3mf.json")
    motion = read("validation/explosion-motion.json")
    browser_file = ROOT / "validation/web.json"
    web = read("validation/web.json") if browser_file.is_file() else {
        "status": "PENDING_CURRENT_REVISION_CI", "revision": None,
        "note": "No current browser execution has been recorded.",
    }
    assert cad["status"] == mesh["status"] == "PASS_DIGITAL_ONLY"
    assert packages["status"] == "PASS_GEOMETRY_AND_QUANTITIES_ONLY"
    assert three_mf["status"] == "PASS_INDEPENDENT_3MF_REOPEN"
    assert motion["status"] == "PASS_REAL_NATIVE_MOTION_CHECK"
    assert all(item["maximum_intersection_mm3"] < 1e-5 for item in motion["models"])
    revision = read("validation/public-template-invariants.json")
    front = read("validation/front-nameplate.json")
    assert revision["status"] == "PASS_PUBLIC_TEMPLATE_GEOMETRY_BOUNDARIES"
    assert front["status"] == "PASS_NATIVE_FRONT_CAPTURE_AND_EXTRACTION"
    current_browser = web["status"] == "PASS_REAL_BROWSER" and web.get("revision") == c["revision"]
    if args.require_browser and not current_browser:
        raise ValueError("A current real-browser pass is required before deployment; pending or historical evidence is insufficient.")
    if current_browser:
        views = web["vertical_explosion"]
        expected_views = {(model["id"], viewport) for model in c["models"] for viewport in ("desktop", "mobile")}
        assert {(view["model"], view["viewport"]) for view in views} == expected_views
        for view in views:
            if view["viewport"] == "mobile":
                assert view.get("viewport_width_px") == 375, "Current phone evidence must be measured at375px."
            assert [state["percent"] for state in view["states"]] == [0, 50, 100]
            assert view["states"][0]["error"] < 1e-7
            assert view["states"][-1]["gap"] >= 9.6
            assert all(state["clip"] <= 1.001 for state in view["states"])
    browser_record = web if current_browser else {
        "status": "PENDING_CURRENT_REVISION_CI", "required_revision": c["revision"],
        "prior_browser_result_not_reused": True,
        "note": "The bounded Linux full-Chrome gate must test this revision before deployment.",
    }
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
        assert all("PUBLIC TEMPLATE / 5-COURSE BASE" in page.extract_text() for page in reader.pages)
        text = "\n".join(page.extract_text() for page in reader.pages)
        assert all(value in text for value in c["message"]["lines"])
        with zipfile.ZipFile(folder / "print-kit.zip") as archive:
            assert archive.read("bom.csv") == (folder / "bom.csv").read_bytes()
            assert archive.read("drawings.pdf") == (folder / "drawings.pdf").read_bytes()
            expected_stls = {c["parts"][item["part"]]["stl"] for item in model["placements"]}
            assert {name for name in archive.namelist() if name.endswith(".stl")} == expected_stls
            for name in expected_stls:
                assert hashlib.sha256(archive.read(name)).hexdigest() == sha(ROOT / "site/downloads" / name)
        records.append({
            "model": key, "cad": native, "blender": scene, "video": video,
            "drawings_pdf_pages": len(reader.pages), "privacy": privacy,
        })
    part_pdf = PdfReader(ROOT / "site/downloads/part-drawings.pdf")
    assert len(part_pdf.pages) == len(c["parts"])
    assert all("PUBLIC TEMPLATE / 5-COURSE BASE" in page.extract_text() for page in part_pdf.pages)
    policy = read("design/publication-policy.json")
    private_route = read("validation/private-route.json")
    assert private_route["status"] == "PASS_PRIVATE_OUTPUT_BOUNDARY_AND_NATIVE_REOPEN"
    result = {
        "scope": "A/B/C five-course bases, enlarged front text, independent right logos and vertical exploded display",
        "revision": c["revision"],
        "publication_mode": policy["mode"],
        "digital_checks_passed": True,
        "digital_checks_scope": "Native, mesh, package and software-output checks; browser execution is recorded separately.",
        "publication_ready": current_browser,
        "physical_testing": "NOT_PERFORMED",
        "parameters_sha256": c["parameters_sha256"],
        "mechanical_source_sha256": sha(ROOT / "scripts/freecad_geometry.py"),
        "parts": len(c["parts"]), "mesh_checks": mesh,
        "models": records, "print_packages": packages, "three_mf_reopen": three_mf, "browser": browser_record,
        "explosion_motion": motion,
        "front_modules": front, "revision_invariants": revision,
        "final_browser_recheck": {"status": "PASS_CURRENT_REVISION_CI" if current_browser else "PENDING_CURRENT_REVISION_CI",
                                  "revision": c["revision"], "local_browser_retry": "not attempted; known environment limitation"},
        "unselected_individual_variant": "withheld from public distribution",
        "private_personalization_route": private_route,
        "privacy_cleanup": read("validation/privacy-cleanup.json"),
        "review_boundary": "Current digital output checks are not physical qualification. Historical personal review records are preserved privately, not republished as generic evidence.",
        "not_claimed": ["Commercial compatibility guarantee", "Physical clutch/strength/tip testing",
                        "Slicer-measured print mass/time", "Toy safety or manufacturing certification",
                        "Official LEGO/GitHub/Bambu product"],
    }
    write_json(ROOT / "site/downloads/validation.json", result)
    print(f"Aggregated genuine checks for {len(records)} models and {len(c['parts'])} unique meshes.")


if __name__ == "__main__":
    main()
