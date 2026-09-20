"""Compare deployed guide, offline ZIPs, print wrappers and tutorial media to verified local bytes."""

import argparse
import hashlib
import io
import json
import re
from urllib.parse import quote
import zipfile

from design import ROOT, write_json
from verify_published import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ci-receipt", required=True)
    parser.add_argument("--base", default="https://ktanino10.github.io/copilot-brick-display/")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise ValueError("Expected the full deployed commit SHA")
    receipt = json.loads((ROOT / args.ci_receipt).read_text())
    if receipt["headSha"] != args.commit or receipt["status"] != "completed" or receipt["conclusion"] != "success":
        raise ValueError("The exact commit has not completed the required successful workflow")
    jobs = {job["name"]: job["conclusion"] for job in receipt["jobs"]}
    if jobs.get("validate") != "success" or jobs.get("deploy") != "success":
        raise ValueError("Validation and actual Pages deployment must both succeed")
    policy = json.loads((ROOT / "design/publication-policy.json").read_text())
    if policy["mode"] != "generic" or policy["public_text_approved"] is not False:
        raise ValueError("This verification is scoped to the generic public project")
    targets = ["index.html", "app.js", "guide.html", "assembly.html", "rebuild.html",
               "assembly-guide/index.html", "assembly-guide/runtime.js", "assembly-guide/style.css",
               "downloads/fit-coupons.zip", "downloads/B/bom.csv", "downloads/B/plates.zip"]
    for model in "ABC":
        targets.extend([f"assembly-guide/{model}.html", f"assembly-guide/{model}.mapping.json",
                        f"assembly-guide/{model}-offline.zip", f"downloads/{model}/print-kit.zip"])
    targets.extend(f"assembly-guide/media/{name}" for name in
                   ("B-first-base.png", "B-black-01-sort.png", "B-black-04-base-parts.png",
                    "B-first-seven-steps.gif", "B-first-seven-steps.mp4"))
    base = args.base.rstrip("/") + "/"
    records = []
    for relative in targets:
        url = base + quote(relative) + "?guide=print-to-place-1&commit=" + args.commit
        actual = fetch(url)
        expected = (ROOT / "site" / relative).read_bytes()
        if actual != expected:
            raise ValueError(f"Published bytes do not match this revision: {relative}")
        if relative.endswith("-offline.zip"):
            with zipfile.ZipFile(io.BytesIO(actual)) as archive:
                if set(archive.namelist()) != {"index.html", "mapping.json", "THREE-LICENSE.txt"}:
                    raise ValueError("Unexpected offline archive member")
                mapping = json.loads(archive.read("mapping.json"))
                model = relative.split("/")[-1][0]
                local = json.loads((ROOT / f"site/assembly-guide/{model}.mapping.json").read_text())
                if mapping != local:
                    raise ValueError("Offline and HTTP guide mapping differ")
                if b'id="assembly-guide-data"' not in archive.read("index.html"):
                    raise ValueError("Offline HTML does not contain its embedded real data")
        records.append({"path": relative, "bytes": len(actual), "sha256": hashlib.sha256(actual).hexdigest()})
    write_json(ROOT / "validation/assembly-guide-published.json", {
        "status": "PASS_LIVE_PRINT_TO_PLACE_GUIDE", "deployed_commit": args.commit,
        "run_url": receipt["url"], "jobs": jobs, "guide_revision": "print-to-place-1",
        "entry_url": base + "assembly-guide/B.html?commit=" + args.commit[:12],
        "files": records, "generic_public_policy": True, "manufacturing_inputs_changed": False,
        "scope": "Listed current generic Pages/ZIP/tutorial files only; no private releases or retained history.",
        "sliced": False, "physical_fit_tested": False,
    })
    print(f"PASS {len(records)} live guide/media/package hashes and all three actual offline ZIPs.")


if __name__ == "__main__":
    main()
