"""Mirror only the addition's declared public artifacts, preserving verified bytes."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from design import ROOT, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true", help="Publish a reviewed, adhesive-free replacement snapshot.")
    args = parser.parse_args()
    source = ROOT / "projects/character-tribute"
    destination = ROOT / "site/tribute"
    if not args.release:
        prior = ROOT / "validation/tribute-mirror.json"
        if prior.exists():
            record = json.loads(prior.read_text())
            owned = set(record.get("copied", []) + record.get("linked_rebuild_sources", []) + ["manifest.json", "index.html"])
            for relative in owned:
                path = (destination / relative).resolve()
                if not path.is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe prior mirror path")
                if path.is_file():
                    path.unlink()
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "resources/tribute-status.html", destination / "index.html")
        write_json(prior, {
            "status": "WITHDRAWN_REJECTED_ADHESIVE_DESIGN",
            "entry": "tribute/index.html", "assets": 0, "copied": ["index.html"],
            "manufacturing_downloads": "REMOVED",
            "user_requirement": "No adhesive; every part, including small colored reliefs, must be removable.",
            "replacement": "redesign and independent review pending",
        })
        print("Withdrew obsolete adhesive-design downloads; published redesign status only.")
        return
    manifest = json.loads((source / "manifest.json").read_text())
    assert manifest["physical_fit_tested"] is False
    assert manifest.get("adhesive_required") is False
    assert manifest.get("all_parts_removable") is True
    assert manifest.get("independent_retention_review") == "accepted_digital_only"
    entry = (source / manifest["entry"]).read_text()
    copied = []
    for asset in manifest["assets"]:
        relative = Path(asset["url"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe asset path in addition manifest")
        original = source / relative
        data = original.read_bytes()
        assert len(data) == asset["bytes"], relative
        assert hashlib.sha256(data).hexdigest() == asset["sha256"], relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        assert target.read_bytes() == data
        copied.append(str(relative))
    shutil.copyfile(source / "manifest.json", destination / "manifest.json")
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "projects/character-tribute"], cwd=ROOT,
    ).decode().split("\0")
    source_files = []
    for filename in filter(None, tracked):
        relative = (ROOT / filename).relative_to(source)
        if relative.suffix not in {".py", ".md", ".txt", ".json"} or str(relative) in copied:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        source_files.append(str(relative))
    write_json(ROOT / "validation/tribute-mirror.json", {
        "status": "PASS_HASH_IDENTICAL_PUBLIC_MIRROR",
        "entry": "tribute/index.html", "assets": len(copied), "copied": copied,
        "linked_rebuild_sources": source_files,
        "geometry": "unchanged separate product", "physical_fit": "NOT_TESTED",
        "manufacturing_release": "digital_prototype_physical_tests_required",
    })
    print(f"Mirrored {len(copied)} verified removable-design artifacts; physical testing remains open")


if __name__ == "__main__":
    main()
