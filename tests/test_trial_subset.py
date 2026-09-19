import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class TrialSubsetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "design/trial-subset.json").read_text())
        cls.catalog = json.loads((ROOT / "design/catalog.json").read_text())
        cls.folder = ROOT / "site/downloads/trial-subset"
        cls.manifest = json.loads((cls.folder / "manifest.json").read_text())

    def test_one_variant_seven_parts_in_two_stages(self):
        self.assertEqual(len(self.manifest["parts"]), 6)
        self.assertTrue(self.manifest["select_one_variant_only"])
        self.assertFalse(self.manifest["sliced"])
        self.assertFalse(self.manifest["physical_trial_performed"])
        self.assertFalse(self.manifest["geometry_changed"])
        for variant in self.manifest["variants"]:
            rows = variant["rows"]
            self.assertEqual(sum(row["quantity"] for row in rows), 7)
            self.assertEqual(sum(row["quantity"] for row in rows if row["stage"] == "real-blocks"), 4)
            self.assertEqual(sum(row["quantity"] for row in rows if row["stage"] == "keeper-base"), 3)
            expected = {
                "BR-02x02-H096": 2, "BR-02x04-H096": 2, "NP3-KEEPER": 1,
                next(value["base_part"] for value in self.config["variants"] if value["id"] == variant["model"]): 2,
            }
            self.assertEqual({row["part"]: row["quantity"] for row in rows}, expected)
            self.assertEqual(len(rows), 4)

    def test_selected_base_is_the_real_repeated_left_end(self):
        for variant in self.config["variants"]:
            model = next(model for model in self.catalog["models"] if model["id"] == variant["id"])
            matching = [item for item in model["placements"] if item["part"] == variant["base_part"]]
            self.assertEqual(len(matching), 2)
            self.assertEqual([item["course"] for item in matching], [2, 4])
            self.assertTrue(all(item["position"][0] == 0 and item["rotation"] == [0, 0, 0] for item in matching))
            part = self.catalog["parts"][variant["base_part"]]
            self.assertEqual(part["studs"][0], 3)
            self.assertEqual(part["reserved_rows"], [0])
            self.assertFalse(part["bottom_course"])

    def test_archive_contains_exact_current_masters_and_small_boms(self):
        with zipfile.ZipFile(ROOT / "site/downloads/trial-subset.zip") as archive:
            files = archive.namelist()
            expected = {part["stl"] for part in self.manifest["parts"]}
            self.assertEqual({name for name in files if name.endswith(".stl")}, expected)
            self.assertFalse(any(name.endswith((".3mf", ".mp4", ".png", ".jpg", ".FCStd", ".blend")) for name in files))
            self.assertFalse(any("FIT-" in name for name in files))
            self.assertEqual(json.loads(archive.read("manifest.json")), self.manifest)
            self.assertEqual(archive.read("fit-log.csv"), (ROOT / "site/downloads/fit-log.csv").read_bytes())
            for part in self.manifest["parts"]:
                current = self.catalog["parts"][part["id"]]
                data = (ROOT / "site/downloads" / current["stl"]).read_bytes()
                self.assertEqual(archive.read(part["stl"]), data)
                self.assertEqual(hashlib.sha256(data).hexdigest(), part["sha256"])
                self.assertEqual(part["sha256"], current["sha256"])
                self.assertEqual(part["orientation"], current["orientation"])
            for variant in self.manifest["variants"]:
                data = (self.folder / variant["bom"]).read_bytes()
                self.assertEqual(archive.read(variant["bom"]), data)
                rows = list(csv.DictReader(io.StringIO(data.decode())))
                self.assertEqual(sum(int(row["quantity"]) for row in rows), 7)

    def test_geometry_and_other_product_are_unchanged(self):
        baseline = self.config["geometry_baseline_commit"]
        frozen = ["design/parameters.json", "design/interface.json", "design/catalog.json",
                  "scripts/design.py", "scripts/freecad_geometry.py", "scripts/front_nameplate.py",
                  "resources/github-mark-relief.json"]
        media_suffixes = {".FCStd", ".step", ".stl", ".blend", ".mp4", ".png", ".svg", ".3mf", ".pdf"}
        for folder in ("site/downloads", "site/media", "site/drawings"):
            frozen.extend(str(path.relative_to(ROOT)) for path in (ROOT / folder).rglob("*")
                          if path.is_file() and path.suffix in media_suffixes)
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", baseline, "--", *frozen,
             "projects/character-tribute", "site/tribute"], cwd=ROOT, text=True)
        self.assertEqual(changed, "", "This is a manufacturing-guidance update, not a geometry/media change.")

    def test_documents_and_empty_log_keep_failure_boundary(self):
        trial = (ROOT / "docs/trial.ja.md").read_text()
        for phrase in ("7個の確認は、5段完成品", "原因", "断定できません", "0.2 mm", "全数印刷を止めます",
                       "1条件ずつ", "そのまま公開しません", "未試験", "同一の左端形状を2個"):
            self.assertIn(phrase, trial)
        self.assertIn(self.config["source_observation"]["commit"], trial)
        self.assertIn("trial.ja.md", (ROOT / "docs/build.ja.md").read_text())
        rows = list(csv.reader(io.StringIO((ROOT / "site/downloads/fit-log.csv").read_text())))
        self.assertEqual(len(rows), 1, "Do not manufacture measurements in the log template.")
        for column in ("source_stl_sha256", "printer_nozzle_preset", "plate_type", "support_mode",
                       "brim_mode", "preview_first_layer_entry_open", "preview_roof_bridge_rib_paths",
                       "observed_obstruction", "hand_grip_result", "one_changed_setting", "stop_or_continue"):
            self.assertIn(column, rows[0])
        self.assertEqual(self.config["source_observation"]["report_blob_sha"],
                         "cfc12acc88c12e722150abc81740e8af32b7182a")


if __name__ == "__main__":
    unittest.main()
