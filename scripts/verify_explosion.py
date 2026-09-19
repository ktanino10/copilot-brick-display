"""Apply actual browser motion samples to reopened native parts."""

import json

import FreeCAD as App

from design import ROOT, write_json


def moved(shape, delta):
    copy = shape.copy()
    copy.translate(App.Vector(*delta))
    return copy


def main():
    samples = json.loads((ROOT / "build/explosion-samples.json").read_text())
    records = []
    for model in "ABC":
        doc = App.openDocument(str(ROOT / "site/downloads" / model / f"{model}.FCStd"))
        card = next(obj.Shape.copy() for obj in doc.Objects if getattr(obj, "PartID", "") == "MSG-CARD")
        dock = next(obj.Shape.copy() for obj in doc.Objects if getattr(obj, "PartID", "") == "MSG-DOCK")
        old = moved(card, [0, -.4, 0]).common(moved(dock, [0, 0, .03])).Volume
        assert old > 1, "The original 1-percent symptom should reproduce"
        maximum = 0
        for sample in (case for case in samples if case["model"] == model):
            volume = moved(card, sample["cardOffset"]).common(moved(dock, sample["dockOffset"])).Volume
            maximum = max(maximum, volume)
            assert volume < 1e-5, f"{model} at {sample['percent']}%: {volume}"
        records.append({"model": model, "samples": 101, "original_1_percent_overlap_mm3": old,
                        "fixed_maximum_overlap_mm3": maximum})
        App.closeDocument(doc.Name)
        print("PASS_EXPLOSION", records[-1], flush=True)
    write_json(ROOT / "validation/explosion-motion.json", {
        "status": "PASS_REAL_NATIVE_MOTION_CHECK", "models": records,
        "motion_source": "site/assembly-motion.js, executed by tests/motion.mjs",
        "continuous_argument": "No sideways travel until insertion depth plus 0.6 mm is cleared; the card tracks dock lift.",
        "physical_simulation": False,
    })


if __name__ == "__main__":
    main()
