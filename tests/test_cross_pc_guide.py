import csv
import io
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


class CrossPCGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "design/catalog.json").read_text())
        cls.guide = (ROOT / "docs/build.ja.md").read_text()

    def test_all_variants_have_direct_downloads_without_selecting_one_for_user(self):
        self.assertIn('id="print-another-pc"', self.guide)
        self.assertIn("1案だけ選んでください", self.guide)
        self.assertIn("Bを選択済みという意味ではありません", self.guide)
        for model in "ABC":
            self.assertIn(f"../site/index.html?model={model}", self.guide)
            for name in ("print-kit.zip", "plates.zip", "bom.csv", "drawings.pdf"):
                self.assertIn(f"../site/downloads/{model}/{name}", self.guide)
                self.assertTrue((ROOT / "site/downloads" / model / name).is_file())

    def test_documented_color_plate_ranges_match_actual_manifests(self):
        expected_counts = {
            "A": {"black": 4, "cyan": 1, "magenta": 1, "green": 1},
            "B": {"black": 7, "cyan": 2, "magenta": 2, "green": 1},
            "C": {"black": 16, "cyan": 5, "magenta": 3, "green": 1},
        }
        for model, colors in expected_counts.items():
            root = ROOT / "site/downloads" / model
            manifest = json.loads((root / "plates/manifest.json").read_text())
            ordinary = [plate for plate in manifest["plates"] if not plate["finish_color"]]
            expected_names = set()
            for color, count in colors.items():
                actual = {plate["file"] for plate in ordinary if plate["color"] == color}
                names = {f"{model}-{color}-{index:02}.3mf" for index in range(1, count + 1)}
                self.assertEqual(actual, names)
                expected_names |= names
                self.assertIn(f"{model}-{color}-01.3mf", self.guide)
                self.assertIn(f"{model}-{color}-{count:02}.3mf", self.guide)
            self.assertEqual(len(manifest["plates"]), sum(colors.values()) + 2)
            with zipfile.ZipFile(root / "plates.zip") as archive:
                expected_names |= {plate["file"] for plate in manifest["plates"] if plate["finish_color"]}
                self.assertEqual(set(archive.namelist()), expected_names | {"manifest.json"})
                self.assertEqual(json.loads(archive.read("manifest.json")), manifest)
                for name in expected_names:
                    self.assertEqual(archive.read(name), (root / "plates" / name).read_bytes())

    def test_white_relief_is_integral_and_generic_3mf_does_not_schedule_pause(self):
        for model in self.catalog["models"]:
            root = ROOT / "site/downloads" / model["id"]
            plates = json.loads((root / "plates/manifest.json").read_text())["plates"]
            with (root / "bom.csv").open() as source:
                bom = list(csv.DictReader(source))
            finishes = [plate for plate in plates if plate["finish_color"]]
            self.assertEqual(len(finishes), 2)
            for kind, height, suffix in (("TEXT", 2.4, "2p4"), ("LOGO", 2.8, "2p8")):
                part_id = f"NP3-{kind}-{model['id']}"
                part = self.catalog["parts"][part_id]
                self.assertEqual(part["optional_color_change_z"], height)
                self.assertEqual(part["letter_color"], "white")
                self.assertAlmostEqual(part["bounds"][1][2], height + .8, places=5)
                row = next(row for row in bom if row["part"] == part_id)
                self.assertEqual((row["color"], row["finish_color"], row["quantity"]), ("black", "white", "1"))
                self.assertEqual(float(row["color_change_z_mm"]), height)
                filename = f"{model['id']}-black-to-white-z{suffix}-01.3mf"
                self.assertIn(filename, self.guide)
                plate = next(plate for plate in finishes if plate["file"] == filename)
                self.assertEqual(plate["manual_change_after_z_mm"], height)
                self.assertEqual([item["part"] for item in plate["items"]], [part_id])
                with zipfile.ZipFile(root / "plates" / filename) as archive:
                    self.assertEqual(set(archive.namelist()),
                                     {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"})
                    content = archive.read("3D/3dmodel.model")
                    self.assertNotIn(b"M600", content)
                    self.assertNotIn(b"M400", content)
                    xml = ET.fromstring(content)
                    self.assertEqual(xml.get("unit"), "millimeter")
                    self.assertEqual(len(xml.findall("m:build/m:item", NS)), 1)
                    self.assertEqual([base.get("name") for base in xml.findall("m:resources/m:basematerials/m:base", NS)],
                                     ["black"])

    def test_guide_states_stop_go_and_no_unapproved_private_upload(self):
        for phrase in ("NOT_SLICED", "二重配置", "Download raw file", "各1個", "FIT-M-D470",
                       "FIT-F-CP12", "初層", "ブリッジ", "一時停止（Pause）も色替え命令も自動設定されていません",
                       "完全別体にしたい場合は設計変更", "未受領", "個人", "履歴", "cache", "private"):
            if phrase == "未受領":
                self.assertIn("まだこちらでは受領・照合していません", self.guide)
            else:
                self.assertIn(phrase, self.guide)
        self.assertIn("2.4 mm", self.guide)
        self.assertIn("2.8 mm", self.guide)
        self.assertIn("次の白い文字層を出す前", self.guide)
        self.assertIn("次の白い図柄層を出す前", self.guide)
        policy = json.loads((ROOT / "design/publication-policy.json").read_text())
        self.assertEqual(policy["mode"], "generic")
        self.assertFalse(policy["public_text_approved"])
        self.assertEqual(self.catalog["message"]["lines"][1], "github.com/YOUR-USERNAME")

    def test_embedded_print_guides_and_entry_links_are_current(self):
        for model in "ABC":
            with zipfile.ZipFile(ROOT / "site/downloads" / model / "print-kit.zip") as archive:
                readme = archive.read("READ-FIRST-ja.md").decode()
                self.assertIn('id="print-another-pc"', readme)
                self.assertIn("separate-color-2026-09-19", readme)
                self.assertIn(f"{model}-black-to-white-z2p4-01.3mf", readme)
                with zipfile.ZipFile(io.BytesIO(archive.read("fit-coupons.zip"))) as coupons:
                    self.assertEqual(coupons.read("READ-FIRST-ja.md").decode(), readme)
        for filename in ("README.md", "site/index.html", "site/guide.html"):
            self.assertIn("print-another-pc", (ROOT / filename).read_text())
        with zipfile.ZipFile(ROOT / "site/downloads/trial-subset.zip") as archive:
            self.assertIn("https://ktanino10.github.io/copilot-brick-display/guide.html#print-another-pc",
                          archive.read("READ-FIRST-ja.md").decode())


if __name__ == "__main__":
    unittest.main()
