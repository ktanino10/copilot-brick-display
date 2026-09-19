"""Rigid flange capture and coarse printed screws; no adhesive or elastic latch."""
import FreeCAD as App
import math
import Part

V = App.Vector


def coarse_thread(spec, length, radial_clearance=0, axial_clearance=0):
    pitch = spec["pitch"]
    root = spec["root_radius"] + radial_clearance
    crest = spec["crest_radius"] + radial_clearance
    width = spec["root_width"] + 2*axial_clearance
    flat = spec["crest_width"] + 2*axial_clearance
    middle = (root + crest)/2
    sweep_height = (math.ceil(length/pitch)+2)*pitch
    helix = Part.makeHelix(pitch, sweep_height, middle)
    helix.translate(V(0, 0, -pitch))
    points = [V(root-.2, 0, -pitch-width/2), V(crest, 0, -pitch-flat/2),
              V(crest, 0, -pitch+flat/2), V(root-.2, 0, -pitch+width/2)]
    profile = Part.makePolygon(points + [points[0]])
    ridge = Part.Wire(helix.Edges).makePipeShell([profile], True, True)
    shaft = Part.makeCylinder(root, sweep_height+2*pitch, V(0,0,-2*pitch))
    envelope = Part.makeCylinder(crest + .1, length)
    result = shaft.fuse(ridge).common(envelope).removeSplitter()
    expected_ridge = math.pi*(root+crest)*length/pitch*(width+flat)/2*(crest-root)
    if (not result.isValid() or len(result.Solids) != 1 or
            result.Volume - math.pi*root*root*length < .5*expected_ridge):
        raise ValueError("Coarse printed thread did not produce one valid solid")
    return result


def screw(spec):
    body = coarse_thread(spec, spec["stem_length"])
    body.translate(V(0, 0, spec["head_height"]))
    points = [V(spec["head_radius"]*math.cos(i*math.pi/3),
                spec["head_radius"]*math.sin(i*math.pi/3), 0) for i in range(6)]
    head = Part.Face(Part.makePolygon(points+[points[0]])).extrude(V(0,0,spec["head_height"]))
    return head.fuse(body).removeSplitter()


def threaded_coupon(spec, radial_clearance):
    block = Part.makeBox(24, 24, spec["engagement"], V(-12, -12, 0))
    hole = coarse_thread(spec, spec["engagement"], radial_clearance, spec["axial_clearance"])
    return block.cut(hole).removeSplitter()


def insert_body(nx, ny, rise, spec):
    pitch = spec["pitch"]
    width = nx*pitch-spec["visible_gap"]
    height = ny*pitch-spec["visible_gap"]
    flange_w = nx*pitch-spec["flange_gap"]
    flange_h = ny*pitch-spec["flange_gap"]
    flange = Part.makeBox(flange_w, flange_h, spec["flange_thickness"],
                          V(-flange_w/2, -flange_h/2, 0))
    face = Part.makeBox(width, height, spec["frame_thickness"]+rise,
                        V(-width/2, -height/2, 0))
    return flange.fuse(face).removeSplitter()


def insert_cutter(nx, ny, spec):
    pitch = spec["pitch"]
    window_w = nx*pitch-spec["visible_gap"]+2*spec["lateral_clearance"]
    window_h = ny*pitch-spec["visible_gap"]+2*spec["lateral_clearance"]
    pocket_w = nx*pitch-spec["flange_gap"]+2*spec["lateral_clearance"]
    pocket_h = ny*pitch-spec["flange_gap"]+2*spec["lateral_clearance"]
    window = Part.makeBox(window_w, window_h, spec["frame_thickness"]+.2,
                          V(-window_w/2, -window_h/2, -.1))
    pocket = Part.makeBox(pocket_w, pocket_h, spec["flange_thickness"]+spec["axial_clearance"]+.1,
                          V(-pocket_w/2, -pocket_h/2, -.1))
    return window.fuse(pocket)
