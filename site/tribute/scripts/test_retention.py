"""Digital proof of positive capture and deliberate, reversible removal; not a print test."""
import json
from pathlib import Path
import unittest

import FreeCAD as App
import Part

from capture_design import build_capture

ROOT = Path(__file__).resolve().parents[1]


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "parameters.json").read_text())
        cls.specs, cls.shapes, cls.instances = build_capture(cls.data)
        cls.placed = {}
        for item in cls.instances:
            shape = cls.shapes[item["part"]].copy()
            shape.translate(App.Vector(*item["xy"], item["depth"]))
            cls.placed[item["id"]] = shape

    def test_all_solids_and_assembly_interference(self):
        for pid, shape in self.shapes.items():
            self.assertTrue(shape.isValid(), pid)
            self.assertEqual(len(shape.Solids), 1, pid)
            self.assertGreater(shape.Volume, 0, pid)
        objects = list(self.placed.items())
        for index, (name, a) in enumerate(objects):
            for other, b in objects[index+1:]:
                if a.BoundBox.intersect(b.BoundBox):
                    self.assertLess(a.common(b).Volume, 1e-5, f"{name}/{other}")

    def test_every_colored_insert_is_captured_in_both_directions(self):
        for item in self.instances:
            if "front_stop" not in item:
                continue
            shape = self.placed[item["id"]]
            for sign, stop in ((1, item["front_stop"]), (-1, item["rear_stop"])):
                displaced = shape.copy()
                displaced.translate(App.Vector(0, 0, sign*.65))
                self.assertGreater(displaced.common(self.placed[stop]).Volume, 1e-5,
                                   f"No positive {'front' if sign>0 else 'rear'} stop: {item['id']}")

    def test_screws_require_rotation_and_can_be_unscrewed(self):
        frame = self.placed["capture-frame"]
        for item in self.instances:
            if item.get("motion") != "helical":
                continue
            shape = self.placed[item["id"]]
            pulled = shape.copy()
            pulled.translate(App.Vector(0,0,-1.6))
            self.assertGreater(pulled.common(frame).Volume, .1, item["id"])
            x, y = item["xy"]
            for distance in (.4,1.6,3.2,6.4,12.8,18):
                turned = shape.copy()
                turned.rotate(App.Vector(x,y,0),App.Vector(0,0,1),-360*distance/item["pitch_mm"])
                turned.translate(App.Vector(0,0,-distance))
                self.assertLess(turned.common(frame).Volume, 1e-5, f"{item['id']} at {distance}")

    def test_back_cover_and_all_inserts_have_rearward_release_paths(self):
        remaining = dict(self.placed)
        for item in self.instances:
            if item.get("motion") == "helical":
                del remaining[item["id"]]
        order = [next(i for i in self.instances if i["id"]=="back-cover")]
        order += sorted([i for i in self.instances if "front_stop" in i], key=lambda i:-i["step"])
        for item in order:
            shape = remaining.pop(item["id"])
            if "tool_target_xy" in item:
                x, y = item["tool_target_xy"]
                tip = Part.makeBox(1.6,2.4,2,App.Vector(-.8,-1.2,item["front_z"]-.1))
                tip.rotate(App.Vector(),App.Vector(0,0,1),item["tool_tip_rotation_deg"])
                tip.translate(App.Vector(x,y,0))
                self.assertGreater(tip.common(shape).Volume,1e-5, f"No tool contact: {item['id']}")
                for name, fixed in remaining.items():
                    if tip.BoundBox.intersect(fixed.BoundBox):
                        self.assertLess(tip.common(fixed).Volume,1e-5,f"Tool blocked: {item['id']}/{name}")
            for distance in (.2,1,4,12,24):
                moved = shape.copy()
                moved.translate(App.Vector(0,0,-distance))
                for name, fixed in remaining.items():
                    if moved.BoundBox.intersect(fixed.BoundBox):
                        self.assertLess(moved.common(fixed).Volume,1e-5,
                                        f"Release blocked: {item['id']}/{name}/{distance}")

    def test_coupon_uses_the_actual_color_insert_and_screw(self):
        frame, cover = self.shapes["CAPTURE-FRAME"], self.shapes["CAPTURE-COVER"]
        tile = self.shapes["IN-W-1x1"].copy()
        tile.translate(App.Vector(-12,0,0))
        self.assertLess(tile.common(frame).Volume,1e-5)
        self.assertLess(tile.common(cover).Volume,1e-5)
        for dz, stop in ((.65,frame),(-.65,cover)):
            shifted=tile.copy()
            shifted.translate(App.Vector(0,0,dz))
            self.assertGreater(shifted.common(stop).Volume,1e-5)


if __name__ == "__main__":
    unittest.main()
