"""Deterministic 8 mm artwork partition; X cells belong to removable eye/badge cassettes."""
COLOR_KEYS = {"K": "charcoal", "W": "white", "S": "skin", "R": "red",
              "B": "blue", "G": "green", "L": "mint"}


def layout(data):
    spec = data["mosaic"]
    grid = [list(row) for row in reversed(spec["rows_top_first"])]
    if len(grid) != 20 or any(len(row) != 18 for row in grid):
        raise ValueError("The T2 artwork must remain an 18 by 20 nominal-8mm grid")
    if set("".join("".join(row) for row in grid)) - set(".X" + "".join(COLOR_KEYS)):
        raise ValueError("Unknown artwork color code")
    pieces = []
    for y in range(20):
        for x in range(18):
            code = grid[y][x]
            if code in ".X":
                continue
            candidates = []
            for height in range(1, min(spec["max_rows"], 20-y)+1):
                for width in range(1, min(spec["max_columns"], 18-x)+1):
                    if code == "L" and (width != 1 or height != 1):
                        continue
                    if all(grid[yy][xx] == code for yy in range(y, y+height)
                           for xx in range(x, x+width)):
                        candidates.append((width*height, width, height))
            _, width, height = max(candidates)
            for yy in range(y, y+height):
                for xx in range(x, x+width):
                    grid[yy][xx] = "."
            color = COLOR_KEYS[code]
            pieces.append({"id": f"tile-{len(pieces)+1:03d}", "part": f"IN-{code}-{width}x{height}",
                           "color": color, "cells": [width, height],
                           "xy": [-72+8*(x+width/2), 8*(y+height/2)],
                           "rise": spec["rise_by_color"][color],
                           "kind": "circle" if code == "L" else "rectangle"})
    remaining = {(x, y) for y, row in enumerate(grid) for x, cell in enumerate(row) if cell == "X"}
    reserved = set()
    for special in spec["specials"]:
        cx, cy = special["xy"]
        nx, ny = special["cells"]
        reserved.update((x, y) for y in range(20) for x in range(18)
                        if abs(-68+8*x-cx) < nx*4 and abs(4+8*y-cy) < ny*4)
    if remaining != reserved:
        raise ValueError("Artwork X cells differ from the eye/badge cassette footprints")
    return pieces
