"""Exercise the real print-to-place guide through normal controls, including offline file URLs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def snapshot(page):
    return page.evaluate("BrickAssemblyGuide.state()")


def ready(page, url):
    page.goto(url, wait_until="load", timeout=180000)
    expect(page.locator("#guide-app")).to_have_attribute("data-ready", "true", timeout=180000)
    expect(page.locator("#guide-error")).to_be_hidden()


def b_controls(page, output):
    initial = snapshot(page)
    assert initial["cursor"] == 0 and initial["completedIds"] == []
    assert initial["selectedSlot"] == "B-black-02.3mf#3" and initial["activeId"] is None
    assert initial["step"] == 0 and initial["assemblyPoses"] == []
    expect(page.locator("#first-file")).to_contain_text("B-black-02.3mf")
    expect(page.locator("#base-files")).to_contain_text("B-black-04.3mf")
    page.locator("#start-first").click()
    assert snapshot(page)["activeId"] == "B-001"
    expect(page.locator("#capture-caption")).to_contain_text("BASE3-24x10-B-562406")
    page.locator("#motion-progress").focus()
    page.keyboard.press("End")
    seated = snapshot(page)
    assert seated["cursor"] == 0 and seated["completedIds"] == []
    assert seated["seatedCount"] == 1 and seated["seatedIds"] == ["B-001"] and seated["activeSeated"]
    expect(page.locator("#cursor-value")).to_have_text("1 / 150 個配置済み")
    expect(page.locator("#action-title")).to_have_text("工程1 · B-001 の配置完了")
    page.locator("#motion-progress").fill("0")
    no_overflow(page)
    page.locator("#plate-select").select_option("B-black-01.3mf")
    assert snapshot(page)["mode"] == "lookup"
    assert snapshot(page)["candidateIds"] == ["B-006", "B-015"]
    page.locator("#plate-isolate").check()
    page.locator('[data-scene="plate"] [data-view="bottom"]').click()
    expect(page.locator('[data-scene="plate"] [data-view="bottom"]')).to_have_attribute("aria-pressed", "true")
    page.locator("#plate-viewport").screenshot(path=str(output / "B-groove-underside.png"))
    page.locator("#plate-isolate").uncheck()
    page.locator("#plate-select").select_option("B-black-03.3mf")
    data = page.evaluate("BrickAssemblyGuide.mapping()")
    slot = next(s for p in data["plates"] if p["file"] == "B-black-03.3mf" for s in p["slots"]
                if s["part"] == "BASE3-06x10-T-838259")
    page.locator(f'#slot-list [data-slot="{slot["id"]}"]').click()
    assert len(snapshot(page)["candidateIds"]) == 6 and len(snapshot(page)["sourceSlots"]) == 6
    expect(page.locator("#source-list")).to_contain_text("B-black-04.3mf")
    row = page.locator(".target-row").filter(has=page.get_by_role("button", name="B-016 · 工程5", exact=True))
    row.get_by_role("button", name="ここから組む", exact=True).click()
    assert snapshot(page)["cursor"] == 15 and snapshot(page)["selectedPlate"] == "B-black-04.3mf"
    page.locator("#restart").click()
    assert snapshot(page)["cursor"] == 0 and snapshot(page)["empty"]
    page.locator("#start-first").click()
    page.locator("#next").click()
    assert snapshot(page)["completedIds"] == ["B-001"]
    page.locator("#previous").click()
    assert snapshot(page)["cursor"] == 0
    page.locator("#play").click()
    expect(page.locator("#assembly-cursor")).to_have_value("1", timeout=15000)
    page.locator("#play").click()
    stopped = snapshot(page)
    page.wait_for_timeout(180)
    assert not snapshot(page)["playing"] and snapshot(page)["cursor"] == stopped["cursor"]
    page.locator("#step-select").select_option("6")
    assert snapshot(page)["cursor"] == 19 and snapshot(page)["activeId"] == "B-020"
    page.locator("#motion-progress").fill("100")
    pose = next(p for p in snapshot(page)["assemblyPoses"] if p["id"] == "B-020")
    assert pose["rotation"] == [90, 0, 0] and pose["position"] == [4, 3.3, 4]
    assert snapshot(page)["seatedCount"] == 20 and snapshot(page)["activeSeated"]
    page.locator("#step-select").select_option("7")
    assert snapshot(page)["cursor"] == 21 and snapshot(page)["activeId"] == "B-022"
    page.locator("#speed").select_option("700")
    page.locator("#replay-step").click()
    expect(page.locator("#assembly-cursor")).to_have_value("24", timeout=15000)
    expect(page.locator("#play")).to_have_attribute("aria-pressed", "false")
    assert snapshot(page)["seatedCount"] == 24
    for scene in ("plate", "assembly"):
        for direction in ("front", "side", "top", "back", "bottom", "iso"):
            page.locator(f'[data-scene="{scene}"] [data-view="{direction}"]').click()
            expect(page.locator(f'[data-scene="{scene}"] [data-view="{direction}"]')).to_have_attribute("aria-pressed", "true")
    page.locator("#ghost").uncheck()
    page.locator("#assembly-cursor").fill("150")
    complete = snapshot(page)
    assert len(complete["completedIds"]) == 150 and complete["activeId"] is None
    assert complete["seatedCount"] == 150 and not complete["activeSeated"]
    for actual, expected in zip(complete["assemblyPoses"], data["placements"]):
        assert actual["id"] == expected["id"]
        assert actual["position"] == expected["position"] and actual["rotation"] == expected["rotation"]
    page.locator("#restart").click()
    page.locator("#start-first").click()
    page.locator("#capture-card").screenshot(path=str(output / "B-first-file.png"))
    page.set_viewport_size({"width": 375, "height": 900})
    no_overflow(page)
    page.locator("#plate-select").select_option("B-black-01.3mf")
    page.locator("#plate-isolate").check()
    page.locator('[data-scene="plate"] [data-view="bottom"]').click()
    no_overflow(page)
    page.locator("#next").click()
    page.locator("#capture-card").screenshot(path=str(output / "B-mobile-375.png"))
    page.set_viewport_size({"width": 1440, "height": 1100})


def capture_media(page, output):
    page.set_viewport_size({"width": 1440, "height": 1100})
    page.locator("#plate-isolate").uncheck()
    page.locator("#ghost").check()
    page.locator("#start-first").click()
    page.locator("#motion-progress").fill("100")
    page.locator("#capture-card").screenshot(path=str(output / "B-first-base.png"))
    page.locator("#plate-select").select_option("B-black-01.3mf")
    page.locator("#capture-card").screenshot(path=str(output / "B-black-01-sort.png"))
    page.locator("#plate-select").select_option("B-black-04.3mf")
    page.locator("#capture-card").screenshot(path=str(output / "B-black-04-base-parts.png"))
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    number = 0
    for cursor in range(24):
        page.evaluate("(n) => BrickAssemblyGuide.setCursor(n)", cursor)
        for progress in (0, .25, .5, .75, 1):
            page.evaluate("(n) => BrickAssemblyGuide.setProgress(n)", progress)
            page.locator("#capture-card").screenshot(path=str(frames / f"frame-{number:04}.png"))
            number += 1
    page.evaluate("BrickAssemblyGuide.setCursor(23); BrickAssemblyGuide.setProgress(1)")
    page.locator("#ghost").uncheck()
    page.locator("#capture-card").screenshot(path=str(output / "B-base-front-complete.png"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "6", "-i", str(frames / "frame-%04d.png"),
                    "-vf", "scale=1280:-2,pad=ceil(iw/2)*2:ceil(ih/2)*2,tpad=stop_mode=clone:stop_duration=2",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(output / "B-first-seven-steps.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(output / "B-first-seven-steps.mp4"),
                    "-filter_complex", "[0:v]fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
                    "-loop", "0", str(output / "B-first-seven-steps.gif")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(output / "B-first-seven-steps.mp4"), "-f", "null", "-"], check=True)
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", default="site/assembly-guide/B.html", help="Local B HTML or http(s) URL.")
    parser.add_argument("--all-models", action="store_true")
    parser.add_argument("--capture-media", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/assembly-guide-browser")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    url = args.entry if args.entry.startswith(("http://", "https://", "file://")) else Path(args.entry).resolve().as_uri()
    errors, outbound = [], []
    with sync_playwright() as p:
        launch = {"headless": True, "args": ["--enable-unsafe-swiftshader"]}
        if os.environ.get("BROWSER_PATH"):
            launch["executable_path"] = os.environ["BROWSER_PATH"]
        with p.chromium.launch(**launch) as browser:
            context = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1, reduced_motion="reduce")
            expected_origin = (urlsplit(url).scheme, urlsplit(url).netloc)
            def route_network(route):
                target = urlsplit(route.request.url)
                if expected_origin[0] in ("http", "https") and (target.scheme, target.netloc) == expected_origin:
                    route.continue_()
                else:
                    outbound.append(route.request.url)
                    route.abort()
            context.route("http://**/*", route_network)
            context.route("https://**/*", route_network)
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            ready(page, url)
            b_controls(page, args.output)
            frames = capture_media(page, args.output) if args.capture_media else 0
            models = ["B"]
            if args.all_models:
                for name, count in (("A", 91), ("C", 228)):
                    other = url.replace("/B.html", f"/{name}.html")
                    if other == url:
                        raise ValueError("--all-models requires an entry named B.html")
                    ready(page, other)
                    assert page.evaluate("BrickAssemblyGuide.mapping().part_count") == count
                    page.locator("#assembly-cursor").fill(str(count))
                    assert len(snapshot(page)["completedIds"]) == count
                    page.locator("#restart").click()
                    assert snapshot(page)["cursor"] == 0
                    page.set_viewport_size({"width": 375, "height": 900})
                    no_overflow(page)
                    page.set_viewport_size({"width": 1440, "height": 1100})
                    models.append(name)
            assert not outbound, outbound
            assert not errors, errors
            report = {
                "status": "PASS_REAL_PRINT_TO_PLACE_BROWSER", "models": models, "browser": browser.version,
                "file_protocol": url.startswith("file://"), "external_requests": len(outbound),
                "widths_px": [1440, 375], "b_occurrences": 150, "initial_plate": "B-black-02.3mf",
                "initial_slot": 3, "initial_placement": "B-001", "all_interchangeable_sources_and_targets": True,
                "manual_controls_and_replay": True, "final_poses_exact": True, "captured_motion_frames": frames,
                "physical_fit_tested": False, "sliced": False,
            }
            (args.output / "browser.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            context.close()


if __name__ == "__main__":
    main()
