import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site_docs import links
from verify_build_log import verify_photos, PHOTO_NAMES, MASKS


class BuildLogTests(unittest.TestCase):
    def test_exact_approved_photos_are_flattened_and_metadata_free(self):
        report = verify_photos()
        self.assertEqual(len(report["photos"]), 9)
        self.assertEqual(sum(len(rectangles) for rectangles in MASKS.values()), 4)
        self.assertFalse(report["physical_qualification_claimed"])
        self.assertFalse(report["source_photographs_accessed"])

    def test_one_canonical_log_has_five_explanation_stages_and_nine_real_photos(self):
        source = (ROOT / "docs/build-log.ja.md").read_text()
        body = links(markdown.markdown(source, extensions=["tables", "fenced_code", "toc"]))
        page = (ROOT / "site/build-log.html").read_text()
        self.assertIn("制作記録 — Bの台座と前面モジュール", page)
        self.assertEqual(len(re.findall(r"^### 0[1-5] — ", source, re.M)), 5)
        photos = re.findall(r'<img[^>]+src="([^"]+)"', body)
        self.assertEqual(len(photos), 9)
        self.assertEqual({Path(urlsplit(ref).path).name for ref in photos}, PHOTO_NAMES)
        rendered_photos = re.findall(r'<img[^>]+src="([^"]+)"', page)
        self.assertEqual([urlsplit(ref).path for ref in rendered_photos],
                         [urlsplit(ref).path for ref in photos])
        for ref in photos:
            self.assertTrue((ROOT / "site" / urlsplit(ref).path).is_file())
        self.assertNotIn("<canvas", body)
        self.assertNotIn("<svg", body)
        self.assertNotIn("position:absolute", body)
        self.assertNotRegex(page, r'(?:href|src)=["\'][^"\']*(?:github\.com/USER|\.private/|PXL_)')

    def test_report_photo_observation_design_and_unmeasured_bounds_are_distinct(self):
        text = (ROOT / "docs/build-log.ja.md").read_text()
        for phrase in ("2026-09-23", "09/22", "12:09", "12:18", "いけているみたい", "土台が組み上がりました",
                       "報告時刻", "説明する順番", "上が旧版・下が新版などとは断定しません",
                       "個人向けB版", "公開の汎用文字版・A/C", "全150部品", "保持力", "転倒", "寿命",
                       "STLハッシュ", "未照合", "NOT_SLICED", "画像の画素へ焼き込み",
                       "CC0化や第三者への再配布許諾を意味しません", "再利用は権利者へ確認"):
            self.assertIn(phrase, text)
        self.assertIn("写真番号", text)
        self.assertNotIn("source_path", text)
        catalog = json.loads((ROOT / "design/catalog.json").read_text())
        self.assertEqual(catalog["message"]["lines"][1], "github.com/USER")
        self.assertEqual(json.loads((ROOT / "site/downloads/validation.json").read_text())["physical_testing"],
                         "NOT_PERFORMED")

    def test_all_requested_entry_points_link_the_log(self):
        for source in ("README.md", "docs/build.ja.md", "docs/lettering.ja.md", "docs/assembly.ja.md"):
            self.assertIn("build-log.ja.md", (ROOT / source).read_text())
        for page in ("index.html", "guide.html", "lettering.html", "assembly.html", "notices.html"):
            self.assertIn('href="build-log.html', (ROOT / "site" / page).read_text())


if __name__ == "__main__":
    unittest.main()
