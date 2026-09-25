import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site_docs import links
from verify_build_log import verify_photos, FOLDER, PHOTO_NAMES, MASKS, PHOTO_SETS


class BuildLogTests(unittest.TestCase):
    def test_exact_approved_photos_are_flattened_and_metadata_free(self):
        self.assertEqual(set(PHOTO_SETS), {"2026-09-23", "2026-09-24", "2026-09-25"})
        for date, count in (("2026-09-23", 9), ("2026-09-24", 7), ("2026-09-25", 8)):
            report = verify_photos(report_date=date)
            self.assertEqual(len(report["photos"]), count)
            self.assertFalse(report["physical_qualification_claimed"])
            self.assertFalse(report["source_photographs_accessed"])
        self.assertEqual(sum(len(rectangles) for rectangles in MASKS.values()), 4)

    def test_unapproved_photo_changes_and_extra_images_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "public-derivatives"
            shutil.copytree(FOLDER, folder)
            extra = folder / "unapproved.jpg"
            extra.write_bytes(b"not an approved photo")
            with self.assertRaisesRegex(ValueError, "Unexpected file"):
                verify_photos(folder)
            extra.unlink()
            target = folder / "lettering-first.jpg"
            target.write_bytes(target.read_bytes() + b"unexpected trailing data")
            with self.assertRaisesRegex(ValueError, "Approved photo bytes differ"):
                verify_photos(folder)

    def test_one_canonical_log_preserves_dated_progress_and_adds_completion(self):
        source = (ROOT / "docs/build-log.ja.md").read_text()
        body = links(markdown.markdown(source, extensions=["tables", "fenced_code", "toc"]))
        page = (ROOT / "site/build-log.html").read_text()
        self.assertIn("制作記録 — Bの台座から完成まで", page)
        self.assertEqual(len(re.findall(r"^### 0[1-5] — ", source, re.M)), 5)
        self.assertEqual(len(re.findall(r"^### 09/24・0[1-4] — ", source, re.M)), 4)
        self.assertEqual(len(re.findall(r"^### 09/25・0[1-4] — ", source, re.M)), 4)
        photos = re.findall(r'<img[^>]+src="([^"]+)"', body)
        self.assertEqual(len(photos), 24)
        for date, expected in PHOTO_SETS.items():
            dated = [ref for ref in photos if f"media/build-log/{date}/" in ref]
            self.assertEqual({Path(urlsplit(ref).path).name for ref in dated}, expected["photo_names"])
            self.assertIn(f'id="build-{date}"', page)
            self.assertIn(f'href="#build-{date}"', page)
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
        for phrase in ("2026-09-24", "22:27", "こちらは組み立ての途中記録になります",
                       "紫・黄は実制作例の配色", "magenta／green", "黒い板状物の用途は未確認",
                       "保持具・必須部品・補強材・失敗対策とは断定しません",
                       "上部ゴーグル・頭頂の完成は未確認", "顔下部", "添付順やファイル名"):
            self.assertIn(phrase, text)
        introduction = text.split("## 本人の報告と、ここまでの学び")[0]
        self.assertIn("個人向けBが完成しました", introduction)
        self.assertNotIn("完成した写真ではありません", introduction)
        self.assertIn("21:44", text)
        self.assertIn("これで完成ですね", text)
        self.assertIn("個人向けBの完成報告と完成写真", text)
        current = text.split('<a id="build-2026-09-25"></a>')[1].split('<a id="build-2026-09-24"></a>')[0]
        self.assertNotIn("完成は未確認", current)
        self.assertNotIn("合格したとは", current)

    def test_all_requested_entry_points_link_the_log(self):
        for source in ("README.md", "docs/build.ja.md", "docs/lettering.ja.md", "docs/assembly.ja.md"):
            self.assertIn("build-log.ja.md", (ROOT / source).read_text())
        for page in ("index.html", "guide.html", "lettering.html", "assembly.html", "notices.html"):
            self.assertIn('href="build-log.html', (ROOT / "site" / page).read_text())
        for source in ("README.md", "docs/build.ja.md", "docs/lettering.ja.md", "docs/assembly.ja.md"):
            self.assertIn("build-log.ja.md#build-2026-09-25", (ROOT / source).read_text())

    def test_observed_colors_do_not_change_the_public_design(self):
        parameters = json.loads((ROOT / "design/parameters.json").read_text())
        catalog = json.loads((ROOT / "design/catalog.json").read_text())
        self.assertEqual(parameters["colors"], catalog["colors"])
        self.assertEqual(parameters["colors"]["magenta"]["hex"], "#c42eaa")
        self.assertEqual(parameters["colors"]["green"]["hex"], "#42df83")
        self.assertNotIn("yellow", parameters["colors"])
        self.assertNotIn("purple", parameters["colors"])
        receipt = json.loads((ROOT / "validation/build-log-design-boundary-2026-09-25.json").read_text())
        self.assertEqual(receipt["previous_photo_count"], 16)
        self.assertEqual(receipt["geometry_revision"], catalog["revision"])
        for field in ("design_colors_changed", "placement_or_bom_changed", "manufacturing_or_native_changed",
                      "existing_physical_qualification_status_changed"):
            self.assertFalse(receipt[field])

    def test_completion_is_celebrated_without_rewriting_historical_progress(self):
        text = (ROOT / "docs/build-log.ja.md").read_text()
        current = text.split('<a id="build-2026-09-25"></a>')[1].split('<a id="build-2026-09-24"></a>')[0]
        previous = text.split('<a id="build-2026-09-24"></a>')[1].split('<a id="build-2026-09-23"></a>')[0]
        self.assertIn("これで完成ですね", current)
        self.assertIn("個人向けBの完成報告と完成写真", current)
        self.assertIn("8枚をそのまま8つのCAD工程", current)
        self.assertIn("上部ゴーグル・頭頂の完成は未確認", previous)
        self.assertNotIn("量産", current)
        self.assertEqual(text.count('<a id="evidence-boundary"></a>'), 1)
        boundary = text.split('<a id="evidence-boundary"></a>')[1].split("## これから作る方へ")[0]
        for phrase in ("STLハッシュ", "実preset", "未照合", "保持力", "量産・玩具認証", "公開の汎用文字版・A/C"):
            self.assertIn(phrase, boundary)

    def test_supplied_cleaning_video_is_an_external_link_not_an_embed(self):
        source = (ROOT / "docs/build-log.ja.md").read_text()
        page = (ROOT / "site/build-log.html").read_text()
        url = "https://youtu.be/Lc_enNE3nng"
        title = "3Dプリント後のパーツを超音波洗浄｜Ultrasonic Cleaning of 3D-Printed Parts"
        self.assertEqual(source.count(f"]({url})"), 1)
        self.assertEqual(page.count(f'href="{url}"'), 1)
        self.assertIn(title, source)
        self.assertIn('id="post-print-cleaning"', page)
        self.assertIn("docs/build-log.ja.md#post-print-cleaning", (ROOT / "README.md").read_text())
        self.assertIn("本編・字幕は未視聴", source)
        self.assertIn("機器・洗浄液・温度・時間・効果は未確認", source)
        self.assertIn("本制作の必須工程や、安全検証済みの手順としては案内していません", source)
        self.assertNotRegex(page, r"<(?:iframe|video|audio)\b")
        self.assertNotRegex(page, r"""src=["'][^"']*(?:youtu|ytimg)""")


if __name__ == "__main__":
    unittest.main()
