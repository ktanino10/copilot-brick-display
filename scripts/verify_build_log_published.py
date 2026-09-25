"""Match the deployed public journal and sanitized photos to the approved local files."""

import argparse
import hashlib
import json
import re
from urllib.parse import quote

from design import ROOT, write_json
from verify_build_log import PHOTO_SETS, verify_photos
from verify_published import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ci-receipt", required=True)
    parser.add_argument("--report-date", choices=sorted(PHOTO_SETS), default=max(PHOTO_SETS))
    parser.add_argument("--base", default="https://ktanino10.github.io/copilot-brick-display/")
    args = parser.parse_args()
    ci = json.loads((ROOT / args.ci_receipt).read_text())
    if (ci["headSha"] != args.commit or ci["status"] != "completed" or ci["conclusion"] != "success"
            or {job["name"]: job["conclusion"] for job in ci["jobs"]} != {"validate": "success", "deploy": "success"}):
        raise ValueError("The exact journal commit has not passed both validation and actual Pages deployment")
    checked = [verify_photos(report_date=date) for date in sorted(PHOTO_SETS) if date <= args.report_date]
    photo_paths = [f"media/build-log/{entry['report_date']}/" + photo["file"]
                   for entry in checked for photo in entry["photos"]]
    manifests = [f"media/build-log/{entry['report_date']}/manifest.json" for entry in checked]
    paths = ["build-log.html", "index.html", "guide.html", "lettering.html", "assembly.html", "notices.html",
             *manifests, *photo_paths]
    records = []
    video_reference = "https://youtu.be/Lc_enNE3nng" if args.report_date >= "2026-09-25" else None
    video_embed = "https://www.youtube-nocookie.com/embed/Lc_enNE3nng?playsinline=1" if video_reference else None
    base = args.base.rstrip("/") + "/"
    for relative in paths:
        data = fetch(base + quote(relative) + "?log=" + args.report_date + "&commit=" + quote(args.commit))
        if data != (ROOT / "site" / relative).read_bytes():
            raise ValueError(f"Published journal asset differs: {relative}")
        if relative == "build-log.html" and video_reference:
            page = data.decode("utf-8")
            if page.count(f'href="{video_reference}"') != 1:
                raise ValueError("The authorized external video link is missing or duplicated")
            frames = re.findall(r"<iframe\b[^>]*>", page)
            if len(frames) != 1 or f'src="{video_embed}"' not in frames[0]:
                raise ValueError("Expected exactly the authorized privacy-enhanced YouTube player")
            if 'referrerpolicy="strict-origin-when-cross-origin"' not in frames[0] or "allowfullscreen" not in frames[0]:
                raise ValueError("YouTube player permissions/referrer policy differ")
            if "autoplay" in frames[0] or re.search(r"""<(?:img|script|video|audio)\b[^>]*src=["'][^"']*(?:youtu|ytimg)""", page):
                raise ValueError("Do not auto-play or separately load/rehost the supplied media")
        records.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    write_json(ROOT / "validation" / f"build-log-published-{args.report_date}.json", {
        "status": "PASS_LIVE_SANITIZED_BUILD_JOURNAL", "report_date": args.report_date,
        "deployed_commit": args.commit, "run_url": ci["url"],
        "manifest_sha256_by_date": {entry["report_date"]: entry["manifest_sha256"] for entry in checked},
        "entry_url": base + f"build-log.html?log={args.report_date}&commit={args.commit[:12]}#build-{args.report_date}",
        "files": records, "photo_count": len(photo_paths),
        "photos_by_report": {entry["report_date"]: len(entry["photos"]) for entry in checked},
        "scope": "Only current public redacted derivatives and journal pages; no original photos or private distribution.",
        "progress": ("Personalized B completion report and full-view photos; not a physical qualification or design-color change."
                     if checked[-1]["personalized_b_completion_reported"] else
                     "Personalized B work-in-progress observations only, not the complete150-piece figure or a design-color change."),
        "personalized_b_completion_reported": checked[-1]["personalized_b_completion_reported"],
        "external_video_reference": video_reference,
        "official_video_embed": video_embed,
        "video_content_downloaded_to_repo": False,
        "embed_playback_tested_by_this_hash_check": False,
        "slicer_input_hashes_verified": False, "physical_qualification_claimed": False,
    })
    print(f"PASS {len(records)} actual live page/image hashes; all {len(photo_paths)} photos match the approved redacted bytes.")


if __name__ == "__main__":
    main()
