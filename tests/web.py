"""Real browser checks under the GitHub Pages repository prefix."""

import json
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright, expect
from tribute_browser import verify_tribute
from exploded_browser import verify_exploded

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8766/copilot-brick-display/")
OUT = ROOT / "build/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
catalog = json.loads((ROOT / "design/catalog.json").read_text())
errors, failures, explosion_records = [], [], []


def check_no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def check_colors(path):
    image = Image.open(path).convert("RGB")
    colors = {"cyan": 0, "magenta": 0, "green": 0}
    for r, g, b in image.getdata():
        if g > r * 1.2 and b > r * 1.2 and g > 90:
            colors["cyan"] += 1
        if r > g * 1.3 and b > g * 1.3 and r > 90:
            colors["magenta"] += 1
        if g > r * 1.2 and g > b * 1.1 and g > 100:
            colors["green"] += 1
    assert colors["cyan"] > 100 and colors["magenta"] > 100 and colors["green"] > 20, colors
    return colors


with sync_playwright() as playwright:
    print("BROWSER_START", flush=True)
    launch = {"headless": True}
    if os.environ.get("BROWSER_PATH"):
        launch["executable_path"] = os.environ["BROWSER_PATH"]
    browser = playwright.chromium.launch(**launch)
    context = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    page.goto(BASE, wait_until="networkidle", timeout=180000)
    print("BROWSER_PAGE_LOADED", flush=True)
    try:
        expect(page.locator("#viewport")).to_have_class("viewport viewer-ready", timeout=180000)
    except AssertionError:
        print("Viewer diagnostic:", page.locator("#viewer-error").text_content(), errors, failures)
        page.screenshot(path=str(OUT / "viewer-failure.png"), full_page=True)
        raise
    expect(page.locator("#viewport")).to_have_attribute("data-model", "B")
    expect(page.locator("#viewport")).to_have_attribute("data-instances", str(catalog["models"][1]["part_count"]))
    expect(page.locator("#published-revision")).to_have_text(catalog["revision"])
    assert "@YOUR-USERNAME" not in page.locator("body").inner_text()
    page.locator('[data-view="front"]').click()
    page.wait_for_timeout(600)
    page.locator("#viewport").screenshot(path=str(OUT / "B-front.png"))
    colors = check_colors(OUT / "B-front.png")
    page.screenshot(path=str(OUT / "desktop.png"), full_page=True)
    check_no_overflow(page)
    for model in catalog["models"]:
        print("MODEL_BEGIN", model["id"], flush=True)
        page.locator(f'button[data-model="{model["id"]}"]').click()
        expect(page.locator("#viewport")).to_have_attribute("data-model", model["id"], timeout=180000)
        expect(page.locator("#viewport")).to_have_attribute("data-instances", str(model["part_count"]))
        expect(page.locator("#part-count")).to_contain_text(str(model["part_count"]))
        explosion_records.append(verify_exploded(page, model, OUT))
        page.locator("#part-select").select_option(model["placements"][0]["id"])
        expect(page.locator("#part-details")).to_contain_text(model["placements"][0]["part"])
        expect(page.locator("#part-drawing")).to_be_visible()
        page.wait_for_function("document.querySelector('#part-drawing').complete && document.querySelector('#part-drawing').naturalWidth > 0")
        for direction in ["front", "side", "top", "iso"]:
            page.locator(f'[data-view="{direction}"]').click()
            expect(page.locator(f'[data-view="{direction}"]')).to_have_attribute("aria-pressed", "true")
        page.locator("#bounds").check()
        page.locator("#explode").fill("100")
        expect(page.locator("#explode-value")).to_have_text("100%")
        page.locator("#explode").fill("0")
        page.locator("#assembly").fill("0")
        expect(page.locator("#assembly-value")).to_have_text(f"0 / {len(model['steps'])}")
        page.locator("#play").click()
        page.wait_for_function("Number(document.querySelector('#assembly').value) >= 2")
        page.locator("#play").click()
        page.locator("#assembly").fill(str(len(model["steps"])))
        expect(page.locator("#assembly-value")).to_have_text("完成")
        print("VIDEO_BEGIN", model["id"], flush=True)
        page.locator("#assembly-video").scroll_into_view_if_needed()
        page.locator("#assembly-video").click()
        print("VIDEO_STATE", page.locator("#assembly-video").evaluate("""video => ({
          ready: video.readyState, network: video.networkState, paused: video.paused,
          duration: Number.isFinite(video.duration) ? video.duration : null,
          h264: video.canPlayType('video/mp4; codecs="avc1.640028"'),
          source: video.currentSrc, error: video.error?.message || null
        })"""), flush=True)
        page.locator("#assembly-video").evaluate("""(video) => {
          video.muted = true;
          delete video.dataset.playError;
          video.play().catch(error => { video.dataset.playError = error.message; });
        }""")
        page.wait_for_function("""() => {
          const video = document.querySelector('#assembly-video');
          return video.currentTime > 0.1 || video.error || video.dataset.playError;
        }""", timeout=30000)
        video_state = page.locator("#assembly-video").evaluate("""video => ({
          time: video.currentTime, error: video.error?.message || video.dataset.playError || null
        })""")
        assert video_state["time"] > .1 and not video_state["error"], video_state
        page.locator("#assembly-video").evaluate("(video) => video.pause()")
        check_no_overflow(page)
        print("MODEL_PASS", model["id"], flush=True)
    page.screenshot(path=str(OUT / "C-inspector.png"), full_page=True)
    page.goto(BASE + "guide.html?model=C", wait_until="networkidle")
    expect(page.locator("#guide-model")).to_have_value("C")
    c_steps = len(catalog["models"][2]["steps"])
    expect(page.locator("#guide-step option")).to_have_count(c_steps)
    page.locator("#guide-step").select_option(str(c_steps))
    page.wait_for_function("document.querySelector('#guide-drawing').complete && document.querySelector('#guide-drawing').naturalWidth > 0")
    expect(page.locator("#guide-drawing")).to_have_attribute("src", f"drawings/C/step-{c_steps:02}.svg?rev={catalog['revision']}")
    check_no_overflow(page)
    page.goto(BASE + "trial.html", wait_until="networkidle")
    expect(page.get_by_role("heading", name="7個だけ、段階を分けて試す", exact=True)).to_have_count(1)
    expect(page.locator("body")).to_contain_text("7個の確認は、5段完成品")
    expect(page.locator("body")).to_contain_text("全数印刷を止めます")
    expect(page.locator('a[href*="downloads/trial-subset.zip"]')).to_have_count(1)
    for width in (1440, 375):
        page.set_viewport_size({"width": width, "height": 950})
        check_no_overflow(page)
    context.close()
    print("MOBILE_BEGIN", flush=True)
    mobile = browser.new_context(viewport={"width": 375, "height": 844}, device_scale_factor=1, reduced_motion="reduce")
    mobile_page = mobile.new_page()
    mobile_page.on("pageerror", lambda error: errors.append(str(error)))
    mobile_page.goto(BASE + "?model=A", wait_until="networkidle", timeout=180000)
    try:
        expect(mobile_page.locator("#viewport")).to_have_attribute("data-model", "A", timeout=180000)
    except AssertionError:
        print("Mobile viewer diagnostic:", mobile_page.locator("#viewer-error").text_content(), errors, failures)
        mobile_page.screenshot(path=str(OUT / "mobile-viewer-failure.png"), full_page=True)
        raise
    mobile_page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
    check_no_overflow(mobile_page)
    for model in catalog["models"]:
        mobile_page.locator(f'button[data-model="{model["id"]}"]').click()
        expect(mobile_page.locator("#viewport")).to_have_attribute("data-model", model["id"], timeout=180000)
        explosion_records.append(verify_exploded(mobile_page, model, OUT, mobile=True))
    mobile.close()
    verify_tribute(browser, ROOT, BASE, OUT)
    assert not errors, errors
    assert not failures, failures
    report = {
        "status": "PASS_REAL_BROWSER", "browser": browser.version,
        "repository_prefix": "/copilot-brick-display/",
        "models": ["A", "B", "C"], "native_webgl_geometry_visible": colors,
        "revision": catalog["revision"], "vertical_explosion": explosion_records,
        "checks": ["model changes", "four camera views", "part selection + CAD sheet", "bounds",
                   "explosion", "stage seek + play/pause", "all three MP4 decoded in browser",
                   "Japanese guide stage deep link", "desktop/mobile overflow", "reduced motion", "zero page errors/404s"],
        "staged_trial_guidance": {"guidance_revision": "trial-2026-09-19",
                                  "geometry_revision": catalog["revision"], "page_widths_px": [1440, 375],
                                  "physical_trial_performed": False},
        "screenshots": ["desktop.png", "B-front.png", "C-inspector.png", "mobile.png"],
    }
    (ROOT / "validation/web.json").write_text(json.dumps(report, indent=2) + "\n")
    browser.close()
    print(json.dumps(report, indent=2))
