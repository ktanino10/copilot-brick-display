"""Extract the supplied white mark inside its black circle; never distribute the raster."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from design import ROOT, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="User-provided local image; not copied into the repository.")
    args = parser.parse_args()
    gray = np.asarray(Image.open(args.source).convert("L"))
    yy, xx = np.where(gray < 100)
    diameter = int(xx.max() - xx.min() + 1)
    cx = (int(xx.min()) + int(xx.max())) / 2
    cy = int(yy.min()) + diameter / 2 - .5
    y, x = np.indices(gray.shape)
    circle = (x - cx) ** 2 + (y - cy) ** 2 <= (diameter / 2 - 1.0) ** 2
    silhouette = (gray >= 160) & circle
    scratch = ROOT / "build/logo-trace"
    scratch.mkdir(parents=True, exist_ok=True)
    bitmap = scratch / "white-mark.pbm"
    Image.fromarray(np.where(silhouette, 0, 255).astype("uint8")).convert("1").save(bitmap)
    output = scratch / "mark.geojson"
    subprocess.run(["potrace", "--backend", "geojson", "--turdsize", "8", "--opttolerance", ".2",
                    "--output", str(output), str(bitmap)], check=True)
    data = json.loads(output.read_text())
    polygons = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        if geometry["type"] != "Polygon":
            raise ValueError(f"Unexpected logo contour kind: {geometry['type']}")
        rings = []
        for ring in geometry["coordinates"]:
            rings.append([[round((px - cx) / diameter, 7),
                           round((py - (gray.shape[0] - cy)) / diameter, 7)] for px, py in ring])
        polygons.append(rings)
    if len(polygons) != 1:
        raise ValueError(f"Expected one supported white silhouette; got {len(polygons)}")
    write_json(ROOT / "resources/github-mark-relief.json", {
        "description": "Derived white silhouette from the user-supplied black-circle GitHub mark.",
        "units": "normalized to black-disc diameter 1; +Y upward",
        "provenance": "User-supplied artwork transformation. Original raster and path are not distributed.",
        "tracer": "potrace 1.16, GeoJSON, tolerance0.2px; closed polygon coordinates",
        "source_circle_diameter_pixels": diameter,
        "source_mask_sha256": hashlib.sha256(silhouette.tobytes()).hexdigest(),
        "polygons": polygons,
        "physical_interpretation": "White relief fused onto a solid black backing; not independent floating pieces.",
    })
    print("Derived CAD contours:", len(polygons), "polygons,", sum(len(r) for p in polygons for r in p), "points")


if __name__ == "__main__":
    main()
