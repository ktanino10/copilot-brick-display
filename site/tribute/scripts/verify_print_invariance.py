"""Compare the new print-pose assembly to the immutable pre-flip T2 native snapshot."""
import json
from pathlib import Path
import subprocess
import tempfile

import FreeCAD as App

ROOT=Path(__file__).resolve().parents[1]
BASELINE="6e065f53f49518a7947855b72ee647ad9b589b5e"


def shapes(path):
    doc=App.openDocument(str(path))
    result={o.InstanceID:o.Shape.copy() for o in doc.Objects if hasattr(o,"InstanceID")}
    App.closeDocument(doc.Name)
    return result


def main():
    relative="projects/character-tribute/native/character-tribute.FCStd"
    data=subprocess.run(["git","show",f"{BASELINE}:{relative}"],cwd=ROOT,
                        check=True,capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="pose-comparison-",dir=ROOT/"validation") as folder:
        baseline=Path(folder)/"baseline.FCStd"
        baseline.write_bytes(data)
        old=shapes(baseline)
    current=shapes(ROOT/"native/character-tribute.FCStd")
    if set(old)!=set(current):
        raise ValueError("Print-pose revision changed assembly instances")
    records={}
    for key,shape in current.items():
        a,b=shape.optimalBoundingBox(False,False),old[key].optimalBoundingBox(False,False)
        delta=max(abs(x-y) for x,y in zip([a.XMin,a.YMin,a.ZMin,a.XMax,a.YMax,a.ZMax],
                                         [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]))
        volume=abs(shape.Volume-old[key].Volume)
        if delta>.001 or volume>.1:
            raise ValueError(f"Final assembled geometry moved: {key}")
        records[key]={"bounds_max_delta_mm":delta,"volume_delta_mm3":volume}
    a,b=current["capture-frame"],old["capture-frame"]
    difference=a.cut(b).Volume+b.cut(a).Volume
    if difference>.1:
        raise ValueError("Capture-frame symmetric difference is not numerically zero")
    report={"status":"pass","baseline_commit":BASELINE,"manufacturing_revision":"T2-R1",
            "instances":records,"capture_frame_symmetric_difference_mm3":difference,
            "note":"Print pose and inverse placement changed; final assembled geometry retained."}
    (ROOT/"validation/print-pose-invariance.json").write_text(json.dumps(report,indent=2)+"\n")
    print("ASSEMBLY_POSE_INVARIANCE_PASS",len(records),difference)


if __name__=="__main__":
    main()
