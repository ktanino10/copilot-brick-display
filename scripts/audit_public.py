"""Inspect every public file, including nested native/print archives, before pushing."""

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from design import ROOT, write_json

PATTERNS = [
    re.compile(rb"/Users/[A-Za-z0-9_.-]+/"),
    re.compile(rb"/home/[A-Za-z0-9_.-]+/"),
    re.compile(rb"\.copilot/(?:attachments|session-state)/"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def inspect(data, name, depth=0):
    for pattern in PATTERNS:
        if pattern.search(data):
            raise ValueError(f"Private material detected in {name}; not safe to publish")
    count = 1
    if data[:4] == b"PK\x03\x04":
        if depth > 5:
            raise ValueError(f"Unexpected archive nesting in {name}")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if member.filename.startswith("/") or ".." in Path(member.filename).parts:
                    raise ValueError(f"Unsafe archive member in {name}")
                count += inspect(archive.read(member), f"{name}!{member.filename}", depth + 1)
    return count


def main():
    entries, expanded = [], 0
    for path in sorted((ROOT / "site").rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in {".FCBak", ".FCStd1", ".blend1", ".log"}:
            raise ValueError(f"Intermediate file in public site: {path.name}")
        data = path.read_bytes()
        expanded += inspect(data, str(path.relative_to(ROOT)))
        entries.append({"path": str(path.relative_to(ROOT / "site")), "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    for path in sorted((ROOT / "projects").rglob("*")) if (ROOT / "projects").exists() else []:
        if path.is_file() and path.suffix not in (".pyc",) and "__pycache__" not in path.parts:
            expanded += inspect(path.read_bytes(), str(path.relative_to(ROOT)))
    write_json(ROOT / "validation/public-audit.json", {
        "status": "PASS_RECURSIVE_PUBLIC_ARTIFACT_AUDIT", "expanded_entries": expanded,
        "public_files": len(entries), "site_bytes": sum(entry["bytes"] for entry in entries),
        "files": entries,
        "original_photographs": "not included",
        "scope": "public site and separate generated tribute project, including archive contents",
    })
    print(f"PASS public privacy/archive audit: {len(entries)} site files, {expanded} expanded entries")


if __name__ == "__main__":
    main()
