"""Gravity-retained plaque support, independent of the shared commercial-stud interface."""
import FreeCAD as App
import Part

from relief_geometry import prism


def stand_body(data):
    p = data["stand"]
    x, y = p["width"] / 2, p["depth"] / 2
    corner = data["nominal_pitch"]
    base = prism([(-x, -y + corner), (-x + corner, -y), (x - corner, -y),
                  (x, -y + corner), (x, y - corner), (x - corner, y),
                  (-x + corner, y), (-x, y - corner)], p["height"])
    cradle = Part.makeBox(p["cradle_width"], p["cradle_depth"], p["cradle_height"],
                          App.Vector(-p["cradle_width"] / 2, p["cradle_y_min"], p["height"]))
    slot = Part.makeBox(p["slot_width"], p["slot_depth"], p["cradle_height"] + .1,
                        App.Vector(-p["slot_width"] / 2, p["slot_y_min"], p["height"]))
    base = base.fuse(cradle.cut(slot))
    for x_origin in [-40, 33.6]:
        y_start = p["cradle_y_min"] + p["cradle_depth"]
        vertices = [App.Vector(x_origin, y_start, p["height"]),
                    App.Vector(x_origin, p["rear_brace_end_y"], p["height"]),
                    App.Vector(x_origin, y_start, p["height"] + p["cradle_height"])]
        wire = Part.makePolygon(vertices + [vertices[0]])
        brace = Part.Face(wire).extrude(App.Vector(p["brace_thickness"], 0, 0))
        base = base.fuse(brace)
    return base.removeSplitter()


def custom_coupons(data):
    p = data["custom_coupons"]
    block = Part.makeBox(64, 24, p["slot_floor"] + p["slot_depth"])
    for index, gap in enumerate(p["slot_gaps_total"]):
        depth = p["tongue_thickness"] + gap
        cutter = Part.makeBox(p["slot_width"], depth, p["slot_depth"] + .1,
                              App.Vector(8 + index * 16 - p["slot_width"] / 2,
                                         12 - depth / 2, p["slot_floor"]))
        block = block.cut(cutter)
    tongue = prism([(0, 0), (10, 0), (10, 16), (12, 16), (12, 24),
                    (-2, 24), (-2, 16), (0, 16)], p["tongue_thickness"])
    a = data["alignment"]
    pin_base = Part.makeBox(20, 12, 3.2)
    pin_base = pin_base.fuse(Part.makeBox(a["pin_width"], a["pin_width"], a["pin_height"],
                            App.Vector(10 - a["pin_width"]/2, 6 - a["pin_width"]/2, 3.2)))
    cap = Part.makeBox(20, 12, 2.4)
    cap = cap.cut(Part.makeBox(a["socket_width"], a["socket_width"], a["socket_depth"] + .01,
                   App.Vector(10 - a["socket_width"]/2, 6 - a["socket_width"]/2, -.01)))
    return {"T90": block.removeSplitter(), "T91": tongue,
            "T92": pin_base.removeSplitter(), "T93": cap.removeSplitter()}
