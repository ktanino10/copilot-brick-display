"""Verify the published color-printing entry and the real files it tells another PC to use."""

import hashlib
import json

from design import ROOT, write_json
from verify_published import fetch


def main():
    base = "https://ktanino10.github.io/copilot-brick-display/"
    version = "separate-color-2026-09-19"
    targets = ["index.html", "guide.html", "trial.html", "downloads/fit-coupons.zip",
               "downloads/trial-subset.zip", "downloads/fit-log.csv"]
    for model in "ABC":
        targets.extend(f"downloads/{model}/{filename}" for filename in
                       ("print-kit.zip", "plates.zip", "bom.csv", "drawings.pdf", "plates/manifest.json"))
    records = []
    for relative in targets:
        data = fetch(base + relative + "?guide=" + version)
        expected = (ROOT / "site" / relative).read_bytes()
        if data != expected:
            raise ValueError(f"Published printing-guide artifact differs: {relative}")
        records.append({"path": relative, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    manifest = json.loads((ROOT / "design/publication-policy.json").read_text())
    assert manifest["mode"] == "generic" and manifest["public_text_approved"] is False
    write_json(ROOT / "validation/cross-pc-published.json", {
        "status": "PASS_LIVE_GENERIC_COLOR_PRINT_GUIDE",
        "guide_revision": version, "geometry_revision": "4.0-public-template",
        "entry_url": base + "guide.html?guide=" + version + "#print-another-pc",
        "files": records, "personal_files_published": False,
        "manual_black_to_white_after_mm": {"message_plate": 2.4, "logo": 2.8},
        "pause_commands_in_distributed_3mf": False,
        "actual_slicer_profile_received": False, "sliced_or_physical_print_verified": False,
    })
    print(f"PASS {len(records)} live generic guide/package hashes; private files were not published.")


if __name__ == "__main__":
    main()
