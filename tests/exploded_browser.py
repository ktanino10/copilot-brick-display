"""Observe the rendered meshes, framing and screenshots at 0/50/100, not just pure math."""

import json
import math

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import expect


def verify_exploded(page, model, screenshots, mobile=False):
    label = "mobile" if mobile else "desktop"
    page.locator("#assembly").fill(str(len(model["steps"])))
    page.locator('[data-view="front"]').click()
    page.locator("#explode").fill("0")
    initial_direction = json.loads(page.locator("#viewport").get_attribute("data-camera-direction"))
    states = []
    for percent in (0, 50, 100):
        print("EXPLODED_VIEW", model["id"], label, percent, flush=True)
        page.locator("#explode").fill(str(percent))
        page.wait_for_timeout(200)
        expect(page.locator("#explode-value")).to_have_text(f"{percent}%")
        state = page.locator("#viewport").evaluate("""element => ({
          bounds: JSON.parse(element.dataset.displayBounds),
          direction: JSON.parse(element.dataset.cameraDirection),
          modules: JSON.parse(element.dataset.frontModuleBounds),
          offsets: JSON.parse(element.dataset.verticalOffsets),
          clip: Number(element.dataset.maxClipCoordinate),
          gap: Number(element.dataset.courseGapMm),
          error: Number(element.dataset.zeroPoseError),
          visible: Number(element.dataset.visibleInstances)
        })""")
        assert state["visible"] == model["part_count"]
        assert state["clip"] <= 1.001, (model["id"], label, percent, state)
        assert math.dist(state["direction"], initial_direction) < .01
        if percent == 0:
            assert state["error"] < 1e-7
            for bounds in state["modules"].values():
                assert 3.999 < bounds[0][2] < 4.001 and 43.999 < bounds[1][2] < 44.001
            assert state["modules"]["logo"][0][0] - state["modules"]["text"][1][0] >= 1.999
        if percent == 100:
            assert state["gap"] >= 9.6
            assert state["offsets"][0] < 0 < state["offsets"][1]
        path = screenshots / f"{model['id']}-{label}-explode-{percent:03}.png"
        page.locator("#viewport").screenshot(path=str(path), timeout=90000)
        states.append({"percent": percent, **state, "screenshot": path.name})
    a = Image.open(screenshots / f"{model['id']}-{label}-explode-000.png").convert("RGB")
    b = Image.open(screenshots / f"{model['id']}-{label}-explode-100.png").convert("RGB")
    assert sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3 > 8, "Rendered 0/100 states look unchanged"
    page.locator("#explode").press("Home")
    expect(page.locator("#explode-value")).to_have_text("0%")
    assert float(page.locator("#viewport").get_attribute("data-zero-pose-error")) < 1e-7
    page.locator("#explode").press("End")
    expect(page.locator("#explode-value")).to_have_text("100%")
    middle = max(1, len(model["steps"]) // 2)
    page.locator("#assembly").fill(str(middle))
    assert int(page.locator("#viewport").get_attribute("data-visible-instances")) == sum(
        item["step"] <= middle for item in model["placements"])
    page.locator("#assembly").fill(str(len(model["steps"])))
    page.locator("#explode").fill("0")
    for direction in ("side", "top", "iso", "front"):
        page.locator(f'[data-view="{direction}"]').click()
        page.locator("#explode").fill("100")
        assert float(page.locator("#viewport").get_attribute("data-max-clip-coordinate")) <= 1.001
        page.locator("#explode").fill("0")
    return {"model": model["id"], "viewport": label, "states": states,
            "keyboard_home_end": True, "return_to_zero_exact": True, "assembly_filter_consistent": True}
