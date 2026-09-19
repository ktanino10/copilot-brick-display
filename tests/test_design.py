import json
import math
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from design import build_catalog, load_parameters


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load_parameters()
        cls.c = build_catalog(cls.p)

    def test_exact_approved_message(self):
        self.assertEqual(self.p["message"]["lines"], [
            "Same icon, New adventures", "github.com/YOUR-USERNAME"])
        self.assertNotIn("MSG-CARD", self.c["parts"])
        self.assertNotIn("MSG-DOCK", self.c["parts"])

    def test_distinct_fixed_grid_layouts(self):
        self.assertEqual([v["base_studs"] for v in self.c["models"]],
                         [[18, 8], [24, 10], [30, 14]])
        for model in self.c["models"]:
            for item in model["placements"]:
                if item["part"].startswith("BR-"):
                    self.assertEqual(item["rotation"], [0, 0, 0])
                    self.assertAlmostEqual(item["position"][0] % 8, 0)
                    self.assertAlmostEqual(item["position"][1] % 8, 0)

    def test_quantities_and_steps(self):
        for model in self.c["models"]:
            expected = Counter((x["part"], x["color"]) for x in model["placements"])
            actual = {(x["part"], x["color"]): x["quantity"] for x in model["bom"]}
            self.assertEqual(dict(expected), actual)
            self.assertEqual(sum(actual.values()), model["part_count"])
            instances = [x for s in model["steps"] for x in s["instances"]]
            self.assertEqual(sorted(instances), sorted(x["id"] for x in model["placements"]))
            self.assertEqual(len(instances), len(set(instances)))

    def test_body_course_support_and_no_occupied_cell_overlap(self):
        for model in self.c["models"]:
            top_studs = defaultdict(set)
            occupied = set()
            for item in model["placements"]:
                spec = self.c["parts"][item["part"]]
                if spec["kind"] not in ("brick", "front_base"):
                    continue
                x, y, z = item["position"]
                nx, ny = spec["studs"]
                cells = {(round(x / 8) + a, round(y / 8) + b)
                         for a in range(nx) for b in range(ny)}
                if z > 0:
                    self.assertGreaterEqual(len(cells & top_studs[round(z, 6)]), 2,
                                            f"{item['id']} is insufficiently supported")
                keys = {(a, b, z) for a, b in cells}
                self.assertFalse(keys & occupied, item["id"])
                occupied |= keys
                top_studs[round(z + spec["height"], 6)] |= cells
                for row in spec.get("reserved_rows", []):
                    top_studs[round(z + spec["height"], 6)] -= {
                        (round(x / 8) + a, round(y / 8) + row) for a in range(nx)}

    def test_grid_ribs_clear_reference_studs(self):
        i = self.p["interface"]
        margin = i["pitch"] / 2 - i["reference_stud_diameter"] / 2 - i["roof_support_rib_width"] / 2
        self.assertGreaterEqual(margin, 1.0)
        tube_r = i["pitch"] / math.sqrt(2) - i["reference_stud_diameter"] / 2 - i["female_radial_clearance"]
        self.assertGreater(tube_r - i["tube_inner_diameter"] / 2, 1.2)

    def test_thin_plate_headroom_and_base_front_message(self):
        i, m = self.p["interface"], self.p["message"]
        self.assertGreaterEqual(i["plate_height"] - i["thin_plate_roof"] - i["stud_height"], 0.39)
        self.assertGreater(m["minimum_straight_stroke"], .8)
        self.assertGreaterEqual(m["bottom_z"], 0)
        self.assertLessEqual(m["bottom_z"] + m["height"], 48)
        self.assertGreaterEqual(m["back_y"] - m["thickness"] - m["relief"], .099)
        for model in self.c["models"]:
            plaque = next(x for x in model["placements"] if x.get("module") == "text" and x.get("role") == "front_module")
            self.assertEqual(plaque["rotation"], [90, 0, 0])
            self.assertEqual(plaque["color"], "black")
            self.assertEqual(plaque["position"][2], m["bottom_z"])
            self.assertEqual(model["base_courses"], 5)
            self.assertEqual(model["base_body_height_mm"], 48)
            self.assertEqual(len([x for x in model["placements"] if x["part"] == "NP3-KEEPER"]), 3)
            for bottom, height in zip(m["line_bottoms"], model["text_heights"]):
                self.assertGreaterEqual(bottom, 2)
                self.assertLessEqual(bottom + height, m["height"] - 2)
            self.assertLessEqual(max(model["base_segments_x"]) * 8 - i["body_gap"] + 12, 256)
            self.assertLessEqual(model["base_studs"][1] * 8 - i["body_gap"] + 12, 256)


if __name__ == "__main__":
    unittest.main()
