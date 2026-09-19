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
    print("T2_NATIVE_RETENTION_BEGIN", flush=True)
    catalog = json.loads((ROOT / "catalog.json").read_text())
    params = json.loads((ROOT / "parameters.json").read_text())
    text = check_text(catalog)
    doc = App.openDocument(str(ROOT / "native/character-tribute.FCStd"))
    shapes = {obj.InstanceID: obj.Shape for obj in doc.Objects if hasattr(obj, "InstanceID")}
    pairs = 0
    ids = list(shapes)
    for index, name in enumerate(ids):
        for other in ids[index + 1:]:
            volume = intersection_volume(shapes[name], shapes[other])
            if volume > TOLERANCE:
                raise ValueError(f"Assembly interference {name}/{other}: {volume} mm3")
            pairs += 1
    print(f"PAIR_INTERFERENCE_PASS {pairs}", flush=True)
    colored = [item for item in catalog["instances"] if "front_stop" in item]
    capture = []
    for item in colored:
        record = {"instance":item["id"],"front_stop":item["front_stop"],"rear_stop":item["rear_stop"]}
        for label, delta, stop in (
            ("front",App.Vector(0,-.65,0),item["front_stop"]),
            ("rear",App.Vector(0,.65,0),item["rear_stop"]),
            ("left",App.Vector(-.65,0,0),item["front_stop"]),
            ("right",App.Vector(.65,0,0),item["front_stop"]),
            ("up",App.Vector(0,0,.65),item["front_stop"]),
            ("down",App.Vector(0,0,-.65),item["front_stop"])):
            moved = shapes[item["id"]].copy()
            moved.translate(delta)
            overlap = intersection_volume(moved,shapes[stop])
            if overlap <= TOLERANCE:
                raise ValueError(f"Color insert lacks positive {label} capture: {item['id']}")
            record[label+"_blocked_volume_mm3"] = overlap
        capture.append(record)
    print(f"POSITIVE_CAPTURE_PASS {len(capture)} inserts",flush=True)
    screw_results = []
    screws = [item for item in catalog["instances"] if item.get("motion")=="helical"]
    for item in screws:
        shape = shapes[item["id"]]
        pulled = shape.copy()
        pulled.translate(App.Vector(0,1.6,0))
        blocked = intersection_volume(pulled,shapes["capture-frame"])
        if blocked < .1:
            raise ValueError(f"Screw axial retention missing: {item['id']}")
        x, y = item["xy"]
        pivot = App.Vector(x,params["board"]["back_y"],params["board"]["bottom_z"]+y)
        for distance in (.4,1.6,3.2,6.4,12.8,18):
            moving = shape.copy()
            moving.rotate(pivot,App.Vector(0,-1,0),-360*distance/item["pitch_mm"])
            moving.translate(App.Vector(0,distance,0))
            for name, fixed in shapes.items():
                if name != item["id"] and intersection_volume(moving,fixed)>TOLERANCE:
                    raise ValueError(f"Helical release collision: {item['id']}/{name}/{distance}")
        access = Part.makeCylinder(9,8,App.Vector(x,29,params["board"]["bottom_z"]+y),App.Vector(0,1,0))
        for name, fixed in shapes.items():
            if name != item["id"] and intersection_volume(access,fixed)>TOLERANCE:
                raise ValueError(f"Rear screw access obstructed: {item['id']}/{name}")
        screw_results.append({"instance":item["id"],"pure_pull_blocked_volume_mm3":blocked,
                              "pitch_mm":item["pitch_mm"],"unscrew_offsets_mm":[.4,1.6,3.2,6.4,12.8,18],
                              "rear_access_envelope_mm":{"diameter":18,"depth":8}})
    remaining = {key:value for key,value in shapes.items() if key not in {i["id"] for i in screws}}
    sequence = [next(i for i in catalog["instances"] if i["id"]=="back-cover")]
    sequence += sorted(colored,key=lambda i:-i["step"])
    release = []
    distances = [.2,1,4,12,24]
    for item in sequence:
        shape = remaining.pop(item["id"])
        if "tool_target_xy" in item:
            x, y = item["tool_target_xy"]
            tip = Part.makeBox(1.6,2.4,2,App.Vector(-.8,-1.2,item["front_z"]-.1))
            tip.rotate(App.Vector(),App.Vector(0,0,1),item["tool_tip_rotation_deg"])
            tip.translate(App.Vector(x,y,0))
            tip.rotate(App.Vector(),App.Vector(1,0,0),90)
            tip.translate(App.Vector(0,params["board"]["back_y"],params["board"]["bottom_z"]))
            if intersection_volume(tip,shape)<=TOLERANCE:
                raise ValueError(f"Printed-tool target misses the part: {item['id']}")
            for name, fixed in remaining.items():
                if intersection_volume(tip,fixed)>TOLERANCE:
                    raise ValueError(f"Tool target blocked: {item['id']}/{name}")
        for distance in distances:
            moved = shape.copy()
            moved.translate(App.Vector(0,distance,0))
            for name, fixed in remaining.items():
                if intersection_volume(moved,fixed)>TOLERANCE:
                    raise ValueError(f"Rear removal blocked: {item['id']}/{name}/{distance}")
        release.append({"instance":item["id"],"direction_world":"+Y rearward","offsets_mm":distances,
                        "front_tool_target_xy":item.get("tool_target_xy"),
                        "tool_tip_rotation_deg":item.get("tool_tip_rotation_deg")})
    plaque_ids = [name for name in shapes if name not in ("stand","message-dock","message-card")]
    plaque = Part.makeCompound([shapes[name] for name in plaque_ids])
    for distance in (.2,1,8,32.2,40,160):
        raised = plaque.copy()
        raised.translate(App.Vector(0, 0, distance))
        for name in ("stand", "message-dock", "message-card"):
            if intersection_volume(raised, shapes[name]) > TOLERANCE:
                raise ValueError(f"Finished plaque cannot be lifted past {name}")
    card_path = []
    for distance in (.2,1,4.8,8,40,100):
        card = shapes["message-card"].copy()
        card.translate(App.Vector(0,0,distance))
        for name, fixed in shapes.items():
            if name!="message-card" and intersection_volume(card,fixed)>TOLERANCE:
                raise ValueError(f"Message card removal blocked: {name}/{distance}")
        card_path.append(distance)
    print("ALL_REMOVAL_AND_TOOL_PATHS_PASS", flush=True)
    stand_spec, board_spec = params["stand"], params["board"]
    message = catalog["shared_interface"]["message"]
    brick = catalog["shared_interface"]["brick"]
    board_thickness = params["retention"]["frame_thickness"]
    slot_floor = stand_spec["dock_origin"][2] + message["dock_height"] - message["slot_depth"]
    diameter = brick["reference_stud_diameter"] + brick["stud_diameter_correction"]
    pitch = brick["pitch"]
    stand_section = measured_floor(shapes["stand"], stand_spec["height"],
                                   [stand_spec["slot_width"], stand_spec["slot_depth"]])
    tongue_section = measured_floor(shapes["capture-frame"], board_spec["bottom_z"]-board_spec["tongue_length"],
                                    [board_spec["tongue_width"], board_thickness])
    dock_section = measured_floor(shapes["message-dock"], slot_floor,
                                  [message["slot_length"], message["slot_width"]])
    card_section = measured_floor(shapes["message-card"], slot_floor,
                                  [message["card_width"], message["card_thickness"]])
    cylinders = [face for face in shapes["stand"].Faces
                 if isinstance(face.Surface, Part.Cylinder) and
                 abs(face.BoundBox.ZMin - stand_spec["dock_origin"][2]) < 1e-5 and
                 abs(face.Surface.Radius - diameter/2) < 1e-5]
    if len(cylinders) != 24:
        raise ValueError("Shared stand mating patch does not contain 24 measured diameter-4.8 studs")
    xs = sorted({round(face.BoundBox.Center.x, 5) for face in cylinders})
    ys = sorted({round(face.BoundBox.Center.y, 5) for face in cylinders})
    if (len(xs) != 12 or len(ys) != 2 or
            any(abs(b-a-pitch) > 1e-5 for values in (xs, ys) for a, b in zip(values, values[1:]))):
        raise ValueError("Measured shared stand stud pitch differs from 8mm")
    volume = sum(shape.Volume for shape in shapes.values())
    center = sum((shape.CenterOfMass * shape.Volume for shape in shapes.values()), App.Vector()) / volume
    # The full support polygon includes clipped corners, rather than a generous rectangle.
    x, y, corner = stand_spec["width"]/2, stand_spec["depth"]/2, params["nominal_pitch"]
    polygon = [(-x,-y+corner),(-x+corner,-y),(x-corner,-y),(x,-y+corner),
               (x,y-corner),(x-corner,y),(-x+corner,y),(-x,y-corner)]
    margins = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        margins.append(((b[0]-a[0])*(center.y-a[1])-(b[1]-a[1])*(center.x-a[0])) /
                       math.hypot(b[0]-a[0], b[1]-a[1]))
    if min(margins) <= 0:
        raise ValueError("Uniform-solid center of mass is outside the support polygon")
    print("ASSEMBLY_FIT_FACES_PASS", flush=True)
    report = {
        "status": "pass", "revision":"T2","adhesive_required":False,"all_parts_removable":True,
        "brep_pair_checks": pairs, "maximum_allowed_intersection_mm3": TOLERANCE,
        "positive_capture": capture, "coarse_screw_retention_and_release":screw_results,
        "reverse_order_removal_and_tool_access":release,
        "message_card_upward_removal_offsets_mm":card_path,
        "insertion_path": {"sampled_offsets_mm": distances,"reverse_paths_provide_assembly":True,
                           "finished_plaque_upward_removal_also_checked": True,
                           "scope": "Rigid BRep samples, positive shoulders and helical paths; not printed wear, force, hand ergonomics or elastic-clutch certification."},
        "measured_fit_faces_mm": {"stand_socket": stand_section, "board_tongue": tongue_section,
                                  "message_slot": dock_section, "message_card": card_section,
                                  "shared_stud_diameter": diameter, "shared_pitch": pitch, "shared_stud_count": 24},
        "geometric_stability": {"uniform_solid_com_mm": list(center),
                                 "nearest_support_edge_margin_mm": min(margins),
                                 "solid_proxy_tip_angle_deg": math.degrees(math.atan(min(margins)/center.z)),
                                 "scope": "Uniform-density full-solid CAD proxy only. Slicer infill, PLA creep, impacts and real tipping strength are not certified."},
        "feature_gauges_mm": {"flange_thickness":1.6,"nominal_shoulder_overlap_per_side":.8,
                              "minimum_overlap_after_lateral_play":.6,"minimum_grid_web":2,
                              "pupil_width":3.2,"tool_tip":[1.6,2.4],"thread_root_diameter":8.8,
                              "thread_major_diameter":11.2,"thread_pitch":3.2,"nominal_thread_engagement":9.6},
        "text": text, "physical_fit_tested": False, "safety_certified": False
    }
    (ROOT / "validation/assembly.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    App.closeDocument(doc.Name)
    print(f"ASSEMBLY_AUDIT_PASS {pairs} pairs; minimum glyph island {text['minimum_separate_glyph_island_bbox_mm']:.3f}mm")


if __name__ == "__main__":
    main()
