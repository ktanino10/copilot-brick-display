"""Canonical part catalogue and placements. Coordinates and STL units are mm."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_parameters():
    return json.loads((ROOT / "design/parameters.json").read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def brick_id(nx, ny, height):
    return f"BR-{nx:02d}x{ny:02d}-H{round(height * 10):03d}"


def cell(v, course, x):
    """Profile is discrete design data, not a scaled copy of another variant."""
    width = v["body_width"]
    goggle = v["goggle_bottom"]
    count = v["body_courses"]
    if course < goggle:
        inset = max(0, v["bottom_inset"] - course)
        if not inset <= x < width - inset:
            return None
        if course == 0:
            return ("magenta", *v["chin_y"])
        rim = 2
        if x < inset + rim or x >= width - inset - rim:
            return ("magenta", *v["headset_y"])
        color = "black"
        if v["eye_courses"][0] <= course <= v["eye_courses"][1]:
            if x in v["eye_columns"]:
                color = "green"
        return (color, *v["face_y"])
    inset = 2 if course == count - 1 else 1 if course == count - 2 else 0
    if not inset <= x < width - inset:
        return None
    if course in (goggle, count - 2, count - 1):
        return ("cyan", *v["goggle_y"])
    middle = width // 2
    is_frame = x < 2 or x >= width - 2 or middle - 1 <= x <= middle
    return ("cyan", *v["goggle_y"]) if is_frame else ("black", *v["face_y"])


def split_run(start, end, course):
    # Shift joints by two studs between courses; avoid a new one-stud cantilever.
    cursor = start
    first = 2 if course % 2 else 4
    while cursor < end:
        length = min(first if cursor == start else 4, end - cursor)
        if end - cursor - length == 1:
            length += 1
        yield cursor, length
        cursor += length


def build_catalog(p):
    pitch = p["interface"]["pitch"]
    height = p["interface"]["brick_height"]
    parts = {}
    models = []
    message = p["message"]

    def register(nx, ny, h):
        key = brick_id(nx, ny, h)
        parts[key] = {
            "id": key, "kind": "brick", "studs": [nx, ny], "height": h,
            "top_studs": True, "socket": True, "stl": f"parts/{key}.stl",
            "orientation": "underside_on_bed_studs_up",
        }
        return key

    parts["MSG-DOCK"] = {
        "id": "MSG-DOCK", "kind": "dock", "studs": message["dock_studs"],
        "height": message["dock_height"], "top_studs": False, "socket": True,
        "stl": "parts/MSG-DOCK.stl", "orientation": "sockets_on_bed_slot_up",
    }
    parts["MSG-CARD"] = {
        "id": "MSG-CARD", "kind": "card", "top_studs": False, "socket": False,
        "stl": "parts/MSG-CARD.stl", "orientation": "flat_back_on_bed_text_up",
        "text": message["lines"],
        "optional_color_change_z": message["card_thickness"],
    }
    for v in p["variants"]:
        placements = []
        steps = []

        def step(title):
            index = len(steps) + 1
            steps.append({"number": index, "title": title, "instances": []})
            return index

        def place(part, color, xyz, number, rotation=(0, 0, 0)):
            instance = f'{v["id"]}-{len(placements) + 1:03d}'
            placements.append({
                "id": instance, "part": part, "color": color,
                "position": [round(n, 6) for n in xyz], "rotation": list(rotation),
                "step": number,
            })
            steps[number - 1]["instances"].append(instance)

        bw, bd = v["base_studs"]
        number = step("台座を水平な机に置く")
        base_x = 0
        for segment in v["base_segments_x"]:
            place(register(segment, bd, height), "black", [base_x * pitch, 0, 0], number)
            base_x += segment
        if base_x != bw:
            raise ValueError("Base segments must exactly fill the nominal width")
        number = step("前側の予約スタッドにメッセージドックを載せる")
        dock_x = (bw - message["dock_studs"][0]) * pitch / 2
        dock_y = pitch
        place("MSG-DOCK", "black", [dock_x, dock_y, height], number)
        offset_x = (bw - v["body_width"]) // 2
        for course in range(v["body_courses"]):
            number = step(f"本体 {course + 1} 段目を左から載せる")
            x = 0
            while x < v["body_width"]:
                spec = cell(v, course, x)
                end = x + 1
                while end < v["body_width"] and cell(v, course, end) == spec:
                    end += 1
                if spec is not None:
                    color, y0, y1 = spec
                    for start, length in split_run(x, end, course):
                        place(register(length, y1 - y0, height), color,
                              [(offset_x + start) * pitch, y0 * pitch,
                               (course + 1) * height], number)
                x = end
        number = step("頭頂のマゼンタのプレートを載せる")
        crest_start = (bw - v["crest_width"]) // 2
        for x, length in split_run(0, v["crest_width"], v["body_courses"]):
            place(register(length, v["face_y"][1] - v["face_y"][0],
                           v["crest_height"]), "magenta",
                  [(crest_start + x) * pitch, v["face_y"][0] * pitch,
                   (v["body_courses"] + 1) * height], number)
        number = step("文字カードをドックへ上から差し込み、転倒と保持を確認する")
        place("MSG-CARD", "cyan", [
            dock_x + (message["dock_studs"][0] * pitch - message["card_width"]) / 2,
            dock_y + message["slot_center_y"] + message["card_thickness"] / 2,
            height + message["dock_height"] - message["slot_depth"],
        ], number, (90, 0, 0))
        quantities = Counter((i["part"], i["color"]) for i in placements)
        bom = [{"part": key, "color": color, "quantity": n,
                "stl": parts[key]["stl"]}
               for (key, color), n in sorted(quantities.items())]
        models.append({
            **v, "placements": placements, "steps": steps, "bom": bom,
            "part_count": len(placements), "unique_prints": len({i["part"] for i in placements}),
        })
    for correction in p["fit_candidates"]["male_diameter_corrections"]:
        diameter = p["interface"]["reference_stud_diameter"] + correction
        key = f"FIT-M-D{round(diameter * 100):03d}"
        parts[key] = {
            "id": key, "kind": "male_coupon", "studs": [4, 2], "height": 3.2,
            "top_studs": True, "socket": False, "male_correction": correction,
            "stl": f"parts/{key}.stl", "orientation": "flat_bottom_studs_up",
        }
    for clearance in p["fit_candidates"]["female_radial_clearances"]:
        sign = "P" if clearance >= 0 else "M"
        key = f"FIT-F-C{sign}{round(abs(clearance) * 100):02d}"
        parts[key] = {
            "id": key, "kind": "female_coupon", "studs": [4, 2], "height": 9.6,
            "top_studs": False, "socket": True, "female_clearance": clearance,
            "stl": f"parts/{key}.stl", "orientation": "socket_down",
        }
    return {
        "schema_version": 1, "revision": p["revision"], "units": "mm",
        "parameters_sha256": digest(ROOT / "design/parameters.json"),
        "interface": p["interface"], "message": p["message"], "colors": p["colors"],
        "parts": parts, "models": models,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="design/catalog.json")
    args = parser.parse_args()
    p = load_parameters()
    catalog = build_catalog(p)
    write_json(ROOT / args.output, catalog)
    write_json(ROOT / "design/interface.json", {
        "id": "BRICK-8-MSG-SLOT-1", "revision": p["revision"], "units": "mm",
        "status": p["status"], "brick": p["interface"], "message": p["message"],
        "note": "Design candidates, not a LEGO specification or compatibility certification.",
        "insertion": "Vertical downward; card slides freely into gravity-retained slot.",
    })
    for model in catalog["models"]:
        print(model["id"], model["part_count"], "parts,", len(model["steps"]), "steps")


if __name__ == "__main__":
    main()
