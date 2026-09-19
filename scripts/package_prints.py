"""Exact color BOM packages and unsliced, single-color, generic 3MF plate layouts."""

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

import trimesh

from design import ROOT, write_json

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE)


def tag(name):
    return f"{{{CORE}}}{name}"


def pack(items, c):
    plates, plate = [], []
    x = y = row_depth = 0
    for key in sorted(items, key=lambda key: c["parts"][key]["bounds"][1][1] - c["parts"][key]["bounds"][0][1], reverse=True):
        low, high = c["parts"][key]["bounds"]
        w, d = high[0] - low[0] + 12, high[1] - low[1] + 12
        if max(w, d) > 224:
            raise ValueError(f"{key} does not fit the conservative 224 mm packing area")
        if x + w > 224:
            x, y, row_depth = 0, y + row_depth + 2, 0
        if y + d > 224:
            plates.append(plate)
            plate, x, y, row_depth = [], 0, 0, 0
        plate.append({"part": key, "position": [x + 6 - low[0], y + 6 - low[1], -low[2]],
                      "brim_box": [x, y, x + w, y + d]})
        x += w + 2
        row_depth = max(row_depth, d)
    if plate:
        plates.append(plate)
    for plate in plates:
        width = max(item["brim_box"][2] for item in plate)
        depth = max(item["brim_box"][3] for item in plate)
        dx, dy = (256 - width) / 2, (256 - depth) / 2
        for item in plate:
            item["position"][0] += dx
            item["position"][1] += dy
            item["brim_box"] = [value + (dx if index % 2 == 0 else dy)
                                for index, value in enumerate(item["brim_box"])]
    return plates


def write_3mf(path, color, plate, c, cache, finish=None):
    model = ET.Element(tag("model"), {"unit": "millimeter", "xml:lang": "en-US"})
    ET.SubElement(model, tag("metadata"), {"name": "Title"}).text = path.stem
    ET.SubElement(model, tag("metadata"), {"name": "Description"}).text = (
        "Unsliced geometry, single color. Not a validated printer profile or G-code. "
        "6 mm brim envelope reserved; verify exclusions, toolpaths, fit and settings in your slicer. " +
        (f"Dedicated finish plate: start {color}, manually change to {finish[0]} after {finish[1]:g}mm. No other black parts on this plate."
         if finish else "No filament change on this plate."))
    resources = ET.SubElement(model, tag("resources"))
    bases = ET.SubElement(resources, tag("basematerials"), {"id": "1"})
    ET.SubElement(bases, tag("base"), {"name": color, "displaycolor": c["colors"][color]["hex"].upper() + "FF"})
    ids = {}
    for index, key in enumerate(sorted({item["part"] for item in plate}), 2):
        ids[key] = index
        if key not in cache:
            cache[key] = trimesh.load_mesh(ROOT / "site/downloads" / c["parts"][key]["stl"])
        mesh = cache[key]
        obj = ET.SubElement(resources, tag("object"), {"id": str(index), "type": "model", "name": key, "pid": "1", "pindex": "0"})
        node = ET.SubElement(obj, tag("mesh"))
        vertices = ET.SubElement(node, tag("vertices"))
        for x, y, z in mesh.vertices:
            ET.SubElement(vertices, tag("vertex"), {"x": f"{x:.6f}", "y": f"{y:.6f}", "z": f"{z:.6f}"})
        triangles = ET.SubElement(node, tag("triangles"))
        for a, b, d in mesh.faces:
            ET.SubElement(triangles, tag("triangle"), {"v1": str(a), "v2": str(b), "v3": str(d)})
    build = ET.SubElement(model, tag("build"))
    for item in plate:
        x, y, z = item["position"]
        ET.SubElement(build, tag("item"), {"objectid": str(ids[item["part"]]),
                                         "transform": f"1 0 0 0 1 0 0 0 1 {x:.6f} {y:.6f} {z:.6f}"})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
                         '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        archive.writestr("_rels/.rels",
                         '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        archive.writestr("3D/3dmodel.model", ET.tostring(model, encoding="utf-8", xml_declaration=True))
    with zipfile.ZipFile(path) as archive:
        reopened = ET.fromstring(archive.read("3D/3dmodel.model"))
        assert reopened.get("unit") == "millimeter"
        assert len(reopened.find(tag("build"))) == len(plate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plates-only", action="store_true")
    parser.add_argument("--reuse-plates", action="store_true")
    args = parser.parse_args()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    downloads = ROOT / "site/downloads"
    read_first = (ROOT / "docs/build.ja.md").read_text()
    read_first = read_first.replace("(../site/", "(https://ktanino10.github.io/copilot-brick-display/")
    read_first = read_first.replace("(../design/", "(https://github.com/ktanino10/copilot-brick-display/blob/main/design/")
    read_first = read_first.replace("(rebuild.md)", "(https://ktanino10.github.io/copilot-brick-display/rebuild.html)")
    read_first = read_first.replace("(trial.ja.md)", "(https://ktanino10.github.io/copilot-brick-display/trial.html?guidance=trial-2026-09-19)")
    coupons = sorted(key for key in c["parts"] if key.startswith(("FIT-", "NP3-FIT-")))
    if not args.plates_only:
        with zipfile.ZipFile(downloads / "fit-coupons.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for key in coupons:
                archive.write(downloads / c["parts"][key]["stl"], f"{key}.stl")
            archive.write(downloads / "fit-log.csv", "fit-log.csv")
            archive.writestr("READ-FIRST-ja.md", read_first)
            archive.write(downloads / "interface.pdf", "interface.pdf")
    cache, results = {}, []
    for model in c["models"]:
        folder = downloads / model["id"]
        if not args.plates_only:
            with zipfile.ZipFile(folder / "print-kit.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for key in sorted({row["part"] for row in model["bom"]}):
                    archive.write(downloads / c["parts"][key]["stl"], f"parts/{key}.stl")
                for filename in ["bom.csv", "assembly.json", "drawings.pdf"]:
                    archive.write(folder / filename, filename)
                archive.writestr("READ-FIRST-ja.md", read_first)
                archive.write(downloads / "fit-coupons.zip", "fit-coupons.zip")
        plates_path = folder / "plates"
        plates_path.mkdir(exist_ok=True)
        if args.reuse_plates:
            manifest = json.loads((plates_path / "manifest.json").read_text())["plates"]
            counts = Counter((item["part"], plate["color"]) for plate in manifest for item in plate["items"])
            expected = Counter({(row["part"], row["color"]): row["quantity"] for row in model["bom"]})
            assert counts == expected, "Cached print layout no longer matches the current BOM"
            report = json.loads((ROOT / "validation/3mf.json").read_text())
            verified = next(item for item in report["models"] if item["model"] == model["id"])
            import hashlib
            for item in verified["files"]:
                assert hashlib.sha256((plates_path / item["file"]).read_bytes()).hexdigest() == item["sha256"]
            results.append({"model": model["id"], "plates": len(manifest), "instances": sum(counts.values()),
                            "bom_exact": True, "all_6mm_brim_envelopes_inside_16_to_240_mm": True})
            print(f"{model['id']}: rebuilt print ZIP; reused {len(manifest)} independently verified 3MF plates")
            continue
        manifest = []
        actual_counts = Counter()
        groups = defaultdict(list)
        for row in model["bom"]:
            groups[(row["color"], row.get("finish_color", ""), row.get("color_change_z_mm", ""))].extend(
                [row["part"]] * row["quantity"])
        for (color, finish_color, change_z), parts in groups.items():
            finish = (finish_color, float(change_z)) if finish_color else None
            for index, plate in enumerate(pack(parts, c), 1):
                suffix = f"-to-{finish_color}-z{str(change_z).replace('.', 'p')}" if finish else ""
                filename = f"{model['id']}-{color}{suffix}-{index:02}.3mf"
                write_3mf(plates_path / filename, color, plate, c, cache, finish)
                for i, item in enumerate(plate):
                    actual_counts[(item["part"], color)] += 1
                    x1, y1, x2, y2 = item["brim_box"]
                    assert min(x1, y1) >= 16 - 1e-6 and max(x2, y2) <= 240 + 1e-6
                    for previous in plate[:i]:
                        a1, b1, a2, b2 = previous["brim_box"]
                        assert min(x2, a2) <= max(x1, a1) or min(y2, b2) <= max(y1, b1)
                manifest.append({"file": filename, "color": color, "items": plate,
                                 "finish_color": finish_color, "manual_change_after_z_mm": change_z})
        expected = Counter({(row["part"], row["color"]): row["quantity"] for row in model["bom"]})
        assert actual_counts == expected
        write_json(plates_path / "manifest.json", {
            "units": "mm", "bed_nominal": [256, 256], "brim_reserved_mm": 6,
            "sliced": False, "printer_settings_validated": False,
            "note": "Generic 3MF. Confirm real exclusions, orientation, bridge paths and nozzle profile. Print by layer, not sequential by object.",
            "plates": manifest,
        })
        expected_files = {item["file"] for item in manifest} | {"manifest.json"}
        for stale in plates_path.iterdir():
            if stale.is_file() and stale.name not in expected_files and stale.suffix == ".3mf":
                stale.unlink()
        with zipfile.ZipFile(folder / "plates.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(plates_path.iterdir()):
                archive.write(path, path.name)
        results.append({"model": model["id"], "plates": len(manifest),
                        "instances": sum(actual_counts.values()), "bom_exact": True,
                        "all_6mm_brim_envelopes_inside_16_to_240_mm": True})
        print(f"{model['id']}: exact BOM packaged across {len(manifest)} single-color 3MF plates")
    write_json(ROOT / "validation/print-packages.json", {
        "status": "PASS_GEOMETRY_AND_QUANTITIES_ONLY", "sliced": False, "models": results,
    })


if __name__ == "__main__":
    main()
