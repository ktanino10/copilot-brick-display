"""Check publication sources without writes, or inspect the generated site in Chrome."""
from collections import Counter
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class PublicationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "catalog.json").read_text())
        cls.parameters = json.loads((ROOT / "parameters.json").read_text())

    def video_evidence(self):
        return {"status": "pass", "encoded_stream": {
            "width": 960, "height": 720, "duration": "37.5",
            "avg_frame_rate": "30/1", "nb_frames": "1125"},
            "frame_count": 1125, "decoded_frames": 1125, "decode_errors": 0,
            "disassembly": {"encoded_stream": {
                "width": 640, "height": 480, "duration": "11.75", "avg_frame_rate": "24/1"},
                "frame_count": 282, "decoded_frames": 282, "decode_errors": 0}}

    def drawing_index(self):
        from publish import BASE_DRAWING_FILES
        return {"revision": "T2", "sheets": [
            {"file": name, "title": "確認図", "subtitle": "CAD CHECK"}
            for name in sorted(BASE_DRAWING_FILES)]}

    def test_counts_and_categories_come_from_catalog(self):
        from publish import catalog_counts
        counts = catalog_counts(self.catalog)
        categories = Counter(part["category"] for part in self.catalog["parts"])
        self.assertEqual(counts["print_master_count"], len(self.catalog["parts"]))
        self.assertEqual(counts["assembly_instances"], len(self.catalog["instances"]))
        for category, field in (("assembly", "assembled_unique_parts"),
                                ("coupon", "coupon_unique_parts"), ("tool", "tool_unique_parts")):
            self.assertEqual(counts[field], categories[category])
        self.assertEqual(counts["tool_print_quantity"], sum(
            part["tool_quantity"] for part in self.catalog["parts"] if part["category"] == "tool"))

    def test_catalog_quantity_mismatch_is_rejected(self):
        from publish import catalog_counts
        changed = deepcopy(self.catalog)
        next(part for part in changed["parts"] if part["category"] == "assembly")["quantity"] += 1
        with self.assertRaises(ValueError):
            catalog_counts(changed)

    def test_additional_tool_is_counted_without_an_assembly_instance(self):
        from publish import catalog_counts
        changed = deepcopy(self.catalog)
        extra = deepcopy(next(part for part in changed["parts"] if part["category"] == "tool"))
        extra.update(id="EXTRA-TOOL", mesh="meshes/EXTRA-TOOL.stl",
                     step="native/parts/EXTRA-TOOL.step", tool_quantity=3)
        changed["parts"].append(extra)
        before, after = catalog_counts(self.catalog), catalog_counts(changed)
        self.assertEqual(after["print_master_count"], before["print_master_count"] + 1)
        self.assertEqual(after["tool_print_quantity"], before["tool_print_quantity"] + 3)
        self.assertEqual(after["assembly_instances"], before["assembly_instances"])

    def test_tool_table_uses_catalog_quantity_and_not_coupon_label(self):
        from publish import table
        rest = next(part for part in self.catalog["parts"] if part["id"] == "ASSEMBLY-REST")
        result = table([rest], self.catalog)
        self.assertIn('data-category="tool"', result)
        self.assertIn(f'data-print-quantity="{rest["tool_quantity"]}"', result)
        self.assertIn(f'治具 {rest["tool_quantity"]}', result)
        self.assertNotIn("試験1", result)

    def test_drawing_index_allows_extra_sheets(self):
        from publish import drawing_tuples
        index = self.drawing_index()
        index["sheets"].append({"file": "retention-details.svg", "title": "保持機構",
                                "subtitle": "REMOVABLE RETENTION"})
        self.assertEqual(drawing_tuples(index)[-1],
                         ("retention-details.svg", "保持機構", "REMOVABLE RETENTION"))

    def test_drawing_index_rejects_missing_duplicate_and_nonlocal_sheets(self):
        from publish import drawing_tuples
        for change in ("missing", "duplicate", "nonlocal", "old_revision"):
            with self.subTest(change=change):
                index = self.drawing_index()
                if change == "missing":
                    index["sheets"].pop()
                elif change == "duplicate":
                    index["sheets"].append(index["sheets"][0])
                elif change == "nonlocal":
                    index["sheets"].append({"file": "../outside.svg", "title": "図", "subtitle": "VIEW"})
                else:
                    index["revision"] = "T1"
                with self.assertRaises(ValueError):
                    drawing_tuples(index)

    def test_video_properties_are_read_from_evidence(self):
        from publish import video_metadata
        result = video_metadata(self.video_evidence())
        self.assertEqual(result, {"duration_seconds": 37.5, "fps": 30.0, "frames": 1125,
                                  "width": 960, "height": 720})

    def test_incomplete_video_evidence_is_rejected(self):
        from publish import video_metadata
        for key, value in (("decoded_frames", 1), ("decode_errors", 1),
                           ("status", "pending"), ("frame_count", 1)):
            with self.subTest(key=key):
                evidence = self.video_evidence()
                evidence[key] = value
                with self.assertRaises(ValueError):
                    video_metadata(evidence)

    def test_both_videos_use_their_own_metadata_and_have_caption_assets(self):
        from publish import (drawing_tuples, download_specs, publication_urls,
                             publication_videos, public_metadata)
        videos = publication_videos(self.video_evidence())
        self.assertEqual(videos["assembly"]["duration_seconds"], 37.5)
        self.assertEqual(videos["disassembly"], {
            "duration_seconds": 11.75, "fps": 24.0, "frames": 282, "width": 640, "height": 480})
        metadata = public_metadata(self.catalog, self.parameters, videos)
        self.assertEqual(metadata["video"], metadata["videos"]["assembly"])
        for name, scene in (("assembly", "Assembly"), ("disassembly", "Disassembly")):
            self.assertEqual(metadata["videos"][name]["scene"], scene)
            self.assertEqual(metadata["videos"][name]["url"], f"media/{name}.mp4")
            self.assertEqual(metadata["videos"][name]["captions"], f"media/{name}.ja.vtt")
        downloads = {url: description for url, _, description, _ in download_specs(self.catalog, videos)}
        self.assertIn("37.5秒", downloads["media/assembly.mp4"])
        self.assertIn("11.75秒", downloads["media/disassembly.mp4"])
        assets = dict(publication_urls(self.catalog, drawing_tuples(self.drawing_index()), videos))
        for name in videos:
            self.assertEqual(assets[f"media/{name}.mp4"], "download")
            self.assertEqual(assets[f"media/{name}.ja.vtt"], "captions")

    def test_missing_or_incomplete_disassembly_evidence_is_rejected(self):
        from publish import publication_videos
        for change in ("missing", "short_decode", "decode_error", "failed_status"):
            with self.subTest(change=change):
                evidence = self.video_evidence()
                if change == "missing":
                    evidence.pop("disassembly")
                elif change == "short_decode":
                    evidence["disassembly"]["decoded_frames"] = 1
                elif change == "decode_error":
                    evidence["disassembly"]["decode_errors"] = 1
                else:
                    evidence["disassembly"]["status"] = "pending"
                with self.assertRaises(ValueError):
                    publication_videos(evidence)

    def test_blender_scene_timelines_match_each_video_independently(self):
        from publish import publication_videos
        from check_release import validate_video_timelines
        videos = publication_videos(self.video_evidence())
        blender = {"scenes": {
            "Assembly": {"frame_count": 1125, "fps": 30},
            "Disassembly": {"frame_count": 282, "fps": 24}}}
        validate_video_timelines(blender, videos)
        blender["scenes"]["Disassembly"]["frame_count"] = 1125
        with self.assertRaises(ValueError):
            validate_video_timelines(blender, videos)

    def test_fixture_evidence_and_verifier_are_publication_assets(self):
        from publish import drawing_tuples, publication_urls, publication_videos
        assets = dict(publication_urls(self.catalog, drawing_tuples(self.drawing_index()),
                                      publication_videos(self.video_evidence())))
        self.assertEqual(assets["validation/fixture.json"], "evidence")
        self.assertEqual(assets["scripts/verify_fixture.py"], "evidence_source")

    def test_fixture_evidence_requires_catalog_quantity_contacts_and_clearance(self):
        from check_release import validate_fixture_evidence
        rest = next(part for part in self.catalog["parts"] if part["id"] == "ASSEMBLY-REST")
        fixture = {"status": "pass", "revision": self.catalog["revision"],
                   "rest_quantity": rest["tool_quantity"], "frame_contacts_verified": True,
                   "rest_part_intersections": 0, "front_frame_plane_above_table_mm": 12,
                   "minimum_relief_table_clearance_mm": 5.6}
        validate_fixture_evidence(self.catalog, fixture)
        for field, value in (("rest_quantity", rest["tool_quantity"] + 1),
                             ("rest_part_intersections", 1), ("frame_contacts_verified", False),
                             ("minimum_relief_table_clearance_mm", 0), ("status", "pending")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_fixture_evidence(self.catalog, {**fixture, field: value})

    def test_corrected_print_poses_and_initial_tool_limit_are_published(self):
        from publish import public_metadata, publication_parts, publication_videos, publication_urls, drawing_tuples
        metadata = public_metadata(self.catalog, self.parameters, publication_videos(self.video_evidence()))
        self.assertEqual(metadata["manufacturing_revision"], self.catalog["manufacturing_revision"])
        self.assertEqual(metadata["release_tool"]["max_initial_push_mm"], 3.5)
        self.assertIs(metadata["release_tool"]["then_grip_rear_flange"], True)
        self.assertIs(metadata["release_tool"]["full_removal_with_tool"], False)
        parts = {part["id"]: part for part in publication_parts(self.catalog)}
        for name in ("T02", "CAPTURE-FRAME"):
            self.assertEqual(parts[name]["print_rotation_deg_xyz"], [180, 0, 0])
            self.assertEqual(parts[name]["print_orientation"], "front_face_on_bed")
        assets = dict(publication_urls(self.catalog, drawing_tuples(self.drawing_index()),
                                      publication_videos(self.video_evidence())))
        for name in ("print-pose", "print-pose-invariance"):
            self.assertEqual(assets[f"validation/{name}.json"], "evidence")
        self.assertEqual(assets["validation/drawing-previews.json"], "drawing_preview_evidence")
        for name in ("verify_print_pose", "verify_print_invariance", "render_drawing_previews"):
            self.assertEqual(assets[f"scripts/{name}.py"], "evidence_source")
        self.assertEqual(assets["validation/web.json"], "browser_evidence")

    def test_unflipped_masters_or_unsafe_tool_limits_are_rejected(self):
        from publish import public_metadata, publication_videos
        for change in ("T02", "CAPTURE-FRAME", "overstroke", "no_grip"):
            with self.subTest(change=change), self.assertRaises(ValueError):
                catalog, parameters = deepcopy(self.catalog), deepcopy(self.parameters)
                if change in ("T02", "CAPTURE-FRAME"):
                    next(part for part in catalog["parts"] if part["id"] == change)["print_rotation_deg_xyz"] = [0, 0, 0]
                elif change == "overstroke":
                    parameters["release_tool"]["max_initial_push_mm"] = 9.5
                else:
                    parameters["release_tool"]["then_grip_rear_flange"] = False
                public_metadata(catalog, parameters, publication_videos(self.video_evidence()))

    def test_table_marks_front_down_masters_as_already_oriented(self):
        from publish import table
        selected = [part for part in self.catalog["parts"] if part["id"] in ("T02", "CAPTURE-FRAME")]
        result = table(selected, self.catalog)
        self.assertEqual(result.count('data-print-orientation="front_face_on_bed"'), len(selected))
        self.assertEqual(result.count("前面を下 / 提供STLは方向設定済み"), len(selected))

    def test_manufacturing_guidance_rejects_back_down_and_full_pusher_removal(self):
        from check_release import assert_manufacturing_guidance
        for text in ("すべてのSTLは背面を下にして印刷します。",
                     "T02は背面を下にして印刷します。",
                     "EJECTORで最後まで押し出してください。",
                     "押し棒を使って全部取り出します。",
                     "Print all parts back-down.", "Use the pusher for full removal."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                assert_manufacturing_guidance(text, "test")
        with self.assertRaises(ValueError):
            assert_manufacturing_guidance("EJECTORで軽く押してフランジをつまみます。", "test", 3.5)
        assert_manufacturing_guidance(
            "EJECTORは初動のみ最大3.5 mm。その位置で工具を止め、後ろのフランジをつまんで残りを引き抜きます。"
            "押し棒を使って最後まで押し出しません。", "test", 3.5)
        assert_manufacturing_guidance(
            "Do not print all parts back-down. Never use the pusher for full removal. "
            "Initial push at most 3.5 mm; stop the tool, grip the flange and pull the remainder.", "test", 3.5)

    def test_blocked_browser_evidence_cannot_be_reported_as_passed(self):
        from check_release import browser_evidence_status
        report = {"status": "blocked_environment", "revision": self.catalog["manufacturing_revision"],
                  "browser_tested": False}
        result = browser_evidence_status(self.catalog, report)
        self.assertEqual(result["browser_status"], "blocked_environment")
        self.assertIs(result["browser_tested"], False)
        with self.assertRaises(ValueError):
            browser_evidence_status(self.catalog, {**report, "status": "pass"})

    def test_manufacturing_evidence_requires_bounded_full_tool_and_corrected_footprints(self):
        from check_release import validate_manufacturing_evidence
        revision, maximum = self.catalog["manufacturing_revision"], self.parameters["release_tool"]["max_initial_push_mm"]
        reports = {
            "print-pose": {"status": "pass", "revision": revision, "parts": {
                name: {"print_rotation_deg_xyz": [180, 0, 0], "bed_contact_area_mm2": 100,
                       "layer_samples": [{"area_outside_first_layer_footprint_mm2": 0}]}
                for name in ("T02", "CAPTURE-FRAME")}},
            "print-pose-invariance": {"status": "pass", "manufacturing_revision": revision,
                                     "instances": {row["id"]: {} for row in self.catalog["instances"]}},
            "assembly": {"status": "pass", "manufacturing_revision": revision,
                         "ejector_full_shape_validated_pushes_mm": [0, 1, maximum],
                         "reverse_order_removal_and_tool_access": [
                             {"instance": row["id"], "front_tool_target_xy": row["tool_target_xy"],
                              "tool_tip_rotation_deg": row["tool_tip_rotation_deg"],
                              "max_initial_tool_push_mm": maximum, "then_grip_rear_flange": True}
                             for row in self.catalog["instances"] if "tool_target_xy" in row],
                         "unsafe_overstroke_regression": {"push_mm": 9.5, "iris_intersection_mm3": .8112}},
        }
        validate_manufacturing_evidence(self.catalog, self.parameters, reports)
        for change in ("overstroke", "no_grip", "unsupported_layer", "missing_part"):
            with self.subTest(change=change), self.assertRaises(ValueError):
                changed = deepcopy(reports)
                if change == "overstroke":
                    changed["assembly"]["ejector_full_shape_validated_pushes_mm"].append(9.5)
                elif change == "no_grip":
                    changed["assembly"]["reverse_order_removal_and_tool_access"][0]["then_grip_rear_flange"] = False
                elif change == "unsupported_layer":
                    changed["print-pose"]["parts"]["T02"]["layer_samples"][0]["area_outside_first_layer_footprint_mm2"] = 1
                else:
                    changed["assembly"]["reverse_order_removal_and_tool_access"].pop()
                validate_manufacturing_evidence(self.catalog, self.parameters, changed)

    def test_public_metadata_keeps_user_decision_and_review_separate(self):
        from publish import public_metadata, publication_videos
        result = public_metadata(self.catalog, self.parameters, publication_videos(self.video_evidence()))
        self.assertIs(result["adhesive_required"], False)
        self.assertIs(result["all_parts_removable"], True)
        self.assertEqual(result["adhesive_design_status"], "rejected")
        self.assertEqual(result["independent_retention_review"], "pending_coordinated_review")
        for field in ("physical_fit_tested", "thread_durability_tested", "tipping_tested", "safety_certified"):
            self.assertIs(result[field], False)

    def test_release_rejects_stale_counts_and_tool_quantities(self):
        from publish import public_metadata, publication_parts, publication_videos
        from check_release import validate_manifest_metadata
        video = publication_videos(self.video_evidence())
        manifest = {**public_metadata(self.catalog, self.parameters, video),
                    "parts": publication_parts(self.catalog)}
        validate_manifest_metadata(self.catalog, self.parameters, manifest, video)
        changed = deepcopy(manifest)
        changed["assembly_instances"] -= 1
        with self.assertRaises(ValueError):
            validate_manifest_metadata(self.catalog, self.parameters, changed, video)
        changed = deepcopy(manifest)
        next(part for part in changed["parts"] if part["category"] == "tool")["print_quantity"] += 1
        with self.assertRaises(ValueError):
            validate_manifest_metadata(self.catalog, self.parameters, changed, video)

    def test_changed_message_pitch_or_removability_is_rejected(self):
        from publish import public_metadata, publication_videos
        for field, value in (("message", ["changed"]), ("nominal_pitch", 10),
                             ("adhesive_required", True), ("all_parts_removable", False)):
            with self.subTest(field=field):
                parameters = deepcopy(self.parameters)
                parameters[field] = value
                with self.assertRaises(ValueError):
                    public_metadata(self.catalog, parameters, publication_videos(self.video_evidence()))

    def test_nonlocal_asset_urls_are_rejected(self):
        from publish import project_asset_path
        for url in ("https://example.invalid/file.stl", "//example.invalid/file.stl",
                    "/absolute/file.stl", "../file.stl", "%2e%2e/file.stl",
                    "meshes/../../file.stl", "meshes\\file.stl", "file.stl?raw=1", "file.stl#part"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                project_asset_path(url)
        self.assertEqual(project_asset_path("catalog.json"), ROOT / "catalog.json")

    def test_asset_hash_mismatch_is_rejected(self):
        from publish import asset
        from check_release import verify_asset
        item = asset("catalog.json", "canonical_catalog")
        self.assertEqual(verify_asset(item), (ROOT / "catalog.json").stat().st_size)
        item["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_asset(item)

    def test_active_adhesive_instructions_are_rejected(self):
        from check_release import assert_no_active_adhesive
        for text in ("色パーツの保持には少量の接着が必要です。",
                     "製作リリース保留。この方式のユーザー承認は未確認です。",
                     "背板を寝かせて色部品を接着し、完全硬化後に台座へ戻します。",
                     "PLAへの適合が明記された模型用接着剤を使います。",
                     "両面テープで固定してください。", "熱かしめしてください。", "溶着します。",
                     "Glue the inserts.", "Tape the parts.", "Heat-stake the pins.",
                     "Weld the cover.", "Manufacturing release awaits adhesive approval."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                assert_no_active_adhesive(text, "test")

    def test_historical_rejection_and_no_adhesive_notice_are_allowed(self):
        from check_release import assert_no_active_adhesive
        assert_no_active_adhesive(
            "T1の接着方式は却下。046a48eは履歴比較専用です。"
            "接着剤・テープ・熱かしめ・溶着は使いません。"
            "No adhesive is used; the adhesive design was rejected.", "test")

    def test_scoped_human_facing_sources_have_no_active_adhesive_instructions(self):
        from check_release import assert_no_active_adhesive, assert_manufacturing_guidance
        from publish import GUIDE_NAMES
        for name in ["README.md", "templates/index.html"] + [f"docs/{name}.md" for name in GUIDE_NAMES]:
            with self.subTest(name=name):
                text = (ROOT / name).read_text()
                assert_no_active_adhesive(text, name)
                assert_manufacturing_guidance(text, name)
        assert_manufacturing_guidance((ROOT / "docs/howto.ja.md").read_text(), "howto",
                                     self.parameters["release_tool"]["max_initial_push_mm"])

    def test_front_page_renders_every_master_and_dynamic_video_metadata(self):
        from publish import drawing_tuples, render_page, publication_videos
        result = render_page(self.catalog, publication_videos(self.video_evidence()),
                             drawing_tuples(self.drawing_index()), "", parameters=self.parameters)
        self.assertNotIn("{{", result)
        self.assertEqual(result.count("<tr data-part="), len(self.catalog["parts"]))
        self.assertEqual(result.count("<video "), 2)
        self.assertIn('width="960" height="720"', result)
        self.assertIn('width="640" height="480"', result)
        self.assertIn("37.5秒", result)
        self.assertIn("11.75秒", result)
        for name in ("assembly", "disassembly"):
            self.assertIn(f'data-video="{name}"', result)
            self.assertIn(f'src="media/{name}.mp4"', result)
            self.assertIn(f'src="media/{name}.ja.vtt"', result)
        from check_release import assert_manufacturing_guidance
        assert_manufacturing_guidance(result, "index", self.parameters["release_tool"]["max_initial_push_mm"])

    def test_pack_note_reports_tools_and_glue_free_status(self):
        from publish import print_pack_readme
        from check_release import assert_no_active_adhesive, assert_manufacturing_guidance
        result = print_pack_readme(self.catalog, self.parameters)
        self.assertIn("/ T2 /", result)
        for part in self.catalog["parts"]:
            if part["category"] == "tool":
                self.assertIn(f'{part["id"]} ×{part["tool_quantity"]}', result)
        assert_no_active_adhesive(result, "PRINT-README.txt")
        assert_manufacturing_guidance(result, "PRINT-README.txt", self.parameters["release_tool"]["max_initial_push_mm"])


def main():
    from playwright.sync_api import sync_playwright
    from publish import (GUIDE_NAMES, VIDEO_ASSETS, catalog_counts, load_drawings,
                         print_quantity, publication_videos)
    from check_release import assert_no_active_adhesive, assert_manufacturing_guidance, validate_manifest_metadata

    if not Path(CHROME).is_file():
        raise FileNotFoundError("Set CHROME to an existing browser; this test does not download a browser.")
    drawings = load_drawings()
    drawings_only = "--drawings-only" in sys.argv
    if not drawings_only:
        catalog = json.loads((ROOT / "catalog.json").read_text())
        parameters = json.loads((ROOT / "parameters.json").read_text())
        manifest = json.loads((ROOT / "manifest.json").read_text())
        expected_videos = publication_videos(json.loads((ROOT / "validation/video.json").read_text()))
        validate_manifest_metadata(catalog, parameters, manifest, expected_videos)
        counts = catalog_counts(catalog)
        colors = {part["color"] for part in catalog["parts"] if part["category"] == "assembly"}
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    previews = ROOT / "validation/previews"
    if not drawings_only:
        previews.mkdir(exist_ok=True)
    errors, failures, responses = [], [], []
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(ROOT / "validation/browser-profile"), executable_path=CHROME, headless=True,
                viewport={"width": 1440, "height": 1000},
                args=["--disable-background-networking", "--disable-sync", "--no-first-run", "--disable-gpu"])
            try:
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda request: failures.append(
                    {"url": request.url.replace(base, ""), "reason": request.failure}))
                page.on("response", lambda response: responses.append((response.status, response.url.replace(base, ""))))
                if drawings_only:
                    folder = ROOT / "media/drawings"
                    folder.mkdir(exist_ok=True)
                    for filename, _, _ in drawings:
                        page.goto(base + "/drawings/" + filename)
                        page.wait_for_load_state("networkidle")
                        page.locator("svg").evaluate("(svg) => {svg.style.width='1260px';svg.style.height='891px';}")
                        page.locator("svg").screenshot(path=str(folder / (Path(filename).stem + ".png")),
                                                      timeout=120000)
                else:
                    page.goto(base + "/index.html")
                    page.wait_for_load_state("networkidle")
                    assert page.get_by_role("heading", name="@YOUR-USERNAME", exact=True).count() == 1
                    assert page.locator("tr[data-part]").count() == counts["print_master_count"]
                    assert page.locator(".color-batch").count() == len(colors)
                    assert_no_active_adhesive(page.locator("body").inner_text(), "index.html")
                    assert_manufacturing_guidance(page.locator("body").inner_text(), "index.html",
                                                  parameters["release_tool"]["max_initial_push_mm"])
                    notice = page.locator(".notice").inner_text()
                    assert all(word in notice for word in ("無接着", "ユーザー", "未検証"))
                    for part in catalog["parts"]:
                        row = page.locator(f'tr[data-part="{part["id"]}"]')
                        assert row.count() == 1
                        assert row.get_attribute("data-category") == part["category"]
                        assert row.get_attribute("data-print-quantity") == str(print_quantity(part))
                        assert row.get_attribute("data-print-orientation") == part.get("print_orientation", "flat_base_as_exported")
                        assert set(row.locator("a[download]").evaluate_all(
                            "(links) => links.map(a => a.getAttribute('href'))")) == {part["mesh"], part["step"]}
                    assert page.locator("video[data-video]").count() == len(VIDEO_ASSETS)
                    page.wait_for_function(
                        "Array.from(document.querySelectorAll('video[data-video]')).every(v => Number.isFinite(v.duration))")
                    observed_videos = {}
                    for name, spec in VIDEO_ASSETS.items():
                        player = page.locator(f'video[data-video="{name}"]')
                        assert player.count() == 1
                        assert player.locator("source").get_attribute("src") == spec["url"]
                        assert player.locator('track[kind="captions"]').get_attribute("src") == spec["captions"]
                        assert page.locator(f'a[href="{spec["captions"]}"][download]').count() == 1
                        observed = player.evaluate(
                            "(v) => ({duration:v.duration,width:v.videoWidth,height:v.videoHeight})")
                        expected = expected_videos[name]
                        assert abs(observed["duration"] - expected["duration_seconds"]) < max(.05, 1 / expected["fps"])
                        assert (observed["width"], observed["height"]) == (expected["width"], expected["height"])
                        observed_videos[name] = observed
                    page.locator("details").evaluate_all("(details) => details.forEach(d => d.open = true)")
                    assert page.locator(".drawing-link").count() == len(drawings)
                    for filename, _, _ in drawings:
                        link = page.locator(f'.drawing-link[href="drawings/{filename}"]')
                        assert link.count() == 1
                        assert link.locator("img").get_attribute("src") == f"media/drawings/{Path(filename).stem}.png"
                    page.locator(".drawing-link img").evaluate_all("(imgs) => imgs.forEach(img => img.loading='eager')")
                    page.wait_for_function(
                        "Array.from(document.querySelectorAll('.drawing-link img')).every(img => img.complete && img.naturalWidth > 0)")
                    page.screenshot(path=str(previews / "site-desktop.png"), full_page=True, timeout=120000)
                    for width in (375, 768):
                        page.set_viewport_size({"width": width, "height": 900})
                        page.wait_for_load_state("networkidle")
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), f"Overflow at {width}px"
                        if width == 375:
                            page.screenshot(path=str(previews / "site-mobile.png"), full_page=True, timeout=120000)
                    page.set_viewport_size({"width": 375, "height": 900})
                    for name in GUIDE_NAMES:
                        page.goto(base + f"/docs/{name}.html")
                        page.wait_for_load_state("networkidle")
                        assert page.get_by_role("heading", level=1).count() == 1
                        assert_no_active_adhesive(page.locator("body").inner_text(), name)
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                    page.set_viewport_size({"width": 1600, "height": 1140})
                    for filename in ("three-views.svg", "exploded.svg"):
                        page.goto(base + "/drawings/" + filename)
                        page.wait_for_load_state("networkidle")
                        page.locator("svg").evaluate("(svg) => {svg.style.width='1260px';svg.style.height='891px';}")
                        page.locator("svg").screenshot(
                            path=str(previews / f"{Path(filename).stem}-browser.png"), timeout=120000)
            finally:
                context.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    bad = [(status, url) for status, url in responses if status >= 400 and not url.endswith("/favicon.ico")]
    video_paths = {"/" + spec["url"] for spec in VIDEO_ASSETS.values()}
    unexpected = [item for item in failures
                  if not (item["url"] in video_paths and item["reason"] == "net::ERR_ABORTED")]
    if errors or unexpected or bad:
        raise AssertionError({"page_errors": errors, "failed_requests": unexpected, "http_errors": bad})
    if drawings_only:
        print("DRAWING_PREVIEWS_PASS", len(drawings))
        return
    report = {"status": "pass", "revision": catalog["revision"],
              "manufacturing_revision": catalog["manufacturing_revision"], "browser_tested": True,
              "engine": "Existing Chrome / Python Playwright",
              "viewports_px": [1440, 768, 375], "print_part_rows": counts["print_master_count"],
              "color_groups": len(colors), "drawing_sheets": len(drawings), **counts,
              "horizontal_overflow": False, "page_errors": [], "http_errors": [],
              "video_metadata": observed_videos["assembly"],
              "expected_video_metadata": expected_videos["assembly"],
              "videos_metadata": observed_videos, "expected_videos_metadata": expected_videos,
              "expected_media_preload_cancellations": len(failures)-len(unexpected),
              "generated_guides_and_svg_views_opened": True,
              "adhesive_required": False, "all_parts_removable": True, "physical_fit_tested": False}
    (ROOT / "validation/web.json").write_text(json.dumps(report, indent=2) + "\n")
    print("BROWSER_CHECK_PASS")


if __name__ == "__main__":
    if "--source-only" in sys.argv:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    else:
        main()
