"""Check the deployed Pages URLs, real downloads, and browser-ready movie bytes."""

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
from urllib.parse import quote

from design import ROOT, write_json


def fetch(url, head=False, limit=None):
    command = ["curl", "--fail", "--location", "--silent", "--show-error",
               "--retry", "2", "--max-time", "90"]
    if head:
        command += ["--head"]
    if limit:
        command += ["--range", f"0-{limit - 1}"]
    command.append(url)
    return subprocess.run(command, check=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://ktanino10.github.io/copilot-brick-display/")
    args = parser.parse_args()
    base = args.base.rstrip("/") + "/"
    c = json.loads((ROOT / "design/catalog.json").read_text())
    files = {"index.html", "guide.html", "technical.html", "rebuild.html", "notices.html",
             "assets/catalog.json", "app.js", "style.css", "vendor/three.module.js",
             "downloads/validation.json", "downloads/fit-coupons.zip", "downloads/interface.pdf",
             "downloads/part-drawings.pdf", "drawings/interface.svg", "tribute/index.html"}
    exact = ["index.html", "guide.html", "guide.js", "assets/catalog.json", "lettering.html",
             "downloads/lettering.json", "downloads/lettering-coupons.zip",
             "downloads/lettering-coupons/manifest.json"]
    files.update(exact)
    for model in c["models"]:
        key = model["id"]
        for filename in [f"{key}.FCStd", f"{key}.step", f"{key}.blend", "drawings.pdf",
                         "bom.csv", "assembly.json", "print-kit.zip", "plates.zip"]:
            files.add(f"downloads/{key}/{filename}")
        for filename in [f"{key}-hero.png", f"{key}-assembly.mp4", f"{key}-assembly.vtt"]:
            files.add(f"media/{filename}")
        files.add(f"drawings/{key}/overview.svg")
        files.add(f"drawings/{key}/exploded.svg")
        files.update(f"drawings/{key}/step-{step['number']:02d}.svg" for step in model["steps"])
        exact += [f"downloads/{key}/{key}.FCStd", f"downloads/{key}/{key}.step",
                  f"downloads/{key}/{key}.blend", f"downloads/{key}/bom.csv",
                  f"downloads/{key}/drawings.pdf", f"downloads/{key}/print-kit.zip",
                  f"downloads/{key}/plates.zip", f"downloads/{key}/plates/{key}-black-to-white-z2p4-01.3mf",
                  f"media/{key}-assembly.mp4", f"media/{key}-base-front.png",
                  f"downloads/parts/NP3-TEXT-{key}.stl", f"downloads/parts/NP3-LOGO-{key}.stl"]
        exact += [f"downloads/lettering-coupons/GLYPH-{key}.stl",
                  f"downloads/lettering-coupons/GLYPH-{key}.3mf",
                  f"media/lettering/{key}-lettering-before-after.png"]
    files.update(f"downloads/{part['stl']}" for part in c["parts"].values())
    assert not (ROOT / "site/tribute/manifest.json").exists(), "The private individual variant must not be distributed."
    files.update(("customize.html", "privacy.html", "trial.html", "downloads/trial-subset.zip"))
    exact += ["customize.html", "privacy.html", "trial.html", "downloads/trial-subset.zip",
              "downloads/trial-subset/manifest.json", "downloads/fit-log.csv"]
    exact += ["downloads/parts/BASE3-24x10-B-562406.stl", "downloads/parts/NP3-KEEPER.stl",
              "downloads/parts/FIT-M-D470.stl"]
    def check(relative):
        headers = fetch(base + quote(relative), head=True).decode("latin1")
        assert "200" in headers or "206" in headers, relative
        return relative
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        reached = list(pool.map(check, sorted(files)))
    hashes = {}
    for relative in exact:
        remote = fetch(base + quote(relative) + "?rev=" + quote(c["revision"]))
        local = (ROOT / "site" / relative).read_bytes()
        assert remote == local, f"Published bytes differ: {relative}"
        hashes[relative] = hashlib.sha256(remote).hexdigest()
    prefixes = {}
    for model in c["models"]:
        key = model["id"]
        for suffix, magic in [("step", b"ISO-10303-21"), ("blend", b"BLENDER")]:
            relative = f"downloads/{key}/{key}.{suffix}"
            downloaded = fetch(base + relative, limit=1024)
            assert downloaded.startswith(magic), relative
            prefixes[relative] = "download prefix matches native format"
    write_json(ROOT / "validation/published.json", {
        "status": "PASS_LIVE_GITHUB_PAGES", "base_url": base, "revision": c["revision"],
        "cache_identifying_url": base + "?rev=" + quote(c["revision"]), "reachable_urls": reached,
        "exact_published_hashes": hashes, "native_range_downloads": prefixes,
        "source_photos": "not published", "physical_testing": "NOT_PERFORMED",
    })
    print(f"PASS live Pages: {len(reached)} URLs, {len(hashes)} exact download hashes, 6 native range downloads.")


if __name__ == "__main__":
    main()
