"""T2 positive-capture frame, removable color inserts, back cover and printed fasteners."""
import FreeCAD as App
import Part

from mosaic_layout import layout
from relief_geometry import prism, expanded_profile
from retention_geometry import coarse_thread, insert_body, insert_cutter, screw, threaded_coupon

V = App.Vector


def box(width, height, z, thickness):
    return Part.makeBox(width, height, thickness, V(-width/2, -height/2, z))


def ellipse(width, height, z, thickness):
    curve = Part.Ellipse(V(), max(width, height)/2, min(width, height)/2).toShape()
    if height > width:
        curve.rotate(V(), V(0, 0, 1), 90)
    face = Part.Face(Part.Wire([curve]))
    face.translate(V(0, 0, z))
    return face.extrude(V(0, 0, thickness))


def moved(shape, x, y, z=0):
    result = shape.copy()
    result.translate(V(x, y, z))
    return result


def eye_shapes(retention):
    e = retention["eye"]
    t, c = retention["flange_thickness"], retention["lateral_clearance"]
    white = box(*e["white_flange"], 0, t).fuse(ellipse(*e["white_face"], 0, e["white_front_z"]))
    white = white.cut(ellipse(e["iris_face"][0]+2*c, e["iris_face"][1]+2*c, -.1, e["white_front_z"]+.2))
    blue = box(*e["iris_flange"], e["iris_back_z"], t).fuse(
        ellipse(*e["iris_face"], e["iris_back_z"], e["iris_front_z"]-e["iris_back_z"]))
    blue = blue.cut(box(e["pupil_face"][0]+2*c, e["pupil_face"][1]+2*c,
                        e["iris_back_z"]-.1, e["iris_front_z"]-e["iris_back_z"]+.2))
    black = box(*e["pupil_flange"], e["pupil_back_z"], t).fuse(
        box(*e["pupil_face"], e["pupil_back_z"], e["pupil_front_z"]-e["pupil_back_z"]))
    return [shape.removeSplitter() for shape in (white, blue, black)]


def badge_shapes(retention):
    b = retention["badge"]
    t, c = retention["flange_thickness"], retention["lateral_clearance"]
    white = box(*b["flange"], 0, t).fuse(ellipse(b["diameter"], b["diameter"], 0, b["white_front_z"]))
    opening = expanded_profile({"profile": b["m_profile"]}, c, b["white_front_z"]+.2)
    opening.translate(V(0, 0, -.1))
    white = white.cut(opening)
    letter = box(*b["m_flange"], b["m_back_z"], t).fuse(
        prism(b["m_profile"], b["m_front_z"]-b["m_back_z"], b["m_back_z"]))
    return white.removeSplitter(), letter.removeSplitter()


def special_window(special, retention):
    c, h, t = retention["lateral_clearance"], retention["frame_thickness"], retention["flange_thickness"]
    if special["kind"] == "eye":
        dimensions, flange = retention["eye"]["white_face"], retention["eye"]["white_flange"]
    else:
        dimensions = [retention["badge"]["diameter"]]*2
        flange = retention["badge"]["flange"]
    window = ellipse(dimensions[0]+2*c, dimensions[1]+2*c, -.1, h+.2)
    pocket = box(flange[0]+2*c, flange[1]+2*c, -.1, t+retention["axial_clearance"]+.1)
    return window.fuse(pocket)


def build_capture(data):
    r, thread = data["retention"], data["screw"]
    pieces = layout(data)
    outline = [[-40,-32],[40,-32],[40,0],[72,0],[80,8],[80,152],[72,160],
               [-72,160],[-80,152],[-80,8],[-72,0],[-40,0]]
    frame = prism(outline, r["frame_thickness"])
    bosses = [Part.makeCylinder(r["boss_radius"], r["frame_thickness"]-r["boss_back_z"],
                                 V(x, y, r["boss_back_z"])) for x, y in r["screw_centers"]]
    frame = frame.multiFuse(bosses)
    female = coarse_thread(thread, thread["female_depth"], thread["radial_clearance"], thread["axial_clearance"])
    cuts = [moved(female, x, y, r["boss_back_z"]) for x, y in r["screw_centers"]]
    shapes, specs, instances = {}, {}, []
    for piece in pieces:
        nx, ny = piece["cells"]
        shape = insert_body(nx, ny, piece["rise"], r)
        cutter = insert_cutter(nx, ny, r)
        if piece["kind"] == "circle":
            shape = box(8-r["flange_gap"], 8-r["flange_gap"], 0, r["flange_thickness"]).fuse(
                ellipse(8-r["visible_gap"], 8-r["visible_gap"], 0, r["frame_thickness"]+piece["rise"]))
            cutter = ellipse(8-r["visible_gap"]+2*r["lateral_clearance"],
                              8-r["visible_gap"]+2*r["lateral_clearance"], -.1, r["frame_thickness"]+.2).fuse(
                box(8-r["flange_gap"]+2*r["lateral_clearance"],
                    8-r["flange_gap"]+2*r["lateral_clearance"], -.1,
                    r["flange_thickness"]+r["axial_clearance"]+.1))
        shapes[piece["part"]] = shape.removeSplitter()
        specs[piece["part"]] = {
            "name_ja": f'{nx}×{ny} フランジ付き色インサート', "color": piece["color"], "category": "assembly",
            "source": "parameters.json#mosaic", "retention": "front_shoulder_and_back_cover",
            "cells": piece["cells"], "flange_mm": [nx*8-r["flange_gap"], ny*8-r["flange_gap"]],
            "window_mm": [nx*8-r["visible_gap"]+2*r["lateral_clearance"],
                          ny*8-r["visible_gap"]+2*r["lateral_clearance"]]}
        cuts.append(moved(cutter, *piece["xy"]))
        instances.append({**piece, "parent": "capture-frame", "step": 2, "depth": 0,
                          "front_stop": "capture-frame", "rear_stop": "back-cover",
                          "front_stop_offset_mm": .2, "rear_stop_offset_mm": .2,
                          "front_z": r["frame_thickness"]+piece["rise"],
                          "tool_target_xy": piece["xy"], "tool_tip_rotation_deg": 0})
    detail_shapes = eye_shapes(r) + list(badge_shapes(r))
    detail_ids = ["EYE-W", "EYE-B", "EYE-K", "BADGE-W", "BADGE-M"]
    detail_names = ["目の白い捕捉カセット", "青い虹彩と背面フランジ", "瞳と背面フランジ",
                    "白い丸の捕捉カセット", "Mと背面フランジ"]
    for pid, shape, name, color in zip(detail_ids, detail_shapes, detail_names, ("white","blue","charcoal","white","red")):
        shapes[pid] = shape
        specs[pid] = {"name_ja": name, "color": color, "category": "assembly",
                      "source": "parameters.json#retention", "retention": "nested_flange_capture"}
    cover_outline = [[-76,0],[76,0],[76,152],[68,160],[-68,160],[-76,152]]
    cover = prism(cover_outline, r["back_cover_base_thickness"], r["back_cover_back_z"])
    cover = cover.fuse(Part.makeBox(144, 160, r["back_cover_land_z"]+8, V(-72, 0, -8)))
    for special in data["mosaic"]["specials"]:
        x, y = special["xy"]
        cuts.append(moved(special_window(special, r), x, y))
        if special["kind"] == "eye":
            ids, stages = ["EYE-W", "EYE-B", "EYE-K"], [3,4,5]
            names = [special["id"]+"-white", special["id"]+"-iris", special["id"]+"-pupil"]
            for key in ("iris", "pupil"):
                e = r["eye"]
                z = e[key+"_back_z"]-r["axial_clearance"]
                w, h = e[key+"_flange"]
                cover = cover.cut(moved(box(w+2*r["lateral_clearance"], h+2*r["lateral_clearance"],
                                           z, r["back_cover_land_z"]-z+.1), x, y))
        else:
            ids, stages = ["BADGE-W", "BADGE-M"], [3,4]
            names = ["badge-white", "badge-m"]
            b = r["badge"]
            z = b["m_back_z"]-r["axial_clearance"]
            w, h = b["m_flange"]
            cover = cover.cut(moved(box(w+2*r["lateral_clearance"], h+2*r["lateral_clearance"],
                                       z, r["back_cover_land_z"]-z+.1), x, y))
        for i, (pid, stage, name) in enumerate(zip(ids, stages, names)):
            tool_offsets = {"EYE-W":(-5.3,0,0), "EYE-B":(0,-5,90), "EYE-K":(0,0,0),
                            "BADGE-W":(0,-5.4,90), "BADGE-M":(-3,0,0)}
            tx, ty, angle = tool_offsets[pid]
            fronts = {"EYE-W":r["eye"]["white_front_z"],"EYE-B":r["eye"]["iris_front_z"],
                      "EYE-K":r["eye"]["pupil_front_z"],"BADGE-W":r["badge"]["white_front_z"],
                      "BADGE-M":r["badge"]["m_front_z"]}
            instances.append({"id": name, "part": pid, "xy": [x,y], "depth": 0, "step": stage,
                              "parent": names[i-1] if i else "capture-frame",
                              "front_stop": names[i-1] if i else "capture-frame", "rear_stop": "back-cover",
                              "front_stop_offset_mm": .4 if i else .2, "rear_stop_offset_mm": .2,
                              "front_z":fronts[pid], "tool_target_xy":[x+tx,y+ty],
                              "tool_tip_rotation_deg":angle})
    for x, y in r["screw_centers"]:
        cover = cover.cut(Part.makeCylinder(r["boss_radius"]+.3, 8.2, V(x,y,-8)))
        cover = cover.cut(Part.makeCylinder(thread["crest_radius"]+.4, 3.4, V(x,y,r["back_cover_back_z"]-.1)))
    frame = frame.cut(Part.makeCompound(cuts)).removeSplitter()
    structural = {"T02": frame, "T03": cover.removeSplitter(), "T04": screw(thread)}
    names = {"T02":"フランジ捕捉前枠と差込舌", "T03":"全小部品を支持する着脱裏蓋", "T04":"交換可能な印刷粗ねじ"}
    for pid, shape in structural.items():
        shapes[pid] = shape
        specs[pid] = {"name_ja": names[pid], "color": "white" if pid=="T02" else "charcoal",
                      "category":"assembly","source":"parameters.json#retention"}
    instances.insert(0, {"id":"capture-frame","part":"T02","parent":"stand","xy":[0,0],"depth":0,"step":1})
    instances.append({"id":"back-cover","part":"T03","parent":"capture-frame","xy":[0,0],"depth":0,"step":6})
    for index, (x, y) in enumerate(r["screw_centers"]):
        instances.append({"id":f"screw-{index+1}","part":"T04","parent":"capture-frame","xy":[x,y],
                          "depth":r["back_cover_back_z"]-thread["head_height"],"step":7,
                          "motion":"helical","pitch_mm":thread["pitch"]})
    for clearance in thread["coupon_radial_clearances"]:
        pid = f"THREAD-C{round(clearance*100):02d}"
        shapes[pid] = threaded_coupon(thread, clearance)
        specs[pid] = {"name_ja":f"粗ねじ雌側クリアランス {clearance:.2f} 試験片", "color":"charcoal",
                      "category":"coupon","source":"parameters.json#screw",
                      "radial_clearance_mm":clearance}
    coupon_frame = Part.makeBox(48,24,r["frame_thickness"],V(-24,-12,0)).fuse(
        Part.makeCylinder(r["boss_radius"], r["frame_thickness"]-r["boss_back_z"],
                           V(12,0,r["boss_back_z"])))
    coupon_frame = coupon_frame.cut(moved(insert_cutter(1,1,r),-12,0))
    coupon_frame = coupon_frame.cut(moved(female,12,0,r["boss_back_z"])).removeSplitter()
    coupon_cover = Part.makeBox(48,24,r["back_cover_base_thickness"],V(-24,-12,r["back_cover_back_z"]))
    coupon_cover = coupon_cover.fuse(Part.makeBox(16,16,7.8,V(-20,-8,-8)))
    coupon_cover = coupon_cover.cut(Part.makeCylinder(thread["crest_radius"]+.4,3.4,V(12,0,-11.3)))
    shapes["CAPTURE-FRAME"], shapes["CAPTURE-COVER"] = coupon_frame, coupon_cover.removeSplitter()
    shapes["EJECTOR"] = prism([[-4,0],[4,0],[4,26],[.8,30],[.8,36],[-.8,36],[-.8,30],[-4,26]],2.4)
    shapes["ASSEMBLY-REST"] = Part.makeBox(16,112,2.4,V(-8,-56,0)).fuse(
        Part.makeBox(8,112,9.6,V(-4,-56,2.4))).removeSplitter()
    for pid, name in [("CAPTURE-FRAME","一枠のフランジ捕捉・ねじ試験台"),
                      ("CAPTURE-COVER","捕捉試験台の着脱裏蓋"),("EJECTOR","短い剛性先端の取り出し押し棒"),
                      ("ASSEMBLY-REST","前面を保護する組立用支持台")]:
        specs[pid] = {"name_ja":name,"color":"charcoal","category":"tool" if pid in ("EJECTOR","ASSEMBLY-REST") else "coupon",
                      "tool_quantity":2 if pid=="ASSEMBLY-REST" else 1,
                      "source":"parameters.json#retention"}
    for pid, shape in shapes.items():
        if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
            raise ValueError(f"T2 capture part is not one valid positive-volume solid: {pid}")
    return specs, shapes, instances
