"""Build a self-contained, relative-URL publication from the canonical catalog."""
import hashlib
from html import escape
import json
from pathlib import Path
import zipfile

import markdown

ROOT = Path(__file__).resolve().parents[1]
DRAWINGS = [
    ("assembly-isometric.svg", "完成図", "CAD ASSEMBLY"),
    ("three-views.svg", "三面図", "FRONT / TOP / RIGHT"),
    ("exploded.svg", "分解図と部品ID", "EXPLODED VIEW"),
    ("part-dimensions.svg", "色別部品・最大外形", "PART DIMENSIONS"),
    ("interface-details.svg", "接続・隙間・最小形状", "INTERFACE DETAILS"),
    ("fit-coupons.svg", "本体より先に刷る試験片", "FIT COUPONS")
]
DOWNLOADS = [
    ("native/character-tribute.FCStd", "FreeCAD完成モデル", "29個の実形状・組立配置", "FCSTD"),
    ("native/character-tribute.step", "組立STEP", "CAD交換用・mm", "STEP"),
    ("media/character-assembly.blend", "Blender組立シーン", "実キーフレーム・カタログと同じ配置", "BLEND"),
    ("media/model.glb", "標準3Dプレビュー", "glTF 2.0 / m / 印刷にはSTLを使用", "GLB"),
    ("media/assembly.mp4", "組立動画", "21秒・日本語字幕付き", "MP4"),
    ("downloads/print-pack.zip", "印刷STLと部品表の一括パック", "本体20種類＋試験片12種類・色別BOM", "ZIP")
]


def asset(url, role):
    path = ROOT / url
    if not path.is_file():
        raise FileNotFoundError(f"Required publication asset is missing: {url}")
    content = path.read_bytes()
    return {"url": url, "role": role, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def table(parts, catalog):
    rows = []
    for part in parts:
        width, length, height = part["bounds_mm"]
        stages = sorted({i["step"] for i in catalog["instances"] if i["part"] == part["id"]})
        quantity = str(part["quantity"]) if part["category"] == "assembly" else "試験1"
        stage = ",".join(map(str, stages)) or "0 / 試験"
        rows.append(f'<tr data-part="{escape(part["id"])}"><td>{escape(part["id"])}</td>'
                    f'<td>{escape(part["name_ja"])}<small>{width:.2f} × {length:.2f} × {height:.2f} mm</small></td>'
                    f'<td>{quantity}</td><td>{stage}</td>'
                    f'<td><a href="{escape(part["mesh"])}" download>STL</a> · '
                    f'<a href="{escape(part["step"])}" download>STEP</a></td></tr>')
    return ('<table><thead><tr><th scope="col">ID</th><th scope="col">部品 / 印刷時の最大外形</th>'
            '<th scope="col">個数</th><th scope="col">工程</th><th scope="col">保存</th></tr></thead>'
            '<tbody>' + "".join(rows) + "</tbody></table>")


def guides():
    for name in ("howto.ja", "validation.ja", "reproduce.ja"):
        source = (ROOT / f"docs/{name}.md").read_text()
        rendered = markdown.markdown(source, extensions=["tables", "fenced_code", "toc"])
        for target in ("howto.ja", "validation.ja", "reproduce.ja"):
            rendered = rendered.replace(f'href="{target}.md"', f'href="{target}.html"')
        title = source.splitlines()[0].lstrip("# ")
        page = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{escape(title)}</title><link rel="stylesheet" href="../site.css"></head>'
                '<body><main class="guide"><nav class="guide-nav" aria-label="パンくず">'
                '<a href="../index.html">← @YOUR-USERNAME 製作ページ</a></nav>' + rendered + "</main></body></html>\n")
        (ROOT / f"docs/{name}.html").write_text(page)


def print_pack(catalog):
    (ROOT / "downloads").mkdir(exist_ok=True)
    note = ("@YOUR-USERNAME / T1 / mm / 100%\n\n"
            "このZIPは本体20種類・試験片12種類のSTLと色別部品表です。\n"
            "製作前に同じ版の docs/howto.ja.html を製作ページで読んでください。\n"
            "STL全体を拡大縮小せず、試験片から確認。文字は0.2mmノズルを使用。\n"
            "色レリーフは少量の接着を使う候補方式です。交換カード/ドック/背板-台座は無接着。\n"
            "実物のclutch・接着強度・転倒は未検証。市販部品へ無理に押し込まないでください。\n")
    files = [part["mesh"] for part in catalog["parts"]] + ["docs/bom.csv"]
    with zipfile.ZipFile(ROOT / "downloads/print-pack.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for url in sorted(files):
            info = zipfile.ZipInfo(url, (2026, 9, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / url).read_bytes())
        info = zipfile.ZipInfo("PRINT-README.txt", (2026, 9, 19, 0, 0, 0))
        archive.writestr(info, note.encode())


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    guides()
    print_pack(catalog)
    colors, parts = catalog["colors"], catalog["parts"]
    palette, batches = [], []
    for key, color in colors.items():
        selected = [p for p in parts if p["category"] == "assembly" and p["color"] == key]
        quantity = sum(p["quantity"] for p in selected)
        palette.append(f'<div class="swatch" style="--swatch:{color["hex"]}">{escape(color["name_ja"])}'
                       f'<span>{quantity} PARTS</span></div>')
        opened = " open" if key == "charcoal" else ""
        batches.append(f'<details class="color-batch"{opened}><summary>'
                       f'<i class="color-dot" style="--swatch:{color["hex"]}" aria-hidden="true"></i>'
                       f'{escape(color["name_ja"])}<span>{len(selected)}種類 / 組込{quantity}個</span></summary>'
                       f'<div class="table-wrap">{table(selected, catalog)}</div></details>')
    drawing_links = "".join(
        f'<a class="drawing-link" href="drawings/{file}"><img src="media/drawings/{Path(file).stem}.png" width="420" height="297" '
        f'loading="lazy" alt="{escape(title)}"><b>{escape(title)}</b><span>A3 / SVG / {subtitle}</span></a>'
        for file, title, subtitle in DRAWINGS)
    download_links = []
    for url, title, description, kind in DOWNLOADS:
        item = asset(url, "download")
        size = f'{item["bytes"]/1024/1024:.1f} MB' if item["bytes"] >= 1024*1024 else f'{item["bytes"]/1024:.0f} KB'
        download_links.append(f'<a class="download-item" href="{url}" download><span><b>{escape(title)}</b>'
                              f'<small>{escape(description)}</small></span><span class="file-type">{kind}<br>{size} ↓</span></a>')
    page = (ROOT / "templates/index.html").read_text()
    for key, value in {
        "PALETTE": "".join(palette), "PART_BATCHES": "".join(batches),
        "COUPONS": table([p for p in parts if p["category"] == "coupon"], catalog),
        "DRAWINGS": drawing_links, "DOWNLOADS": "".join(download_links)
    }.items():
        page = page.replace("{{" + key + "}}", value)
    if "{{" in page:
        raise ValueError("Unresolved site template placeholder")
    (ROOT / "index.html").write_text(page)
    urls = [(url, "download") for url, _, _, _ in DOWNLOADS]
    urls += [(f"drawings/{name}", "drawing") for name, _, _ in DRAWINGS]
    urls += [(f"media/drawings/{Path(name).stem}.png", "drawing_preview") for name, _, _ in DRAWINGS]
    urls += [(f"docs/{name}.html", "guide") for name in ("howto.ja", "validation.ja", "reproduce.ja")]
    urls += [("media/finished.png", "poster"), ("media/assembly.ja.vtt", "captions"),
             ("docs/bom.csv", "bom"), ("catalog.json", "canonical_catalog"),
             ("parameters.json", "parameters"), ("shared-lock.json", "shared_contract_lock"),
             ("sources.json", "sources"), ("index.html", "entry"), ("site.css", "stylesheet"),
             ("resources/fonts/B612Mono-Bold.ttf", "font"), ("resources/fonts/OFL.txt", "font_license")]
    urls += [(p["mesh"], "print_mesh") for p in parts] + [(p["step"], "part_step") for p in parts]
    urls += [(f"validation/{name}.json", "evidence") for name in ("native", "meshes", "assembly", "blender", "video", "glb")]
    manifest = {
        "schema_version": 1, "id": "character-tribute", "revision": catalog["revision"],
        "title": "@YOUR-USERNAME キャラクター記念楯", "entry": "index.html",
        "description_ja": "ユーザー提供のアイコンから新しく設計した、7色の段差レリーフと交換式メッセージカード。",
        "status": "digital_prototype_physical_fit_unverified",
        "adhesive_design_status": "candidate; manufacturing release awaits user decision through integrator",
        "dimensions_mm": catalog["assembly_size_mm"], "units_print": "mm", "fixed_pitch_mm": 8,
        "assembled_unique_parts": sum(p["category"] == "assembly" for p in parts),
        "assembly_instances": len(catalog["instances"]), "coupon_unique_parts": sum(p["category"] == "coupon" for p in parts),
        "message": catalog["message"], "message_removable": True,
        "physical_fit_tested": False, "safety_certified": False,
        "requires_ams": False, "recommended_nozzles_mm": {"structural": .4, "lettering": .2},
        "viewer": {"format": "glTF 2.0 binary", "url": "media/model.glb", "units": "m", "up_axis": "+Y",
                   "print_source": "catalog.json", "note": "Static preview; not a substitute for the mm STL masters."},
        "mount": {"project_relative_directory": "projects/character-tribute",
                  "instruction": "Publish this directory preserving relative URLs, excluding ignored build/runtime files; link index.html from the shared site."},
        "parts": [{"id": p["id"], "color": p["color"], "quantity": p["quantity"], "category": p["category"],
                   "mesh": p["mesh"], "step": p["step"], "bounds_mm": p["bounds_mm"]} for p in parts],
        "assets": [asset(url, role) for url, role in urls]
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("PUBLICATION_GENERATED", len(manifest["assets"]), "relative assets")


if __name__ == "__main__":
    main()
