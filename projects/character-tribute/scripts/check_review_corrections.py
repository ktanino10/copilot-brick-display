"""Guard review03/04/05 and prove the completed mechanical masters were not regenerated."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from check_release import validate_bom_categories,validate_guide_tool_angles

ROOT=Path(__file__).resolve().parents[1]
BASELINE="46c7661d9f7010e14fa632ffde8cb8d8c260ed6f"


def main():
    catalog=json.loads((ROOT/"catalog.json").read_text())
    paths=[ROOT/"native/character-tribute.FCStd",ROOT/"native/character-tribute.step",
           ROOT/"media/model.glb",ROOT/"media/finished.png"]
    paths+=sorted((ROOT/"native/parts").glob("*.step"))+sorted((ROOT/"meshes").glob("*.stl"))
    preserved={}
    for path in paths:
        name=path.relative_to(ROOT).as_posix()
        original=subprocess.run(["git","show",f"{BASELINE}:projects/character-tribute/{name}"],
                                cwd=ROOT,check=True,capture_output=True).stdout
        current=path.read_bytes()
        if current!=original:
            raise ValueError(f"An immutable mechanical/display master changed: {name}")
        preserved[name]=hashlib.sha256(current).hexdigest()
    for suffix in ("md","html"):
        validate_guide_tool_angles(catalog,(ROOT/f"docs/howto.ja.{suffix}").read_text())
    tools=validate_bom_categories(catalog,(ROOT/"docs/bom.csv").read_bytes())
    with zipfile.ZipFile(ROOT/"downloads/print-pack.zip") as archive:
        if validate_bom_categories(catalog,archive.read("docs/bom.csv"))!=tools:
            raise ValueError("Archive tool count differs from canonical BOM")
    before=json.loads((ROOT/"validation/transfer-regression.json").read_text())
    motion=json.loads((ROOT/"validation/transfer-motion.json").read_text())
    partial=json.loads((ROOT/"validation/transfer-video-update.json").read_text())
    blend_hash=hashlib.sha256((ROOT/"media/character-assembly.blend").read_bytes()).hexdigest()
    if (motion["status"]!="pass" or motion["sampled_max_intersection_mm3"]>1e-5
            or motion["source_blend_sha256"]!=blend_hash or partial["updated_blend_sha256"]!=blend_hash
            or partial["status"]!="pass"):
        raise ValueError("Transfer evidence does not match the delivered native scene")
    for name,expected in (("assembly",[384,441]),("disassembly",[136,193])):
        record=partial["videos"][name]
        if record["rerendered_frame_range_inclusive"]!=expected or record["unchanged_decoded_frames_verified"]!=518:
            raise ValueError("Rerender exceeded or missed the declared bounded scope")
    report={"status":"pass","baseline_commit":BASELINE,"immutable_master_sha256":preserved,
            "preserved_master_count":len(preserved),"old_collisions":before["samples"],
            "new_max_intersection_mm3":motion["sampled_max_intersection_mm3"],
            "continuous_transfer_conditions":motion["continuous_conditions"],
            "badge_white_angle_deg":next(i["tool_tip_rotation_deg"] for i in catalog["instances"] if i["id"]=="badge-white"),
            "bom_and_zip_tool_total":tools,"coupon_tool_column":0,
            "rendered_frames_per_movie":58,"reused_decoded_frames_per_movie":518,
            "native_geometry_recomputed":False,"full_animation_rerendered":False}
    (ROOT/"validation/review-corrections.json").write_text(json.dumps(report,indent=2)+"\n")
    print("REVIEW_03_04_05_GUARD_PASS",len(preserved),tools)


if __name__=="__main__":
    main()
