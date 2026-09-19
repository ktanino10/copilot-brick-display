"""Run using the FreeCAD-bundled Python and its lib directory on PYTHONPATH."""
import json
from pathlib import Path
import unittest

import FreeCAD as App
from relief_geometry import relief_depths, relief_shapes
from stand_geometry import custom_coupons, stand_body

ROOT = Path(__file__).resolve().parents[1]


class ReliefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "parameters.json").read_text())
        cls.shapes = relief_shapes(cls.data)

    def test_exact_message(self):
        self.assertEqual(self.data["message"],
                         ["@YOUR-USERNAME", "Same icon, New adventures", "github.com/YOUR-USERNAME"])

    def test_solids_and_print_envelopes(self):
        for part_id, shape in self.shapes.items():
            with self.subTest(part=part_id):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
                self.assertGreater(shape.Volume, 0)
                self.assertLessEqual(shape.BoundBox.XLength + 16, 256)
                self.assertLessEqual(shape.BoundBox.YLength + 16, 256)

    def test_interference_and_supported_contacts(self):
        depths = relief_depths(self.data)
        placed = {}
        for item in self.data["instances"]:
            shape = self.shapes[item["part"]].copy()
            shape.translate(App.Vector(*item["xy"], depths[item["id"]]))
            placed[item["id"]] = shape
            if item["parent"]:
                parent = placed[item["parent"]]
                self.assertLess(shape.distToShape(parent)[0], 1e-6, item["id"])
        items = list(placed.items())
        for index, (name, shape) in enumerate(items):
            for other_name, other in items[index + 1:]:
                if shape.BoundBox.intersect(other.BoundBox):
                    self.assertLess(shape.common(other).Volume, 1e-5,
                                    f"{name} interferes with {other_name}")

    def test_stand_and_vertical_insertion(self):
        stand = stand_body(self.data)
        board = self.shapes["T02"].copy()
        board.rotate(App.Vector(), App.Vector(1, 0, 0), 90)
        board.translate(App.Vector(0, self.data["board"]["back_y"],
                                   self.data["board"]["bottom_z"]))
        self.assertEqual(len(stand.Solids), 1)
        self.assertTrue(stand.isValid())
        self.assertLess(stand.common(board).Volume, 1e-5)
        self.assertLess(stand.distToShape(board)[0], 1e-6)
        for offset in (0.1, 4, 16, 32, 40):
            lifted = board.copy()
            lifted.translate(App.Vector(0, 0, offset))
            self.assertLess(stand.common(lifted).Volume, 1e-5)
        self.assertAlmostEqual(board.BoundBox.ZMax, 201.6)

    def test_custom_calibration_solids(self):
        for part_id, shape in custom_coupons(self.data).items():
            with self.subTest(part=part_id):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
                self.assertGreater(shape.Volume, 0)


if __name__ == "__main__":
    unittest.main()
