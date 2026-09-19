"""Mirror only the addition's declared public artifacts, preserving verified bytes."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from design import ROOT, write_json


def main():
    source = ROOT / "projects/character-tribute"
    destination = ROOT / "site/tribute"
    manifest = json.loads((source / "manifest.json").read_text())
    assert manifest["physical_fit_tested"] is False
    assert "awaits" in manifest["adhesive_design_status"]
    entry = (source / manifest["entry"]).read_text()
    assert "製作リリース保留" in entry, "Pending adhesive authorization must be visible, not just metadata"
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
        "manufacturing_release": "HELD_PENDING_ADHESIVE_AUTHORIZATION",
    })
    print(f"Mirrored {len(copied)} verified candidate artifacts; manufacturing-release hold preserved")


if __name__ == "__main__":
    main()
