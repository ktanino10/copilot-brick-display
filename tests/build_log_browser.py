"""Inspect the public photo journal under the Pages prefix at desktop and exactly375 CSS pixels."""

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
TITLE = "制作記録 — Bの台座と前面モジュール"


def verify_build_log(page, base, output):
    output.mkdir(parents=True, exist_ok=True)
    page.goto(base.rstrip("/") + "/build-log.html?log=2026-09-23", wait_until="networkidle", timeout=90000)
    expect(page.get_by_role("heading", name=TITLE, exact=True)).to_have_count(1)
    body = page.locator(".document")
    for text in ("個人向けB版", "公開画像は識別情報を伏せています", "上が旧版・下が新版などとは断定しません",
                 "全150部品", "CC0化や第三者への再配布許諾を意味しません"):
        expect(body).to_contain_text(text)
    images = page.locator('.document img[src*="media/build-log/2026-09-23/"]')
    expect(images).to_have_count(9)
    expect(page.locator('.document a[href*="manifest.json"]')).to_have_count(1)
    for width in (1440, 375):
        page.set_viewport_size({"width": width, "height": 1000})
        for image in images.all():
            image.scroll_into_view_if_needed()
            expect(image).to_be_visible()
            assert image.evaluate("image => image.complete && image.naturalWidth > 0")
            assert image.get_attribute("alt")
            bounds = image.bounding_box()
            assert bounds and bounds["width"] > 0 and bounds["width"] <= width
            assert image.evaluate("image => Math.abs(image.clientWidth / image.clientHeight - image.naturalWidth / image.naturalHeight) < .02")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert body.locator("canvas, svg").count() == 0
        page.locator("h1").scroll_into_view_if_needed()
        page.screenshot(path=str(output / f"build-log-{width}.png"), full_page=True)
    image_link = page.locator('.document a[href*="/front-modules-installed.jpg"]').first
    image_link.click()
    assert "/front-modules-installed.jpg" in page.url
    assert page.locator("img").evaluate("image => image.complete && image.naturalWidth === 1710")
    page.go_back(wait_until="networkidle")
    return {
        "status": "PASS_REAL_BUILD_LOG_BROWSER", "report_date": "2026-09-23",
        "widths_px": [1440, 375], "photos": 9, "actual_raster_photos_loaded": True,
        "full_size_link_uses_same_redacted_file": True, "separate_captions_and_limits_visible": True,
        "original_photos_accessed": False, "physical_qualification_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/build-log-browser")
    args = parser.parse_args()
    errors, bad = [], []
    with sync_playwright() as p:
        launch = {"headless": True}
        if os.environ.get("BROWSER_PATH"):
            launch["executable_path"] = os.environ["BROWSER_PATH"]
        with p.chromium.launch(**launch) as browser:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: bad.append([response.status, response.url]) if response.status >= 400 else None)
            report = verify_build_log(page, args.base, args.output)
            assert not errors and not bad, (errors, bad)
            report["browser"] = browser.version
            (args.output / "browser.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
