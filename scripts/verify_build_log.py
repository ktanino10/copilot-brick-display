"""Audit only the approved, already-redacted public derivatives; never open source photographs."""

import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

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
PHOTO_SETS = {
    "2026-09-23": {
        "manifest_sha256": MANIFEST_SHA256, "photo_names": PHOTO_NAMES,
        "total_bytes": 3511720, "masks": MASKS, "scope": "sanitized public build journal",
    },
    "2026-09-24": {
        "manifest_sha256": "88b27bcba2820e2649d14438401316444ab9394a7039e7eec78c1848a00bb6bb",
        "photo_names": {
            "first-purple-row.jpg", "lower-face.jpg", "lower-face-detail.jpg", "lower-face-wide.jpg",
            "face-eye-strips.jpg", "face-top-row.jpg", "face-top-row-angle.jpg",
        },
        "total_bytes": 3033706, "masks": {}, "scope": "generic build-journal photo derivatives",
        "masks_from_manifest": True,
    },
    "2026-09-25": {
        "manifest_sha256": "4e07df6e20ab45eb65b308eea3467d7e1785bba83f9912c6a659e8b2dcbc69bd",
        "photo_names": {
            "goggle-lower-band.jpg", "goggle-first-row.jpg", "goggle-growing.jpg", "goggle-midway.jpg",
            "goggle-higher.jpg", "goggle-near-top.jpg", "goggle-before-closure.jpg", "finished-portrait.jpg",
        },
        "total_bytes": 3176033, "masks": {}, "scope": "generic completion-journal derivatives",
        "masks_from_manifest": True, "subject_boundary_masks": True, "completion_reported": True,
    },
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_photo_set(folder, *, manifest_sha256, photo_names, report_date, total_bytes, masks,
                     scope, masks_from_manifest=False, completion_reported=False, subject_boundary_masks=False):
    raw = (folder / "manifest.json").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == manifest_sha256, "Approved photo manifest changed")
    manifest = json.loads(raw)
    require(not re.search(rb"/Users/|/home/|\.copilot/|PXL_|source_path|source_filename", raw),
            "Source-identifying metadata must not be published")
    require(manifest["scope"] == scope and manifest["report_date"] == report_date, "Wrong photo handoff scope/date")
    require({row["path"] for row in manifest["photos"]} == photo_names
            and len(manifest["photos"]) == len(photo_names), "Use only the approved public photo allowlist")
    require({p.name for p in folder.iterdir()} == photo_names | {"manifest.json"},
            "Unexpected file alongside the public photo allowlist")
    if masks_from_manifest:
        masks = {row["path"]: row["personal_mask_rectangles_px"] for row in manifest["photos"]}
        require(all(len(rectangles) == 1 for rectangles in masks.values()), "Expected one personal-row mask per new image")
    records = []
    for row in manifest["photos"]:
        path = folder / row["path"]
        require(path.is_file() and not path.is_symlink(), "Photo must be a local regular file")
        data = path.read_bytes()
        require(len(data) == row["size_bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"],
                f"Approved photo bytes differ: {path.name}")
        require(data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"), "Not a complete JPEG")
        require(row["capture_date"] is None, "Do not infer an exact capture date")
        expected_date = "2026-09-22" if report_date == "2026-09-23" and row["id"] == "lettering-first" else report_date
        require(row["reported_date"] == expected_date,
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
            for x0, y0, x1, y1 in masks.get(path.name, []):
                require(0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height, "Mask outside image")
                # Avoid JPEG boundary ringing and the deliberately visible redaction label.
                require(x1 - x0 > 128 and y1 - y0 > 24, "Mask too small for the declared interior check")
                for left, right in ((x0 + 16, x0 + 64), (x1 - 64, x1 - 16)):
                    patch = image.crop((left, y0 + 12, right, y1 - 12))
                    require(patch.getextrema() == ((32, 32), (39, 39), (47, 47)),
                            "Expected solid baked-in pixels around the redaction label")
            description = ("personal account row masked in pixels" if subject_boundary_masks else
                           "personal account row covered by opaque pixels" if masks_from_manifest else
                           "personal account row irreversibly masked in the pixels")
            require((description in row["edits"])
                    == (path.name in masks), "Pixel masking scope and manifest differ")
            backgrounds = (row["additional_background_mask_polygons_px"] if subject_boundary_masks else
                           row["background_mask_polygons_px"] if masks_from_manifest else [])
            retained = row["subject_retention_polygon_px"] if subject_boundary_masks else []
            if subject_boundary_masks:
                require("unrelated background replaced by opaque neutral pixels outside the recorded subject boundary" in row["edits"],
                        "Subject-background processing is not declared")
                require(len(retained) >= 3, "Missing approved subject boundary")
            elif masks_from_manifest:
                require(("unrelated background areas covered by opaque pixels" in row["edits"]) == bool(backgrounds),
                        "Background-mask scope and manifest differ")
            for polygon in backgrounds + ([retained] if retained else []):
                require(len(polygon) >= 3 and all(0 <= x <= image.width and 0 <= y <= image.height for x, y in polygon),
                        "Background mask outside image")
            if retained:
                mask = Image.new("L", image.size, 255)
                draw = ImageDraw.Draw(mask)
                draw.polygon([tuple(point) for point in retained], fill=0)
                for polygon in backgrounds:
                    draw.polygon([tuple(point) for point in polygon], fill=255)
                interior = mask.filter(ImageFilter.MinFilter(5))
                require(interior.getbbox() is not None, "No subject-background mask interior")
                delta = ImageChops.difference(image, Image.new("RGB", image.size, (234, 239, 243)))
                require(max(ImageStat.Stat(delta, interior).mean) < 1.5,
                        "Pixels outside the retained subject do not match the approved opaque background")
            for polygon in backgrounds:
                mask = Image.new("L", image.size)
                ImageDraw.Draw(mask).polygon([tuple(point) for point in polygon], fill=255)
                interior = mask.filter(ImageFilter.MinFilter(5))
                require(interior.getbbox() is not None, "No background-mask interior")
                delta = ImageChops.difference(image, Image.new("RGB", image.size, (234, 239, 243)))
                require(max(ImageStat.Stat(delta, interior).mean) < 1.5,
                        "Decoded background-mask interior differs from the approved solid color")
        records.append({
            "file": row["path"], "bytes": len(data), "sha256": row["sha256"],
            "pixels": row["pixels"], "stage": row["stage"], "reported_date": row["reported_date"],
            "capture_date": None, "metadata": "JFIF only; no EXIF/XMP/ICC/comment/thumbnail",
            "pixel_mask_rectangles": masks.get(path.name, []),
            "background_mask_polygons": backgrounds,
            "subject_retention_polygon": retained,
        })
    require(sum(row["bytes"] for row in records) == total_bytes, "Approved photo total differs")
    if completion_reported:
        require("これで完成ですね" in manifest["user_reports_ja"], "Missing authorized completion report")
        require([row["path"] for row in manifest["photos"] if row["stage"] == "completed"] == ["finished-portrait.jpg"],
                "The completed view must be the approved final photograph")
    return {
        "status": "PASS_APPROVED_PUBLIC_DERIVATIVE_INTEGRITY",
        "report_date": report_date, "manifest_sha256": manifest_sha256,
        "source_photographs_accessed": False, "photos": records,
        "mask_check": "Flat RGB pixels checked away from visible labels; exact approved bytes and separate visual inspection, not an OCR guarantee.",
        "evidence_scope": ("User completion report and full-view photographs of a personalized B; physical qualification is separate."
                           if completion_reported else
                           "User reports and photographs of personalized B work in progress, not full assembly or physical qualification."),
        "personalized_b_completion_reported": completion_reported,
        "source_print_hashes_known": False, "slicer_project_received": False,
        "physical_qualification_claimed": False,
    }


def verify_photos(folder=None, report_date="2026-09-23"):
    require(report_date in PHOTO_SETS, "No approved public photo set for that report date")
    folder = folder or ROOT / "site/media/build-log" / report_date
    return verify_photo_set(folder, report_date=report_date, **PHOTO_SETS[report_date])


def main():
    reports = [verify_photos(report_date=date) for date in sorted(PHOTO_SETS)]
    for report in reports:
        date = report["report_date"]
        print(f"PASS {date}: {len(report['photos'])} approved JPEGs, baked-in pixel masks, no identifying metadata or thumbnails.")
    latest = reports[-1]
    latest["retained_prior_photo_sets"] = [
        {"report_date": report["report_date"], "manifest_sha256": report["manifest_sha256"],
         "photo_count": len(report["photos"])} for report in reports[:-1]
    ]
    path = ROOT / "validation" / f"build-log-photos-{latest['report_date']}.json"
    path.write_text(json.dumps(latest, indent=2) + "\n")


if __name__ == "__main__":
    main()
