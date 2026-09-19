"""Inspect the static site with an isolated, existing Chrome and Python Playwright."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def main():
    if not Path(CHROME).is_file():
        raise FileNotFoundError("Set CHROME to an existing browser; this test does not download a browser.")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    previews = ROOT / "validation/previews"
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
                if "--drawings-only" in sys.argv:
                    from publish import DRAWINGS
                    folder = ROOT / "media/drawings"
                    folder.mkdir(exist_ok=True)
                    for filename, _, _ in DRAWINGS:
                        page.goto(base + "/drawings/" + filename)
                        page.wait_for_load_state("networkidle")
                        page.locator("svg").evaluate("(svg) => {svg.style.width='1260px';svg.style.height='891px';}")
                        page.locator("svg").screenshot(path=str(folder / (Path(filename).stem + ".png")),
                                                      timeout=120000)
                    print("DRAWING_PREVIEWS_PASS", len(DRAWINGS))
                    return
                page.goto(base + "/index.html")
                page.wait_for_load_state("networkidle")
                assert page.get_by_role("heading", name="@YOUR-USERNAME", exact=True).count() == 1
                assert page.locator("tr[data-part]").count() == 32
                assert page.locator(".color-batch").count() == 7
                page.wait_for_function("Number.isFinite(document.querySelector('video').duration)")
                video = page.locator("video").evaluate("(v) => ({duration:v.duration,width:v.videoWidth,height:v.videoHeight})")
                assert abs(video["duration"]-21) < .05 and (video["width"], video["height"]) == (640, 640)
                for summary in page.locator(".color-batch summary").all():
                    summary.click()
                assert page.locator('tr[data-part="MSG-CARD"] a[download]').count() == 2
                page.locator(".drawing-link img").evaluate_all("(imgs) => imgs.forEach(img => img.loading='eager')")
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(previews / "site-desktop.png"), full_page=True, timeout=120000)
                for width in (375, 768):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.wait_for_load_state("networkidle")
                    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                    assert not overflow, f"Horizontal page overflow at {width}px"
                    if width == 375:
                        page.screenshot(path=str(previews / "site-mobile.png"), full_page=True, timeout=120000)
                page.goto(base + "/docs/howto.ja.html")
                page.wait_for_load_state("networkidle")
                assert page.get_by_role("heading", name="作り方：@YOUR-USERNAME キャラクター記念楯", exact=True).count() == 1
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                page.set_viewport_size({"width": 1600, "height": 1140})
                page.goto(base + "/drawings/three-views.svg")
                page.wait_for_load_state("networkidle")
                page.locator("svg").evaluate("(svg) => {svg.style.width='1260px';svg.style.height='891px';}")
                page.locator("svg").screenshot(path=str(previews / "three-views-browser.png"), timeout=120000)
                page.goto(base + "/drawings/exploded.svg")
                page.wait_for_load_state("networkidle")
                page.locator("svg").evaluate("(svg) => {svg.style.width='1260px';svg.style.height='891px';}")
                page.locator("svg").screenshot(path=str(previews / "exploded-browser.png"), timeout=120000)
            finally:
                context.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    bad = [(status, url) for status, url in responses if status >= 400 and not url.endswith("/favicon.ico")]
    unexpected = [item for item in failures
                  if not (item["url"] == "/media/assembly.mp4" and item["reason"] == "net::ERR_ABORTED")]
    if errors or unexpected or bad:
        raise AssertionError({"page_errors": errors, "failed_requests": unexpected, "http_errors": bad})
    report = {"status": "pass", "engine": "Existing Chrome / Python Playwright",
              "viewports_px": [1440, 768, 375], "print_part_rows": 32, "color_groups": 7,
              "horizontal_overflow": False, "page_errors": [], "http_errors": [],
              "video_metadata": video,
              "expected_media_preload_cancellations": len(failures)-len(unexpected),
              "generated_guides_and_svg_views_opened": True}
    (ROOT / "validation/web.json").write_text(json.dumps(report, indent=2) + "\n")
    print("BROWSER_CHECK_PASS")


if __name__ == "__main__":
    main()
