"""Encode actual Blender frames and decode every frame before publishing the movie."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required")
    frames = sorted((ROOT / "media/frames").glob("frame_*.png"))
    if len(frames) != 504 or any(p.name != f"frame_{i:04d}.png" for i, p in enumerate(frames, 1)):
        raise ValueError("Expected the complete, contiguous 504-frame Blender render")
    subprocess.run([ffmpeg, "-nostdin", "-y", "-v", "error", "-framerate", "24",
                    "-i", "media/frames/frame_%04d.png", "-i", "media/assembly.ja.vtt",
                    "-map", "0:v:0", "-map", "1:0",
                    "-c:v", "libx264", "-threads", "1", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=jpn", "-disposition:s:0", "default",
                    "-movflags", "+faststart", "media/assembly.mp4"],
                   cwd=ROOT, check=True)
    movie = ROOT / "media/assembly.mp4"
    probe = subprocess.run([ffprobe, "-v", "error",
                            "-show_entries", "stream=codec_name,codec_type,width,height,nb_frames,avg_frame_rate,duration",
                            "-of", "json", str(movie)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    stream = next(item for item in streams if item["codec_type"] == "video")
    captions = [item for item in streams if item["codec_type"] == "subtitle"]
    if len(captions) != 1 or captions[0]["codec_name"] != "mov_text":
        raise ValueError("Japanese MP4 subtitle track is missing")
    if (stream["codec_name"], stream["width"], stream["height"], stream["nb_frames"],
        stream["avg_frame_rate"]) != ("h264", 640, 640, "504", "24/1"):
        raise ValueError(f"Unexpected encoded stream: {stream}")
    decoded = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-threads", "1", "-i", str(movie),
                              "-map", "0:v:0", "-f", "framemd5", "-"],
                             capture_output=True, text=True, check=True)
    hashes = [line.rsplit(",", 1)[1].strip() for line in decoded.stdout.splitlines()
              if line and not line.startswith("#")]
    if len(hashes) != 504 or len(set(hashes)) < 100 or hashes[0] == hashes[-1]:
        raise ValueError("Decoded video is incomplete or does not show the changing assembly")
    report = {"status": "pass", "encoded_stream": stream, "decoded_frames": len(hashes),
              "distinct_decoded_frames": len(set(hashes)), "decode_errors": 0,
              "source": "504 real keyframed Blender renders from the audited CAD meshes",
              "mp4_sha256": hashlib.sha256(movie.read_bytes()).hexdigest(),
              "japanese_captions": "media/assembly.ja.vtt",
              "caption_mode": "Default Japanese mov_text track plus WebVTT sidecar; not burned in (local FFmpeg has no drawtext filter).",
              "note": "Animation time is not print time or adhesive cure time."}
    (ROOT / "validation/video.json").write_text(json.dumps(report, indent=2) + "\n")
    print("VIDEO_ENCODE_DECODE_PASS", stream, flush=True)


if __name__ == "__main__":
    main()
