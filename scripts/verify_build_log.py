"""Audit only the approved, already-redacted public derivatives; never open source photographs."""

import hashlib
import json
from pathlib import Path
import re

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "site/media/build-log/2026-09-23"
MANIFEST_SHA256 = "cf7f738f4b5602dffbdec42034b4bb769527aef49ed409c71992b59846499a2d"
PHOTO_NAMES = {
    "lettering-first.jpg", "lettering-follow-up.jpg", "base-overview.jpg",
    "front-modules-installed.jpg", "base-top-angle.jpg", "base-side-angle.jpg",
    "right-logo-installed.jpg", "base-front-detail.jpg", "base-front-overview.jpg",
}
MASKS = {
    "lettering-first.jpg": [[395, 260, 1455, 455]],
    "lettering-follow-up.jpg": [[235, 535, 1565, 715], [215, 1205, 1595, 1405]],
    "front-modules-installed.jpg": [[205, 319, 1165, 449]],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_photos(folder=FOLDER):
    raw = (folder / "manifest.json").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, "Approved photo manifest changed")
    manifest = json.loads(raw)
    require(not re.search(rb"/Users/|/home/|\.copilot/|PXL_|source_path|source_filename", raw),
            "Source-identifying metadata must not be published")
    require(manifest["scope"] == "sanitized public build journal", "Wrong photo handoff scope")
    require({row["path"] for row in manifest["photos"]} == PHOTO_NAMES and len(manifest["photos"]) == 9,
            "Use only the nine approved public photos")
    require({p.name for p in folder.iterdir()} == PHOTO_NAMES | {"manifest.json"},
            "Unexpected file alongside the public photo allowlist")
    records = []
    for row in manifest["photos"]:
        path = folder / row["path"]
        require(path.is_file() and not path.is_symlink(), "Photo must be a local regular file")
        data = path.read_bytes()
        require(len(data) == row["size_bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"],
                f"Approved photo bytes differ: {path.name}")
        require(data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"), "Not a complete JPEG")
        require(row["capture_date"] is None, "Do not infer an exact capture date")
        require(row["reported_date"] == ("2026-09-22" if row["id"] == "lettering-first" else "2026-09-23"),
                "Report date and uncertain capture date must stay distinct")
        with Image.open(path) as image:
            image.load()
            require(image.format == "JPEG" and image.mode == "RGB" and getattr(image, "n_frames", 1) == 1,
                    "Expected a flattened, single-frame RGB JPEG")
            require(list(image.size) == row["pixels"], "Photo dimensions differ")
            require(not image.getexif() and set(image.info) <= {"jfif", "jfif_version", "jfif_unit", "jfif_density"},
                    "EXIF/XMP/ICC/comments are not permitted")
            require(len(image.applist) == 1 and image.applist[0][0] == "APP0",
                    "Unexpected JPEG application metadata or comment")
            jfif = image.applist[0][1]
            require(len(jfif) == 14 and jfif[:5] == b"JFIF\0" and jfif[12:14] == b"\0\0",
                    "Embedded thumbnails or extra JFIF data are not permitted")
            for x0, y0, x1, y1 in MASKS.get(path.name, []):
                require(0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height, "Mask outside image")
                middle = (y0 + y1) // 2
                # Avoid JPEG boundary ringing and the deliberately visible redaction label.
                for top, bottom in ((y0 + 16, middle - 28), (middle + 28, y1 - 16)):
                    patch = image.crop((x0 + 16, top, x1 - 16, bottom))
                    require(patch.getextrema() == ((32, 32), (39, 39), (47, 47)),
                            "Expected solid baked-in pixels around the redaction label")
            require(("personal account row irreversibly masked in the pixels" in row["edits"])
                    == (path.name in MASKS), "Pixel masking scope and manifest differ")
        records.append({
            "file": row["path"], "bytes": len(data), "sha256": row["sha256"],
            "pixels": row["pixels"], "stage": row["stage"], "reported_date": row["reported_date"],
            "capture_date": None, "metadata": "JFIF only; no EXIF/XMP/ICC/comment/thumbnail",
            "pixel_mask_rectangles": MASKS.get(path.name, []),
        })
    require(sum(row["bytes"] for row in records) == 3511720, "Approved photo total differs")
    return {
        "status": "PASS_APPROVED_PUBLIC_DERIVATIVE_INTEGRITY",
        "report_date": "2026-09-23", "manifest_sha256": MANIFEST_SHA256,
        "source_photographs_accessed": False, "photos": records,
        "mask_check": "Flat RGB pixels checked away from visible labels; exact approved bytes and separate visual inspection, not an OCR guarantee.",
        "evidence_scope": "User report and photographs of a personalized B base/front modules, not full assembly or physical qualification.",
        "source_print_hashes_known": False, "slicer_project_received": False,
        "physical_qualification_claimed": False,
    }


def main():
    report = verify_photos()
    path = ROOT / "validation/build-log-photos.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS nine exact approved JPEGs, four baked-in mask regions, no identifying metadata or embedded thumbnails.")


if __name__ == "__main__":
    main()
