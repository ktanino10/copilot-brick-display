"""Match the deployed public journal and sanitized photos to the approved local files."""

import argparse
import hashlib
import json
from urllib.parse import quote

from design import ROOT, write_json
from verify_build_log import MANIFEST_SHA256, verify_photos
from verify_published import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ci-receipt", required=True)
    parser.add_argument("--base", default="https://ktanino10.github.io/copilot-brick-display/")
    args = parser.parse_args()
    ci = json.loads((ROOT / args.ci_receipt).read_text())
    if (ci["headSha"] != args.commit or ci["status"] != "completed" or ci["conclusion"] != "success"
            or {job["name"]: job["conclusion"] for job in ci["jobs"]} != {"validate": "success", "deploy": "success"}):
        raise ValueError("The exact journal commit has not passed both validation and actual Pages deployment")
    checked = verify_photos()
    photo_paths = ["media/build-log/2026-09-23/" + photo["file"] for photo in checked["photos"]]
    paths = ["build-log.html", "index.html", "guide.html", "lettering.html", "assembly.html", "notices.html",
             "media/build-log/2026-09-23/manifest.json", *photo_paths]
    records = []
    base = args.base.rstrip("/") + "/"
    for relative in paths:
        data = fetch(base + quote(relative) + "?log=2026-09-23&commit=" + quote(args.commit))
        if data != (ROOT / "site" / relative).read_bytes():
            raise ValueError(f"Published journal asset differs: {relative}")
        records.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    write_json(ROOT / "validation/build-log-published.json", {
        "status": "PASS_LIVE_SANITIZED_BUILD_JOURNAL", "report_date": "2026-09-23",
        "deployed_commit": args.commit, "run_url": ci["url"], "manifest_sha256": MANIFEST_SHA256,
        "entry_url": base + "build-log.html?log=2026-09-23&commit=" + args.commit[:12],
        "files": records, "photo_count": len(photo_paths),
        "scope": "Only current public redacted derivatives and journal pages; no original photos or private distribution.",
        "progress": "Personalized B base and front modules observed and reported, not the complete150-piece figure.",
        "slicer_input_hashes_verified": False, "physical_qualification_claimed": False,
    })
    print(f"PASS {len(records)} actual live page/image hashes; all nine photos match the approved redacted bytes.")


if __name__ == "__main__":
    main()
