"""Measured, explicit two-row typography; carrier geometry and installation are separate."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import FreeCAD as App
import Part

from legible_lettering import raw_row, face_data, edited_glyph
from letter_metrics import straight_strokes

ROOT = Path(__file__).resolve().parents[1]


def lettering_contract(spec, parameters):
    message = parameters["message"]
    contract = {
        "lines": message["lines"], "sizes": spec["text_sizes"], "heights": spec["text_heights"],
        "fonts": [message["bold_font"], message["font"]], "bottoms": message["line_bottoms"],
        "width": spec["width"], "side_taper": message["side_taper"], "thickness": message["thickness"],
        "goals": spec["lettering_goals"], "minimum_straight_stroke": message["minimum_straight_stroke"],
    }
    contract["font_hashes"] = [hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in contract["fonts"]]
    return contract


@lru_cache(maxsize=32)
def cached_rows(serialized):
    from legible_metrics import plan_rows, ink_shape, material_core_split
    contract = json.loads(serialized)
    raw_shapes, raw = [], []
    for index, (text, font, size, height) in enumerate(zip(
            contract["lines"], contract["fonts"], contract["sizes"], contract["heights"]), 1):
        glyphs, sx, sy = raw_row(text, ROOT / font, size, height, uniform=index == 2)
        if sx < 1 - 1e-8 or sy < 1 - 1e-8:
            raise ValueError("Do not shrink the declared type scale to force a fit.")
        raw_shapes.append(glyphs)
        raw.append({"number": index, "glyphs": [
            {"index": i, "character": char, "faces": face_data(shape)} for i, char, shape in glyphs]})
    maximum = contract["width"] - 2 * contract["side_taper"] - 4
    plans = [plan_rows([row], goals, maximum)[0] for row, goals in zip(raw, contract["goals"])]
    rows = []
    for index, (glyphs, plan, bottom, text) in enumerate(zip(
            raw_shapes, plans, contract["bottoms"], contract["lines"]), 1):
        revised = []
        for (number, character, source), operation in zip(glyphs, plan["glyphs"]):
            if number != operation["index"] or character != operation["character"]:
                raise ValueError("Glyph plan does not preserve the exact display text.")
            shape = edited_glyph(source, operation)
            holes = lambda solid: sum(len(face.Wires) - 1 for face in solid.Faces)
            if len(shape.Faces) != len(source.Faces) or holes(shape) != holes(source):
                raise ValueError("A glyph edit changed connected components or closed-hole count.")
            neck = material_core_split(ink_shape({"faces": face_data(shape)}))
            if neck is not None and neck < contract["minimum_straight_stroke"]:
                raise ValueError("A counter edit leaves an undersized persistent material neck; stop and review that glyph.")
            shape.translate(App.Vector(operation["extra_x_mm"], 0, 0))
            revised.append((number, character, shape))
        bound = Part.makeCompound([shape for _, _, shape in revised]).BoundBox
        if bound.XLength > maximum + 1e-5:
            raise ValueError(f"Display text exceeds the available face width: {bound.XLength:.4f}/{maximum:.4f}mm; stop rather than truncate or compress.")
        if abs(bound.YLength - contract["heights"][index - 1]) > 1e-5:
            raise ValueError("Actual glyph height differs from the declared row height.")
        gaps = [a[2].distToShape(b[2])[0] for a, b in zip(revised, revised[1:])]
        if gaps and min(gaps) < contract["goals"][index - 1]["adjacent_glyph_clearance"] - .006:
            raise ValueError("Actual BRep glyph clearance is below the declared sampled target tolerance.")
        faces = [face for _, _, shape in revised for face in shape.Faces]
        gauges = straight_strokes(faces)
        if min(gauge["width_mm"] for gauge in gauges) < contract["minimum_straight_stroke"]:
            raise ValueError("Printed lettering has an undersized measured positive straight stroke.")
        offset = App.Vector((contract["width"] - bound.XLength) / 2 - bound.XMin,
                            bottom - bound.YMin, contract["thickness"])
        for _, _, shape in revised:
            shape.translate(offset)
        rows.append({"number": index, "text": text, "glyphs": revised, "gauges": gauges,
                     "width_mm": bound.XLength, "height_mm": bound.YLength,
                     "minimum_gap_mm": min(gaps) if gaps else None})
    return rows


def revised_rows(spec, parameters):
    rows = cached_rows(json.dumps(lettering_contract(spec, parameters), sort_keys=True))
    return [{**row, "glyphs": [(i, char, shape.copy()) for i, char, shape in row["glyphs"]]} for row in rows]


def message_faces(spec, parameters):
    return [(row["text"], [face for _, _, shape in row["glyphs"] for face in shape.Faces], row["gauges"])
            for row in revised_rows(spec, parameters)]
