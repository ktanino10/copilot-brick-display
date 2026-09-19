"""Render real CAD SVG sheets with librsvg; independent of a browser/DevTools runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

from artifact_metadata import strip_png_text

ROOT=Path(__file__).resolve().parents[1]


def main():
    converter=shutil.which("rsvg-convert")
    if not converter:
        raise RuntimeError("rsvg-convert is required for non-browser SVG previews")
    version=subprocess.run([converter,"--version"],check=True,capture_output=True,text=True).stdout.strip()
    index=json.loads((ROOT/"drawings/index.json").read_text())
    folder=ROOT/"media/drawings"
    folder.mkdir(parents=True,exist_ok=True)
    sheets=[]
    for item in index["sheets"]:
        source=ROOT/"drawings"/item["file"]
        output=folder/(source.stem+".png")
        subprocess.run([converter,"--format=png","--width=1260","--height=891",
                        "--output",str(output),str(source)],check=True)
        strip_png_text(output)
        raw=output.read_bytes()
        size=struct.unpack_from(">II",raw,16)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or size!=(1260,891):
            raise ValueError(f"Incorrect drawing preview: {output.name}")
        sheets.append({"source_svg":source.relative_to(ROOT).as_posix(),
                       "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
                       "output_png":output.relative_to(ROOT).as_posix(),
                       "output_sha256":hashlib.sha256(raw).hexdigest(),
                       "source_sheet_mm":[420,297],"preview_pixels":list(size)})
    report={"status":"pass","revision":"T2-R1","converter":version,
            "source":"Actual CAD-derived SVG sheets; no source photograph or replacement illustration",
            "sheets":sheets,"browser_verification":False}
    (ROOT/"validation/drawing-previews.json").write_text(json.dumps(report,indent=2)+"\n")
    print("LIBRSVG_PREVIEW_PASS",version,len(sheets))


if __name__=="__main__":
    main()
