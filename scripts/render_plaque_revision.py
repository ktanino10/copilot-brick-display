"""Reuse the unchanged pre-plaque interval; actually rerender every frame containing the new plaque."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from design import ROOT, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["A", "B", "C"], required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    model = next(m for m in c["models"] if m["id"] == args.model)
    old_c = json.loads((args.baseline / "design/catalog.json").read_text())
    old_model = next(m for m in old_c["models"] if m["id"] == args.model)
    if model["placements"] != old_model["placements"] or model["steps"] != old_model["steps"]:
        raise ValueError("Changed placement/order cannot reuse an earlier animation interval")
    unchanged = [p for p in model["placements"] if p["part"] != f"NP3-TEXT-{args.model}"]
    for placement in unchanged:
        if c["parts"][placement["part"]]["sha256"] != old_c["parts"][placement["part"]]["sha256"]:
            raise ValueError("A non-plaque master changed; refuse historical frame reuse")
    start = 2 + (next(p["step"] for p in model["placements"] if p["part"] == f"NP3-TEXT-{args.model}") - 1) * 8
    old_movie = args.baseline / "site/media" / f"{args.model}-assembly.mp4"
    previous = json.loads((args.baseline / "validation" / f"video-{args.model}.json").read_text())
    if hashlib.sha256(old_movie.read_bytes()).hexdigest() != previous["sha256"]:
        raise ValueError("Unverified prior movie; do not claim a valid reused frame interval")
    frames = ROOT / "build/frames" / args.model
    frames.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(old_movie), "-frames:v", str(start - 1),
                    str(frames / "frame-%04d.png")], check=True)
    native = ROOT / "site/downloads" / args.model / f"{args.model}.blend"
    blender = os.environ.get("BLENDER", "blender")
    subprocess.run([blender, "--background", "--factory-startup", "--threads", "2", str(native),
                    "--python", str(ROOT / "scripts/blender_render.py"), "--",
                    "--model", args.model, "--start-frame", str(start)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/render_movies.py"), "--model", args.model, "--encode-only"],
                   cwd=ROOT, check=True)
    write_json(ROOT / "validation" / f"plaque-render-{args.model}.json", {
        "status": "PASS_PARTIAL_REUSE_ACTUAL_RENDER", "revision": c["revision"],
        "model": args.model, "unchanged_interval": [1, start - 1],
        "reused_interval_source": "Decoded verified generic4.0 Blender movie; plaque is not visible in these frames.",
        "previous_movie_sha256": previous["sha256"],
        "newly_rendered_frames_from": start,
        "unchanged_body_meshes_and_camera": True, "physical_simulation": False,
    })


if __name__ == "__main__":
    main()
