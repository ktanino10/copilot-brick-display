"""Sequential Blender rendering, real ffmpeg encoding and decode validation."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from design import ROOT, write_json


def timecode(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["A", "B", "C"], required=True)
    parser.add_argument("--encode-only", action="store_true")
    args = parser.parse_args()
    c = json.loads((ROOT / "design/catalog.json").read_text())
    model = next(x for x in c["models"] if x["id"] == args.model)
    native = ROOT / "site/downloads" / args.model / f"{args.model}.blend"
    if not args.encode_only:
        subprocess.run([
            "blender", "--background", "--factory-startup", "--threads", "2", str(native),
            "--python", "scripts/blender_render.py", "--", "--model", args.model,
        ], check=True, cwd=ROOT)
    movie = ROOT / "site/media" / f"{args.model}-assembly.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "20",
        "-i", str(ROOT / "build/frames" / args.model / "frame-%04d.png"),
        "-c:v", "libx264", "-threads", "2", "-crf", "21", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-map_metadata", "-1", "-an", str(movie),
    ], check=True)
    result = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-show_entries",
        "stream=codec_name,pix_fmt,width,height,nb_read_frames,r_frame_rate:format=duration",
        "-of", "json", str(movie),
    ], check=True, capture_output=True, text=True)
    probe = json.loads(result.stdout)
    stream = probe["streams"][0]
    expected_frames = 2 + len(model["steps"]) * 8 + 100
    assert int(stream["nb_read_frames"]) == expected_frames
    assert stream["codec_name"] == "h264" and stream["pix_fmt"] == "yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(movie), "-f", "null", "-"], check=True)
    raw = movie.read_bytes()
    assert raw.find(b"moov") < raw.find(b"mdat"), "MP4 is not faststart"
    captions = ["WEBVTT", ""]
    for step in model["steps"]:
        start = (1 + (step["number"] - 1) * 8) / 20
        end = (1 + step["number"] * 8) / 20
        captions += [f"{timecode(start)} --> {timecode(end)}",
                     f"{step['number']:02} / {len(model['steps']):02}  {step['title']}", ""]
    captions += [f"{timecode((1 + len(model['steps']) * 8) / 20)} --> {timecode(expected_frames / 20)}",
                 "完成形 / CAD形状の組立表示です。物理シミュレーションではありません。", ""]
    movie.with_suffix(".vtt").write_text("\n".join(captions))
    write_json(ROOT / "validation" / f"video-{args.model}.json", {
        "status": "PASS_ACTUAL_RENDER_ENCODE_DECODE",
        "model": args.model, "source": f"downloads/{args.model}/{args.model}.blend",
        "renderer": "Blender Workbench", "probe": probe, "faststart": True,
        "full_decode": True, "sha256": hashlib.sha256(raw).hexdigest(),
    })
    print(f"PASS {args.model}: {expected_frames} real rendered frames, H.264, full decode")


if __name__ == "__main__":
    main()
