"""Original relief profiles; commercial-stud geometry belongs to the shared generator."""
import FreeCAD as App
import Part


def prism(points, height, z=0):
    vertices = [App.Vector(x, y, z) for x, y in points]
    wire = Part.makePolygon(vertices + [vertices[0]])
    return Part.Face(wire).extrude(App.Vector(0, 0, height))


def profile(part):
    if "profile" in part:
        return prism(part["profile"], part["thickness"])
    rx, ry = [value / 2 for value in part["ellipse"]]
    curve = Part.Ellipse(App.Vector(), max(rx, ry), min(rx, ry)).toShape()
    if ry > rx:
        curve.rotate(App.Vector(), App.Vector(0, 0, 1), 90)
    return Part.Face(Part.Wire([curve])).extrude(App.Vector(0, 0, part["thickness"]))


def expanded_profile(part, clearance, height):
    vertices = [App.Vector(x, y, 0) for x, y in part["profile"]]
    wire = Part.makePolygon(vertices + [vertices[0]])
    expanded = wire.makeOffset2D(clearance, join=2)
    return Part.Face(expanded).extrude(App.Vector(0, 0, height))


def relief_shapes(data):
    parts = {part["id"]: part for part in data["parts"]}
    instances = {item["id"]: item for item in data["instances"]}
    alignment = data["alignment"]
    patterns = {}
    for parent in instances.values():
        pins = []
        for child in instances.values():
            if child["parent"] != parent["id"]:
                continue
            for x, y in parts[child["part"]].get("locators", []):
                pins.append((x + child["xy"][0] - parent["xy"][0],
                             y + child["xy"][1] - parent["xy"][1]))
        pattern = sorted(pins)
        previous = patterns.setdefault(parent["part"], pattern)
        if previous != pattern:
            raise ValueError(f"Nonidentical instances of {parent['part']}")
    shapes = {}
    for part in parts.values():
        shape = profile(part)
        if "subtract_profile" in part:
            cut = expanded_profile(parts[part["subtract_profile"]],
                                   part["subtract_clearance"], part["thickness"])
            shape = shape.cut(cut)
        for extra in part.get("extras", []):
            x, y, width, length = extra["rect"]
            block = Part.makeBox(width, length, extra["height"],
                                 App.Vector(x, y, extra.get("z", 0)))
            shape = shape.fuse(block)
        width = alignment["pin_width"]
        for x, y in patterns[part["id"]]:
            pin = Part.makeBox(width, width, alignment["pin_height"],
                               App.Vector(x - width / 2, y - width / 2, part["thickness"]))
            shape = shape.fuse(pin)
        width = alignment["socket_width"]
        for x, y in part.get("locators", []):
            socket = Part.makeBox(width, width, alignment["socket_depth"] + 0.01,
                                  App.Vector(x - width / 2, y - width / 2, -0.01))
            shape = shape.cut(socket)
        shape = shape.removeSplitter()
        if not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
            raise ValueError(f"{part['id']} is not one valid positive-volume solid")
        shapes[part["id"]] = shape
    return shapes


def relief_depths(data):
    parts = {part["id"]: part for part in data["parts"]}
    instances = {item["id"]: item for item in data["instances"]}
    depths = {}
    for item in data["instances"]:
        parent = instances.get(item["parent"])
        depths[item["id"]] = (depths[parent["id"]] + parts[parent["part"]]["thickness"]
                              if parent else 0)
    return depths
