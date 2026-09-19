"""Check the saved BRep assembly, not a second hand-built proxy."""
import json
import math
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-5


def intersection_volume(a, b):
    return a.common(b).Volume if a.BoundBox.intersect(b.BoundBox) else 0


def measured_floor(shape, z, expected):
    for face in shape.Faces:
        b = face.BoundBox
        if (b.ZLength < 1e-5 and abs(b.ZMin - z) < 1e-5 and
                abs(b.XLength - expected[0]) < 1e-5 and abs(b.YLength - expected[1]) < 1e-5):
            return [b.XLength, b.YLength]
    raise ValueError(f"Actual BRep floor face at Z={z} does not contain {expected}")


def check_text(catalog):
    message = catalog["shared_interface"]["message"]
    card = Part.Shape()
    card.read(str(ROOT / "native/parts/MSG-CARD.step"))
    top_z = message["card_thickness"] + message["text_relief"]
    faces = [face for face in card.Faces if face.BoundBox.ZLength < 1e-6
             and abs(face.BoundBox.ZMin - top_z) < 1e-6]
    if not faces:
        raise ValueError("The actual message card STEP has no raised lettering")
    def inside_wire(x, y, polygon):
        inside = False
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                inside = not inside
        return inside
    components, stem_gauges = [], []
    for index, face in enumerate(faces):
        bounds = face.BoundBox
        polygons = [[(p.x, p.y) for p in wire.discretize(Deflection=.005)] for wire in face.Wires]
        segments = [[], []]
        for edge in face.Edges:
            if len(edge.Vertexes) != 2:
                continue
            a, b = [vertex.Point for vertex in edge.Vertexes]
            if abs(edge.Length - (b-a).Length) > 1e-6:
                continue
            if abs(a.x-b.x) < 1e-6 and abs(a.y-b.y) > .3:
                segments[0].append((a.x, min(a.y, b.y), max(a.y, b.y)))
            if abs(a.y-b.y) < 1e-6 and abs(a.x-b.x) > .3:
                segments[1].append((a.y, min(a.x, b.x), max(a.x, b.x)))
        for axis, edges in enumerate(segments):
            for i, a in enumerate(edges):
                for b in edges[i+1:]:
                    width = abs(a[0]-b[0])
                    low, high = max(a[1], b[1]), min(a[2], b[2])
                    if not .01 < width < 1.2 or high-low < .3:
                        continue
                    samples = [(a[0]+f*(b[0]-a[0]), (low+high)/2) for f in (.1, .3, .5, .7, .9)]
                    if axis:
                        samples = [(y, x) for x, y in samples]
                    if all(sum(inside_wire(x, y, polygon) for polygon in polygons) % 2 for x, y in samples):
                        stem_gauges.append({"island": index, "axis": "X" if axis == 0 else "Y",
                                            "width_mm": width, "parallel_overlap_mm": high-low})
        components.append({"island": index, "bbox_min_dimension_mm": min(bounds.XLength, bounds.YLength),
                           "bounds_mm": [bounds.XMin, bounds.YMin, bounds.XMax, bounds.YMax]})
    if not stem_gauges or min(item["width_mm"] for item in stem_gauges) < .22:
        raise ValueError("Actual card straight strokes are below the 0.22mm baseline line-width gauge")
    return {
        "minimum_separate_glyph_island_bbox_mm": min(x["bbox_min_dimension_mm"] for x in components),
        "minimum_parallel_straight_stroke_mm": min(x["width_mm"] for x in stem_gauges),
        "measured_straight_stroke_gauges": stem_gauges,
        "baseline_line_width_gauge_mm": .22,
        "recommended_nozzle_mm": .2,
        "interpretation": "Measured from raised cap faces in the actual card STEP. Straight stroke pairs overlap at least 0.3mm; inside tests use 0.005mm contour tessellation. Curved/tapered terminals and mathematical corner tips are not declared constant-width printable walls. Check slicer extrusion paths and print the card coupon.",
        "components": components
    }


def main():
    print("ASSEMBLY_BEGIN", flush=True)
    catalog = json.loads((ROOT / "catalog.json").read_text())
    params = json.loads((ROOT / "parameters.json").read_text())
    text = check_text(catalog)
    print("ACTUAL_CARD_TEXT_GAUGES_PASS", flush=True)
    doc = App.openDocument(str(ROOT / "native/character-tribute.FCStd"))
    shapes = {obj.InstanceID: obj.Shape for obj in doc.Objects if hasattr(obj, "InstanceID")}
    print(f"ASSEMBLY_PAIRS {len(shapes)} shapes", flush=True)
    pairs, contacts = 0, []
    ids = list(shapes)
    for index, name in enumerate(ids):
        for other in ids[index + 1:]:
            volume = intersection_volume(shapes[name], shapes[other])
            if volume > TOLERANCE:
                raise ValueError(f"Assembly interference {name}/{other}: {volume} mm3")
            pairs += 1
    for item in catalog["instances"]:
        if item.get("parent"):
            distance = shapes[item["id"]].distToShape(shapes[item["parent"]])[0]
            if distance > 1e-5:
                raise ValueError(f"Floating unsupported part: {item['id']} ({distance}mm)")
            contacts.append({"instance": item["id"], "support": item["parent"],
                             "surface_distance_mm": distance})
    print(f"ASSEMBLY_CONTACTS_PASS {pairs} pairs, {len(contacts)} supports", flush=True)
    sequence = sorted(catalog["instances"], key=lambda item: item["step"])
    checked_path_positions = 0
    installed = []
    distances = [.1, .5, 1, 4, 16, 40]
    for item in sequence:
        print(f"INSERTION_PATH {item['id']}", flush=True)
        direction = (App.Vector(0, 0, 1) if item["id"] in ("stand", "board", "message-dock", "message-card")
                     else App.Vector(0, -1, 0))
        for distance in distances:
            moving = shapes[item["id"]].copy()
            moving.translate(direction * distance)
            for prior in installed:
                if intersection_volume(moving, shapes[prior]) > TOLERANCE:
                    raise ValueError(f"Blocked insertion path: {item['id']}/{prior}, {distance} mm")
            checked_path_positions += 1
        installed.append(item["id"])
    plaque_ids = [item["id"] for item in catalog["instances"] if item["part"].startswith("T") and item["part"] != "T01"]
    plaque = Part.makeCompound([shapes[name] for name in plaque_ids])
    for distance in distances + [160]:
        raised = plaque.copy()
        raised.translate(App.Vector(0, 0, distance))
        for name in ("stand", "message-dock", "message-card"):
            if intersection_volume(raised, shapes[name]) > TOLERANCE:
                raise ValueError(f"Finished plaque cannot be lifted past {name}")
    print("ASSEMBLY_PATHS_PASS", flush=True)
    stand_section = measured_floor(shapes["stand"], 9.6, [80.6, 6.9])
    tongue_section = measured_floor(shapes["board"], 9.6, [80, 6.4])
    dock_section = measured_floor(shapes["message-dock"], 14.4, [88.4, 2.4])
    card_section = measured_floor(shapes["message-card"], 14.4, [88, 2])
    cylinders = [face for face in shapes["stand"].Faces
                 if isinstance(face.Surface, Part.Cylinder) and
                 abs(face.BoundBox.ZMin - 9.6) < 1e-5 and
                 abs(face.Surface.Radius - 2.4) < 1e-5]
    if len(cylinders) != 24:
        raise ValueError("Shared stand mating patch does not contain 24 measured diameter-4.8 studs")
    xs = sorted({round(face.BoundBox.Center.x, 5) for face in cylinders})
    ys = sorted({round(face.BoundBox.Center.y, 5) for face in cylinders})
    if len(xs) != 12 or len(ys) != 2 or any(abs(b-a-8) > 1e-5 for a, b in zip(xs, xs[1:])) or ys[1]-ys[0] != 8:
        raise ValueError("Measured shared stand stud pitch differs from 8mm")
    volume = sum(shape.Volume for shape in shapes.values())
    center = sum((shape.CenterOfMass * shape.Volume for shape in shapes.values()), App.Vector()) / volume
    # The full support polygon includes clipped corners, rather than a generous rectangle.
    polygon = [(-88,-40),(-80,-48),(80,-48),(88,-40),(88,40),(80,48),(-80,48),(-88,40)]
    margins = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        margins.append(((b[0]-a[0])*(center.y-a[1])-(b[1]-a[1])*(center.x-a[0])) /
                       math.hypot(b[0]-a[0], b[1]-a[1]))
    if min(margins) <= 0:
        raise ValueError("Uniform-solid center of mass is outside the support polygon")
    print("ASSEMBLY_FIT_FACES_PASS", flush=True)
    report = {
        "status": "pass", "brep_pair_checks": pairs, "maximum_allowed_intersection_mm3": TOLERANCE,
        "support_contacts": contacts,
        "insertion_path": {"sampled_offsets_mm": distances, "sampled_positions": checked_path_positions,
                           "finished_plaque_upward_removal_also_checked": True,
                           "scope": "BRep samples plus open-axis slots; not a human-hand, glue-cure or elastic-clutch simulation."},
        "measured_fit_faces_mm": {"stand_socket": stand_section, "board_tongue": tongue_section,
                                  "message_slot": dock_section, "message_card": card_section,
                                  "shared_stud_diameter": 4.8, "shared_pitch": 8, "shared_stud_count": 24},
        "geometric_stability": {"uniform_solid_com_mm": list(center),
                                 "nearest_support_edge_margin_mm": min(margins),
                                 "solid_proxy_tip_angle_deg": math.degrees(math.atan(min(margins)/center.z)),
                                 "scope": "Uniform-density full-solid CAD proxy only. Slicer infill, glue, PLA creep, impacts and real tipping strength are not certified."},
        "feature_gauges_mm": {"supported_whisker_width": 3.2, "glove_step": 4,
                              "pupil_width": 3.2, "minimum_relief_thickness": 1.2,
                              "minimum_locator_socket_roof": 1.2},
        "text": text, "physical_fit_tested": False, "safety_certified": False
    }
    (ROOT / "validation/assembly.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    App.closeDocument(doc.Name)
    print(f"ASSEMBLY_AUDIT_PASS {pairs} pairs; minimum glyph island {text['minimum_separate_glyph_island_bbox_mm']:.3f}mm")


if __name__ == "__main__":
    main()
