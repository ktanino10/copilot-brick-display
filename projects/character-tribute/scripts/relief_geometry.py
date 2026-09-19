"""Shared profile primitives for the original, mechanically captured tribute geometry."""
import FreeCAD as App
import Part


def prism(points, height, z=0):
    vertices = [App.Vector(x, y, z) for x, y in points]
    return Part.Face(Part.makePolygon(vertices+[vertices[0]])).extrude(App.Vector(0,0,height))


def expanded_profile(part, clearance, height):
    vertices = [App.Vector(x, y, 0) for x, y in part["profile"]]
    wire = Part.makePolygon(vertices+[vertices[0]])
    return Part.Face(wire.makeOffset2D(clearance, join=2)).extrude(App.Vector(0,0,height))
