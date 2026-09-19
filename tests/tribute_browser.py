"""Browser checks for the actual repository-prefix T2 mirror, only when released."""

import json

from playwright.sync_api import expect


def verify_tribute(browser, root, base, screenshots):
    manifest_file = root / "site/tribute/manifest.json"
    if not manifest_file.exists():
        return
    manifest = json.loads(manifest_file.read_text())
    assert manifest["adhesive_required"] is False
    assert manifest["all_parts_removable"] is True
    assert manifest["independent_retention_review"] == "accepted_digital_only"
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors, failures, videos = [], [], {}
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(response.status) if response.status >= 400 else None)
    try:
        print("TRIBUTE_BEGIN", flush=True)
        page.goto(base + "tribute/", wait_until="networkidle", timeout=120000)
        expect(page.get_by_role("heading", name="@YOUR-USERNAME", exact=True)).to_have_count(1)
        expect(page.locator("tr[data-part]")).to_have_count(59)
        expect(page.locator(".drawing-link")).to_have_count(10)
        notice = page.locator(".notice").inner_text()
        assert "無接着" in notice and "未検証" in notice
        for part in ("T02", "CAPTURE-FRAME"):
            expect(page.locator(f'tr[data-part="{part}"]')).to_have_attribute("data-print-orientation", "front_face_on_bed")
        for name in ("assembly", "disassembly"):
            print("TRIBUTE_VIDEO", name, flush=True)
            player = page.locator(f'video[data-video="{name}"]')
            player.scroll_into_view_if_needed()
            player.click()
            player.evaluate("""video => {
              video.muted = true;
              video.play().catch(error => {video.dataset.playError = error.message;});
            }""")
            page.wait_for_function("""name => {
              const video = document.querySelector(`video[data-video="${name}"]`);
              return video.currentTime > .1 || video.error || video.dataset.playError;
            }""", arg=name, timeout=30000)
            state = player.evaluate("""video => ({
              time: video.currentTime, duration: video.duration,
              width: video.videoWidth, height: video.videoHeight,
              error: video.error?.message || video.dataset.playError || null
            })""")
            assert state["time"] > .1 and state["error"] is None, state
            assert abs(state["duration"] - 24) < .05
            assert [state["width"], state["height"]] == [640, 640]
            player.evaluate("video => video.pause()")
            videos[name] = state
        for width in (1440, 768, 375):
            page.set_viewport_size({"width": width, "height": 950})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.screenshot(path=str(screenshots / "tribute-mobile.png"), full_page=True, timeout=120000)
        for guide in ("howto.ja", "validation.ja", "reproduce.ja", "t2-change-review.ja"):
            page.goto(base + f"tribute/docs/{guide}.html", wait_until="networkidle")
            expect(page.get_by_role("heading", level=1)).to_have_count(1)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert not errors and not failures, (errors, failures)
        report = {
            "status": "PASS_REAL_BROWSER", "revision": "T2-R1", "browser_tested": True,
            "browser": browser.version, "repository_prefix": "/copilot-brick-display/tribute/",
            "part_rows": 59, "drawing_sheets": 10, "viewports": [1440, 768, 375],
            "actual_video_playback": videos, "no_horizontal_overflow": True,
            "page_errors": errors, "http_errors": failures,
            "adhesive_required": False, "all_parts_removable": True, "physical_fit_tested": False,
        }
        (root / "validation/tribute-web-ci.json").write_text(json.dumps(report, indent=2) + "\n")
        print("TRIBUTE_BROWSER_PASS", flush=True)
    finally:
        context.close()
