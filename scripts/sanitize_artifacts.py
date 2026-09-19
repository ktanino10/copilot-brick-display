"""Audit native path metadata and strip optional PNG metadata without changing pixels."""

import argparse
import json
import re
import struct
import zipfile
from pathlib import Path

from PIL import Image

from design import ROOT, write_json


def audit_blend(path):
    data = path.read_bytes()
    if data[:7] != b"BLENDER":
        raise ValueError("Use uncompressed native .blend for auditable metadata cleanup")
    if re.search(rb"/(?:Users|home|private|tmp)/[^\0]+", data):
        raise ValueError("Private native path found. Run blender_clean.py via Blender, then reopen and recheck.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["A", "B", "C"], required=True)
    args = parser.parse_args()
    native = ROOT / "site/downloads" / args.model / f"{args.model}.blend"
    audit_blend(native)
    pngs = []
    for path in (ROOT / "site/media").glob(f"{args.model}-*.png"):
        with Image.open(path) as image:
            pixels = image.copy()
            pixels.info.clear()
            pixels.save(path, format="PNG", optimize=True)
        pngs.append(path.name)
    write_json(ROOT / "validation" / f"privacy-{args.model}.json", {
        "model": args.model, "native_private_path_scan": "PASS",
        "png_metadata_removed": pngs,
        "geometry_and_pixels": "unchanged; native must be reopened after metadata normalization",
    })
    print(f"Sanitized {args.model}: native path audit passed; {len(pngs)} PNG metadata blocks removed")


if __name__ == "__main__":
    main()
