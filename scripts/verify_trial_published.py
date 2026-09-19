"""Verify only the newly published trial guidance/downloads and unchanged catalogue."""

import hashlib
import json

from design import ROOT, write_json
from verify_published import fetch


def main():
    base = "https://ktanino10.github.io/copilot-brick-display/"
    suffix = "?guidance=trial-2026-09-19"
    files = [
        "index.html", "guide.html", "trial.html", "technical.html", "assets/catalog.json",
        "downloads/trial-subset.zip", "downloads/trial-subset/manifest.json",
        "downloads/trial-subset/bom-A.csv", "downloads/trial-subset/bom-B.csv",
        "downloads/trial-subset/bom-C.csv", "downloads/fit-log.csv", "downloads/fit-coupons.zip",
        "downloads/A/print-kit.zip", "downloads/B/print-kit.zip", "downloads/C/print-kit.zip",
    ]
    checked = []
    for relative in files:
        data = fetch(base + relative + suffix)
        local = (ROOT / "site" / relative).read_bytes()
        assert data == local, f"Published trial artifact differs: {relative}"
        checked.append({"url": base + relative, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    manifest = json.loads((ROOT / "site/downloads/trial-subset/manifest.json").read_text())
    write_json(ROOT / "validation/trial-published.json", {
        "status": "PASS_LIVE_TRIAL_GUIDANCE", "guidance_revision": manifest["guidance_revision"],
        "geometry_revision": manifest["geometry_revision"], "exact_published_files": checked,
        "public_trial_url": base + "trial.html" + suffix,
        "geometry_changed": False, "sliced": False, "physical_trial_performed": False,
    })
    print(f"PASS {len(checked)} published guidance/download byte comparisons; geometry is unchanged and physical trials remain unperformed.")


if __name__ == "__main__":
    main()
