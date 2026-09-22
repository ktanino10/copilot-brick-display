import hashlib
import json
from pathlib import Path
import sys
import unittest
import zipfile

import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from legible_metrics import plan_rows
from verify_meshes import vertex_links_are_cycles


class LetteringRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads((ROOT / "design/parameters.json").read_text())
        cls.c = json.loads((ROOT / "design/catalog.json").read_text())

    def test_authorized_short_placeholder_and_real_dimensions(self):
        self.assertEqual(self.c["message"]["lines"], ["Same icon, New adventures", "github.com/USER"])
        self.assertEqual(self.c["revision"], "5.0-legible-plaques")
        self.assertEqual(self.c["message"]["relief"], 1.2)
        self.assertEqual(self.c["message"]["thickness"], 2.4)
        self.assertEqual(self.c["logo"]["relief"], .8)
        expected = {"A": ([143.8, 64.2, 187.4], 91), "B": ([191.8, 80.2, 238.6], 150),
                    "C": ([239.8, 112.2, 286.6], 228)}
        for model in self.c["models"]:
            self.assertEqual((model["actual_mm"], model["part_count"]), expected[model["id"]])
            self.assertEqual(model["text_heights"][1], 10)
            self.assertEqual(self.c["parts"][f"NP3-TEXT-{model['id']}"]["bounds"][1][2], 3.6)

    def test_saved_native_metrics_bind_to_current_source_and_positive_material(self):
        report = json.loads((ROOT / "validation/lettering.json").read_text())
        self.assertEqual(report["revision"], self.c["revision"])
        self.assertEqual(report["parameters_sha256"], self.c["parameters_sha256"])
        for model in report["models"]:
            path = ROOT / f"site/downloads/{model['model']}/{model['model']}.FCStd"
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), model["native_sha256"])
            self.assertEqual(model["carrier_symmetric_difference_mm3"], 0)
            self.assertLess(model["current_lettering_symmetric_difference_mm3"], 1e-5)
            for row in model["rows"]:
                self.assertLessEqual(row["actual_width_mm"], self.c["parts"][model["part"]]["width"] - 8 + .0001)
                self.assertGreaterEqual(row["minimum_actual_gap_mm"], row["targets"]["adjacent_glyph_clearance"] - .006)
                self.assertGreaterEqual(row["minimum_parallel_straight_stroke_mm"], .84)
                for glyph in row["glyphs"]:
                    neck = glyph["persistent_core_split_neck_mm"]
                    if neck is not None:
                        self.assertGreaterEqual(neck, .84)
        self.assertEqual(report["physical_trial"], "NOT_PERFORMED")

    def test_all_68_nontext_masters_and_installation_poses_remain_identical(self):
        baseline = json.loads((ROOT / "design/public-template-invariants.json").read_text())
        self.assertEqual(len(baseline["unchanged_nontext_stl_sha256"]), 68)
        for part, sha in baseline["unchanged_nontext_stl_sha256"].items():
            self.assertEqual(self.c["parts"][part]["sha256"], sha)
            self.assertEqual(hashlib.sha256((ROOT / "site/downloads" / self.c["parts"][part]["stl"]).read_bytes()).hexdigest(), sha)
        for old, new in zip(baseline["models"], self.c["models"]):
            self.assertEqual(old["placements"], [{key: item[key] for key in old["placements"][i]} for i, item in enumerate(new["placements"])])

    def test_overwide_text_stops_without_compression_or_mutating_input(self):
        row = {"number": 1, "glyphs": [{"index": 0, "character": "X", "faces": [
            {"outer": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]], "holes": []}]}]}
        before = json.dumps(row)
        with self.assertRaisesRegex(ValueError, "do not shrink or truncate"):
            plan_rows([row], {"counter_central_half_chord": 1.02, "e_exit_channel": 1.1,
                              "adjacent_glyph_clearance": 1.05}, 19)
        self.assertEqual(json.dumps(row), before)

    def test_trial_glyphs_have_exact_source_scale_and_are_not_assembly_parts(self):
        folder = ROOT / "site/downloads/lettering-coupons"
        report = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(report["revision"], self.c["revision"])
        self.assertFalse(report["sliced"])
        self.assertFalse(report["physical_trial_performed"])
        for model in report["models"]:
            self.assertEqual(model["installed_quantity"], 0)
            self.assertEqual(model["source_plate_sha256"], self.c["parts"][model["source_plate"]]["sha256"])
            for row in model["rows"]:
                for glyph in row["glyphs"]:
                    self.assertFalse(glyph["scale_changed"])
                    if glyph["actual_gap_to_previous_mm"] is not None:
                        self.assertAlmostEqual(glyph["actual_gap_to_previous_mm"], row["spacing_target_mm"], places=5)
            mesh = trimesh.load_mesh(folder / f"{model['coupon']}.stl")
            self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent and vertex_links_are_cycles(mesh))
            self.assertEqual(mesh.body_count, 1)
            self.assertGreater(mesh.volume, 0)
            self.assertAlmostEqual(mesh.bounds[1][2], 3.6, places=5)
            scene = trimesh.load_scene(folder / f"{model['coupon']}.3mf")
            self.assertEqual(len(scene.graph.nodes_geometry), 1)
            for suffix, sha in model["hashes"].items():
                self.assertEqual(hashlib.sha256((folder / f"{model['coupon']}.{suffix}").read_bytes()).hexdigest(), sha)
            self.assertNotIn(model["coupon"], self.c["parts"])
        with zipfile.ZipFile(ROOT / "site/downloads/lettering-coupons.zip") as archive:
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (folder / name).read_bytes())

    def test_current_docs_preserve_pause_boundaries_and_uncertainty(self):
        text = (ROOT / "docs/lettering.ja.md").read_text()
        for phrase in ("github.com/USER", "NOT_SLICED", "1.2 mm", "2.4 mm", "0.90 mm",
                       "0.95 mm", "0.80 mm", "未受領", "dot/slash", "一条件ずつ", "孔を広げても材料"):
            self.assertIn(phrase, text)
        self.assertNotIn('href="https://github.com/USER"', (ROOT / "site/index.html").read_text())


if __name__ == "__main__":
    unittest.main()
