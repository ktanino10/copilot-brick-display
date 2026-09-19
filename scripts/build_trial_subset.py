"""Package a staged selection of existing masters; never generate or transform geometry."""

import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from design import ROOT, write_json


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows_for(config, catalog, variant):
    selected = [
        *config["common"],
        {"part": variant["base_part"], "quantity": variant["base_quantity"],
         "color": "black", "stage": "keeper-base"},
    ]
    rows = []
    for row in selected:
        part = catalog["parts"][row["part"]]
        extents = [round(high - low, 3) for low, high in zip(*part["bounds"])]
        rows.append({**row, "stl": part["stl"], "sha256": part["sha256"],
                     "width_mm": extents[0], "depth_mm": extents[1], "height_mm": extents[2],
                     "orientation": part["orientation"]})
    return rows


def archive_text(markdown):
    return (markdown
            .replace("(../site/", "(https://ktanino10.github.io/copilot-brick-display/")
            .replace("(build.ja.md)", "(https://ktanino10.github.io/copilot-brick-display/guide.html)")
            .replace("(build.ja.md#", "(https://ktanino10.github.io/copilot-brick-display/guide.html#")
            .replace("(trial.ja.md)", "(https://ktanino10.github.io/copilot-brick-display/trial.html)"))


def main():
    config = json.loads((ROOT / "design/trial-subset.json").read_text())
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    assert config["geometry_revision"] == catalog["revision"]
    output = ROOT / "site/downloads/trial-subset"
    output.mkdir(parents=True, exist_ok=True)
    variants = []
    parts = {}
    for variant in config["variants"]:
        rows = rows_for(config, catalog, variant)
        assert sum(row["quantity"] for row in rows) == config["quantity_per_selected_variant"]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        filename = f"bom-{variant['id']}.csv"
        (output / filename).write_text(stream.getvalue())
        variants.append({"model": variant["id"], "bom": filename, "print_count": 7,
                         "real_block_stage_count": 4, "keeper_base_stage_count": 3, "rows": rows})
        for row in rows:
            part = catalog["parts"][row["part"]]
            data = (ROOT / "site/downloads" / part["stl"]).read_bytes()
            assert sha(data) == part["sha256"], f"Master hash differs: {part['id']}"
            parts[part["id"]] = {"id": part["id"], "stl": part["stl"], "sha256": part["sha256"],
                                 "bytes": len(data), "bounds_mm": part["bounds"], "orientation": part["orientation"]}
    manifest = {
        "schema_version": 1, "guidance_revision": config["guidance_revision"],
        "geometry_revision": catalog["revision"], "catalog_sha256": sha((ROOT / "design/catalog.json").read_bytes()),
        "units": "mm", "sliced": False, "physical_trial_performed": False,
        "geometry_changed": False, "quantity_per_selected_variant": 7,
        "select_one_variant_only": True, "variants": variants, "parts": list(parts.values()),
        "existing_coupon_package": "../fit-coupons.zip",
        "not_qualified": config["not_qualified"], "source_observation": config["source_observation"],
    }
    write_json(output / "manifest.json", manifest)
    (output / "READ-FIRST-ja.md").write_text(archive_text((ROOT / "docs/trial.ja.md").read_text()))
    files = {part["stl"]: ROOT / "site/downloads" / part["stl"] for part in parts.values()}
    files.update({path.name: path for path in output.iterdir() if path.is_file()})
    files["fit-log.csv"] = ROOT / "site/downloads/fit-log.csv"
    archive = ROOT / "site/downloads/trial-subset.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative, path in sorted(files.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 9, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes())
    print(f"Packaged {len(parts)} unchanged masters; choose ONE seven-piece staged BOM. Existing coupons are linked, not duplicated.")


if __name__ == "__main__":
    main()
