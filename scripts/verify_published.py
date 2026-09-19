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
    exact = ["index.html", "guide.html", "assets/catalog.json"]
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
        exact += [f"downloads/{key}/{key}.FCStd", f"downloads/{key}/bom.csv",
                  f"media/{key}-assembly.mp4"]
    files.update(f"downloads/{part['stl']}" for part in c["parts"].values())
    def check(relative):
        headers = fetch(base + quote(relative), head=True).decode("latin1")
        assert "200" in headers or "206" in headers, relative
        return relative
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        reached = list(pool.map(check, sorted(files)))
    hashes = {}
    for relative in exact:
        remote = fetch(base + quote(relative))
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
        "status": "PASS_LIVE_GITHUB_PAGES", "base_url": base, "reachable_urls": reached,
        "exact_published_hashes": hashes, "native_range_downloads": prefixes,
        "source_photos": "not published", "physical_testing": "NOT_PERFORMED",
    })
    print(f"PASS live Pages: {len(reached)} URLs, {len(hashes)} exact download hashes, 6 native range downloads.")


if __name__ == "__main__":
    main()
