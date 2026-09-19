"""Preserve old validated renders outside the explicitly changed transfer interval."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RANGES={"assembly":(384,441),"disassembly":(136,193)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    videos={}
    checkout=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    for name,(first,last) in RANGES.items():
        movie=ROOT/f"media/{name}.mp4"
        folder=ROOT/"media/frames"/name
        folder.mkdir(parents=True,exist_ok=True)
        if any(folder.iterdir()):
            raise ValueError(f"Partial-render workspace must start empty: {name}")
        source_hash=digest(movie)
        subprocess.run([ffmpeg,"-nostdin","-v","error","-threads","1","-i",str(movie),
                        "-map","0:v:0","-fps_mode","passthrough",str(folder/"frame_%04d.png")],check=True)
        frames=sorted(folder.glob("frame_*.png"))
        if len(frames)!=576:
            raise ValueError("The validated source movie must decode to576 frames")
        videos[name]={"source_mp4_sha256":source_hash,"source_checkout_commit":checkout,
                      "rerendered_frame_range_inclusive":[first,last],
                      "decoded_frame_sha256":{str(i):digest(path) for i,path in enumerate(frames,1)}}
    report={"status":"prepared","method":"Decode prior validated CGI frames; replace only changed transfer frames and explicit boundaries",
            "videos":videos}
    (ROOT/"validation/transfer-video-update.json").write_text(json.dumps(report,indent=2)+"\n")
    print("PARTIAL_RENDER_BASE_PREPARED")


def verify():
    path=ROOT/"validation/transfer-video-update.json"
    report=json.loads(path.read_text())
    for name,record in report["videos"].items():
        first,last=record["rerendered_frame_range_inclusive"]
        unchanged=0
        for frame,previous in record["decoded_frame_sha256"].items():
            index=int(frame)
            current=digest(ROOT/f"media/frames/{name}/frame_{index:04d}.png")
            if not first<=index<=last:
                if current!=previous:
                    raise ValueError(f"Frame outside changed interval was altered: {name}/{index}")
                unchanged+=1
        record["unchanged_decoded_frames_verified"]=unchanged
        record["rerendered_frames"]=last-first+1
    report["status"]="pass"
    report["updated_blend_sha256"]=digest(ROOT/"media/character-assembly.blend")
    path.write_text(json.dumps(report,indent=2)+"\n")
    print("PARTIAL_RENDER_SCOPE_PASS")


if __name__=="__main__":
    if "--prepare" in sys.argv:
        prepare()
    else:
        verify()
