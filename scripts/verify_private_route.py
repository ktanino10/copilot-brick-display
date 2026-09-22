"""Public evidence for the documented placeholder-only private-route exercise."""

import copy
import argparse
import json
from pathlib import Path

import FreeCAD as App
import Part

from design import ROOT, build_catalog, load_parameters, write_json
from front_nameplate import message_faces


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, default=ROOT / ".private/route-check-output/B")
    args = parser.parse_args()
    folder = args.folder.resolve()
    if not folder.is_relative_to(ROOT / ".private"):
        raise ValueError("The private-route fixture must remain in the ignored private directory.")
    fixture = json.loads((ROOT / "design/personalization.private.example.json").read_text())
    manifest = json.loads((folder / "private-manifest.json").read_text())
    if manifest["lines"] != fixture["lines"]:
        raise ValueError("Do not create a public test receipt from real private display values; use only the documented placeholder fixture.")
    parameters = load_parameters()
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    public = App.openDocument(str(ROOT / "site/downloads/B/B.FCStd"))
    public_plate = next(obj for obj in public.Objects if getattr(obj, "PartID", "") == "NP3-TEXT-B")
    assert json.loads(public_plate.MessageLines) == parameters["message"]["lines"]
    assert abs(public_plate.Shape.Volume - catalog["parts"]["NP3-TEXT-B"]["volume_mm3"]) < .001
    private = App.openDocument(str(folder / "assembly.FCStd"))
    private_parts = [obj for obj in private.Objects if hasattr(obj, "PartID")]
    target = next(obj for obj in private_parts if obj.PartID == "NP3-TEXT-B")
    assert json.loads(target.MessageLines) == fixture["lines"]
    assert len(private_parts) == 150
    native_plate = App.openDocument(str(folder / "plate.FCStd"))
    plate = native_plate.getObject("ReplacementPlate")
    step_plate = Part.read(str(folder / "plate.step"))
    assembly_step = Part.read(str(folder / "assembly.step"))
    assert plate.Shape.isValid() and len(plate.Shape.Solids) == 1
    assert abs(plate.Shape.Volume - step_plate.Volume) < .001
    assert abs(target.Shape.Volume - plate.Shape.Volume) < .001
    assert len(assembly_step.Solids) == 150 and assembly_step.isValid()
    oversized = copy.deepcopy(parameters)
    oversized["message"]["lines"][0] = "X" * 100
    spec = build_catalog(parameters)["parts"]["NP3-TEXT-B"]
    try:
        message_faces(spec, oversized)
    except ValueError as error:
        assert "exceeds available" in str(error) or "exceeds the available face width" in str(error)
        assert "X" * 100 not in str(error)
    else:
        raise AssertionError("An overlong line must stop rather than be compressed or truncated")
    for document in (native_plate, private, public):
        App.closeDocument(document.Name)
    write_json(ROOT / "validation/private-route.json", {
        "status": "PASS_PRIVATE_OUTPUT_BOUNDARY_AND_NATIVE_REOPEN",
        "fixture": "documented placeholders only; no real private values used",
        "model": "B", "private_native_plate_solids": 1, "private_assembly_instances": 150,
        "public_native_message_and_volume_unchanged": True,
        "native_step_reopened": True, "overlong_text_explicitly_rejected": True,
        "private_values_echoed_or_published": False, "physical_fit_tested": False,
        "scope": "This proves the software path for the placeholder fixture, not arbitrary lettering printability or physical fit.",
    })
    print("PASS private route: actual native/STEP reopened, public model unchanged, oversized text explicitly stopped.")


if __name__ == "__main__":
    main()
