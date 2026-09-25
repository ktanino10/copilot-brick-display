"""Observe user-initiated playback in the official iframe; never confuse iframe presence with playback."""

import argparse
import json
import os
from pathlib import Path
import re
import time

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

EMBED = "https://www.youtube-nocookie.com/embed/Lc_enNE3nng?playsinline=1"


def video_state(frame):
    return frame.locator("video").evaluate_all(
        "videos => videos.map(video => ({time: video.currentTime, paused: video.paused,"
        "ready: video.readyState, error: video.error?.code || null}))"
    )


def check_player(browser, url, width, output):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    player = page.locator(".postprocess-video iframe")
    expect(player).to_have_count(1)
    expect(player).to_have_attribute("src", EMBED)
    expect(player).to_have_attribute("referrerpolicy", "strict-origin-when-cross-origin")
    player.scroll_into_view_if_needed()
    expect(player).to_be_visible()
    bounds = player.bounding_box()
    assert bounds and bounds["width"] <= width and abs(bounds["width"] / bounds["height"] - 16 / 9) < .02
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    frame = player.content_frame
    result = {"width_px": width, "layout": "PASS", "user_clicked_play": False,
              "actual_playback_observed": False, "new_tabs": 0}
    play = frame.get_by_role("button", name=re.compile(r"^(動画を再生|Play|Play video)$")).first
    try:
        expect(play).to_be_visible(timeout=25000)
    except (AssertionError, PlaywrightTimeoutError):
        result["limitation"] = "Official player did not expose its play control within25s; consent/network/service restrictions may apply."
    else:
        before = video_state(frame)
        assert all(video["paused"] and video["time"] < .2 for video in before), "Video started without the user's play click"
        result["before_click"] = before
        play.click()
        result["user_clicked_play"] = True
        samples = []
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            samples = video_state(frame)
            if any(video["time"] > .25 and not video["paused"] and video["error"] is None for video in samples):
                break
            if any(video["error"] is not None for video in samples):
                break
            page.wait_for_timeout(500)
        result["after_click"] = samples
        playing = next((video for video in samples if video["time"] > .25 and not video["paused"] and video["error"] is None), None)
        if playing:
            page.wait_for_timeout(1500)
            later = video_state(frame)
            result["later"] = later
            result["actual_playback_observed"] = any(
                video["time"] > playing["time"] + .5 and video["error"] is None for video in later)
        if not result["actual_playback_observed"]:
            result["limitation"] = "Play was clicked but advancing playback was not observed; do not label this an actual-playback pass."
    result["new_tabs"] = len(context.pages) - 1
    assert result["new_tabs"] == 0 and page.url == url, "Playing must not navigate away or open a new tab"
    page.locator(".postprocess-video").screenshot(path=str(output / f"player-{width}.png"))
    context.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        launch = {"headless": True}
        if os.environ.get("BROWSER_PATH"):
            launch["executable_path"] = os.environ["BROWSER_PATH"]
        with p.chromium.launch(**launch) as browser:
            results = [check_player(browser, args.url, width, args.output) for width in (1440, 375)]
            report = {
                "status": ("PASS_USER_INITIATED_EMBED_PLAYBACK" if all(r["actual_playback_observed"] for r in results)
                           else "LAYOUT_VERIFIED_PLAYBACK_NOT_FULLY_CONFIRMED"),
                "browser": browser.version, "entry_url": args.url, "embed": EMBED, "results": results,
                "third_party_network_required": True, "video_conditions_or_effects_verified": False,
                "video_audio_or_thumbnail_rehosted": False,
            }
            (args.output / "playback.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
