"""Build a relative-URL T2 publication from the generated catalog and evidence."""
from collections import Counter
from fractions import Fraction
import hashlib
from html import escape
import json
import math
from pathlib import Path
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GUIDE_NAMES = ("howto.ja", "validation.ja", "reproduce.ja", "t2-change-review.ja")
BASE_DRAWING_FILES = {
    "assembly-isometric.svg", "three-views.svg", "exploded.svg",
    "part-dimensions.svg", "interface-details.svg", "fit-coupons.svg",
}
EXPECTED_MESSAGE = ["@YOUR-USERNAME", "Same icon, New adventures", "github.com/YOUR-USERNAME"]
FRONT_DOWN_PARTS = ("T02", "CAPTURE-FRAME")
VIDEO_ASSETS = {
    "assembly": {"url": "media/assembly.mp4", "captions": "media/assembly.ja.vtt", "scene": "Assembly"},
    "disassembly": {"url": "media/disassembly.mp4", "captions": "media/disassembly.ja.vtt", "scene": "Disassembly"},
}


def project_asset_path(url):
    parsed = urlsplit(url)
    decoded = unquote(parsed.path)
    if (not decoded or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or decoded.startswith("/") or "\\" in decoded or ".." in Path(decoded).parts):
        raise ValueError(f"Asset is not a project-local relative URL: {url}")
    path = (ROOT / decoded).resolve()
    path.relative_to(ROOT)
    return path


def asset(url, role):
    path = project_asset_path(url)
    if not path.is_file():
        raise FileNotFoundError(f"Required publication asset is missing: {url}")
    content = path.read_bytes()
    return {"url": url, "role": role, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def drawing_tuples(index):
    if index.get("revision") != "T2":
        raise ValueError("The drawing index must describe T2")
    result, seen = [], set()
    for sheet in index["sheets"]:
        name, title, subtitle = (sheet[key] for key in ("file", "title", "subtitle"))
        if (Path(name).name != name or not name.endswith(".svg") or name in seen
                or not title or not subtitle or not subtitle.isascii()):
            raise ValueError(f"Invalid or duplicate drawing sheet: {name}")
        project_asset_path(f"drawings/{name}")
        seen.add(name)
        result.append((name, title, subtitle))
    if not BASE_DRAWING_FILES <= seen:
        raise ValueError("The drawing index is missing a base sheet")
    return result


def load_drawings():
    return drawing_tuples(json.loads((ROOT / "drawings/index.json").read_text()))


# Importing source tests is allowed before drawings land; generation still requires the index.
DRAWINGS = load_drawings() if (ROOT / "drawings/index.json").is_file() else []


def print_quantity(part):
    category = part["category"]
    if category == "assembly":
        quantity = part["quantity"]
    elif category == "coupon":
        quantity = part.get("test_quantity", 1)
    elif category == "tool":
        quantity = part["tool_quantity"]
    else:
        raise ValueError(f"Unknown catalog category: {category}")
    if type(quantity) is not int or quantity < 1:
        raise ValueError(f"Invalid print quantity: {part['id']}")
    return quantity


def catalog_counts(catalog):
    parts, instances = catalog["parts"], catalog["instances"]
    by_id = {part["id"]: part for part in parts}
    if len(by_id) != len(parts) or len({row["id"] for row in instances}) != len(instances):
        raise ValueError("Duplicate part or assembly instance ID")
    actual = Counter(row["part"] for row in instances)
    if set(actual) - set(by_id):
        raise ValueError("Assembly instance references an unknown print master")
    for part in parts:
        if part["category"] != "tool" and part.get("tool_quantity",0) != 0:
            raise ValueError(f"Tool quantity is invalid for a non-tool category: {part['id']}")
        print_quantity(part)
        if part["color"] not in catalog["colors"]:
            raise ValueError(f"Unknown catalog color: {part['id']}")
        if (part["quantity"] != actual[part["id"]]
                or (part["category"] != "assembly" and part["quantity"] != 0)):
            raise ValueError(f"Catalog quantity/instance mismatch: {part['id']}")
    categories = Counter(part["category"] for part in parts)
    return {
        "print_master_count": len(parts), "assembled_unique_parts": categories["assembly"],
        "assembly_instances": len(instances), "coupon_unique_parts": categories["coupon"],
        "tool_unique_parts": categories["tool"],
        "coupon_print_quantity": sum(print_quantity(p) for p in parts if p["category"] == "coupon"),
        "tool_print_quantity": sum(print_quantity(p) for p in parts if p["category"] == "tool"),
    }


def video_metadata(evidence):
    try:
        stream = evidence["encoded_stream"]
        frames = int(evidence.get("frame_count", stream.get("nb_frames")))
        result = {"duration_seconds": float(stream["duration"]),
                  "fps": float(Fraction(stream["avg_frame_rate"])), "frames": frames,
                  "width": int(stream["width"]), "height": int(stream["height"])}
        if "nb_frames" in stream and int(stream["nb_frames"]) != frames:
            raise ValueError("Encoded and declared frame counts disagree")
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError("Video stream metadata is missing or inconsistent") from error
    if (evidence.get("status") != "pass" or evidence.get("decode_errors") != 0
            or evidence.get("decoded_frames") != result["frames"]
            or any(not math.isfinite(value) or value <= 0 for value in result.values())
            or abs(result["duration_seconds"] * result["fps"] - result["frames"]) > 1):
        raise ValueError("Video evidence is incomplete or internally inconsistent")
    return result


def publication_videos(evidence):
    if not isinstance(evidence.get("disassembly"), dict):
        raise ValueError("Separate disassembly video evidence is required")
    return {
        "assembly": video_metadata(evidence),
        "disassembly": video_metadata({"status": evidence.get("status"), **evidence["disassembly"]}),
    }


def manufacturing_contract(catalog, parameters):
    parts = {part["id"]: part for part in catalog["parts"]}
    for name in FRONT_DOWN_PARTS:
        if (parameters.get("print_orientations", {}).get(name) != [180, 0, 0]
                or parts[name].get("print_rotation_deg_xyz") != [180, 0, 0]
                or parts[name].get("print_orientation") != "front_face_on_bed"):
            raise ValueError(f"The supplied {name} master must already be oriented front-down")
    release = parameters.get("release_tool", {})
    maximum = release.get("max_initial_push_mm")
    if (not isinstance(maximum, (int, float)) or not math.isfinite(maximum) or not 0 < maximum <= 3.5
            or release.get("then_grip_rear_flange") is not True):
        raise ValueError("EJECTOR is limited to an initial push of at most 3.5 mm, then grip the rear flange")
    if (not catalog.get("manufacturing_revision")
            or catalog["manufacturing_revision"] != parameters.get("manufacturing_revision")):
        raise ValueError("Catalog and parameters must identify the same manufacturing correction")
    return {"max_initial_push_mm": maximum, "then_grip_rear_flange": True,
            "full_removal_with_tool": False}


def public_metadata(catalog, parameters, videos):
    for source in (catalog, parameters):
        if (source.get("revision") != "T2" or source.get("message") != EXPECTED_MESSAGE
                or source.get("adhesive_required") is not False
                or source.get("all_parts_removable") is not True):
            raise ValueError("T2 requires the confirmed message and fully removable/no-adhesive method")
    pitch = catalog["shared_interface"]["brick"]["pitch"]
    if pitch != 8 or parameters["nominal_pitch"] != pitch:
        raise ValueError("The pinned common 8 mm interface must not change")
    video_entries = {name: {**VIDEO_ASSETS[name], "evidence": "validation/video.json", **metadata}
                     for name, metadata in videos.items()}
    release_tool = manufacturing_contract(catalog, parameters)
    return {
        "revision": catalog["revision"], "status": "digital_prototype_physical_fit_unverified",
        "manufacturing_revision": catalog["manufacturing_revision"], "release_tool": release_tool,
        "adhesive_required": False, "all_parts_removable": True,
        "adhesive_design_status": "rejected",
        "manufacturing_method_status": "user_confirmed_fully_removable_no_adhesive",
        "independent_retention_review": "pending_coordinated_review",
        "dimensions_mm": catalog["assembly_size_mm"], "units_print": catalog["units"],
        "fixed_pitch_mm": pitch, **catalog_counts(catalog),
        "message": catalog["message"], "message_removable": True,
        "physical_fit_tested": False, "thread_durability_tested": False,
        "tipping_tested": False, "safety_certified": False, "requires_ams": False,
        "recommended_nozzles_mm": {"structural": parameters["print"]["nozzle_baseline"],
                                   "lettering": parameters["print"]["nozzle_detail"]},
        "video": video_entries["assembly"], "videos": video_entries,
    }


def publication_parts(catalog):
    fields = ("id", "color", "quantity", "category", "mesh", "step", "bounds_mm", "tool_quantity",
              "print_origin_mm", "print_rotation_deg_xyz", "print_orientation")
    return [{**{key: part[key] for key in fields if key in part}, "print_quantity": print_quantity(part)}
            for part in catalog["parts"]]


def table(parts, catalog):
    rows = []
    for part in parts:
        width, length, height = part["bounds_mm"]
        stages = sorted({row["step"] for row in catalog["instances"] if row["part"] == part["id"]})
        category, quantity = part["category"], print_quantity(part)
        purpose = {"assembly": "組込", "coupon": "試験", "tool": "治具"}[category]
        stage = ",".join(map(str, stages)) or "本体組込なし"
        orientation = part.get("print_orientation", "flat_base_as_exported")
        print_note = "<small>前面を下 / 提供STLは方向設定済み</small>" if orientation == "front_face_on_bed" else ""
        rows.append(f'<tr data-part="{escape(part["id"])}" data-category="{category}" '
                    f'data-print-quantity="{quantity}" data-print-orientation="{escape(orientation)}">'
                    f'<td>{escape(part["id"])}</td>'
                    f'<td>{escape(part["name_ja"])}<small>{width:.2f} × {length:.2f} × {height:.2f} mm</small>{print_note}</td>'
                    f'<td>{purpose} {quantity}</td><td>{stage}</td>'
                    f'<td><a href="{escape(part["mesh"])}" download>STL</a> · '
                    f'<a href="{escape(part["step"])}" download>STEP</a></td></tr>')
    return ('<table><thead><tr><th scope="col">ID</th><th scope="col">部品 / 印刷時の最大外形</th>'
            '<th scope="col">用途 / 個数</th><th scope="col">工程</th><th scope="col">保存</th></tr></thead>'
            '<tbody>' + "".join(rows) + "</tbody></table>")


def guides():
    import markdown

    for name in GUIDE_NAMES:
        source = (ROOT / f"docs/{name}.md").read_text()
        rendered = markdown.markdown(source, extensions=["tables", "fenced_code", "toc"])
        for target in GUIDE_NAMES:
            rendered = rendered.replace(f'href="{target}.md"', f'href="{target}.html"')
        title = source.splitlines()[0].lstrip("# ")
        page = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{escape(title)}</title><link rel="stylesheet" href="../site.css"></head>'
                '<body><main class="guide"><nav class="guide-nav" aria-label="パンくず">'
                '<a href="../index.html">← @YOUR-USERNAME 製作ページ</a></nav>' + rendered + "</main></body></html>\n")
        (ROOT / f"docs/{name}.html").write_text(page)


def print_pack_readme(catalog, parameters):
    counts = catalog_counts(catalog)
    maximum = manufacturing_contract(catalog, parameters)["max_initial_push_mm"]
    tools = " / ".join(f'{part["id"]} ×{print_quantity(part)}'
                       for part in catalog["parts"] if part["category"] == "tool")
    return (f'@YOUR-USERNAME / {catalog["revision"]} / mm / 100%\n\n'
            f'印刷マスター{counts["print_master_count"]}種類：組立{counts["assembled_unique_parts"]}種類'
            f'・{counts["assembly_instances"]}個、試験片{counts["coupon_unique_parts"]}種類、'
            f'治具{counts["tool_unique_parts"]}種類・{counts["tool_print_quantity"]}個。\n'
            f'治具：{tools}。試験片・治具は本体組込数に含みません。\n'
            "色・数量・配置・工程の正本は生成されたcatalog.jsonです。色別BOMを同梱しています。\n"
            "全パーツを着脱・再組立できる無接着方式をユーザーが選択済みです。T1の接着方式は却下。\n"
            "製作前に同じ版のdocs/howto.ja.htmlと検証範囲を製作ページで読んでください。\n"
            "THREAD-C40と実物T04、CAPTURE-FRAME/COVERと実物IN-W-1x1で先に試験。\n"
            "T04は独自の印刷TR11.2-P3.2で、標準M12金具ではありません。追加購入金具は不要です。\n"
            "STLは100%のまま。試験片・治具の表示色ではなく、本番の材料・色・ノズルで確認。\n"
            "T02とCAPTURE-FRAMEは前面を下にする提供済みの印刷方向です。さらに180度回転させないでください。\n"
            "他の部品の提供STLの向きは変更していません。すべてを同じ面で印刷する指定ではありません。\n"
            "文字は0.2mmノズル。組立はASSEMBLY-RESTで前面の突出部を保護して前面下向き。\n"
            "分解は背面から反時計回りにねじ4本を外し、裏蓋、瞳、虹彩、白目の順。Mは白いバッジより先。\n"
            f"EJECTORは初動のみ最大{maximum:g}mmで工具を止めます。露出した後ろのフランジをつまみ、残りを引き抜きます。\n"
            "押し棒だけで最後まで押し出しません。色部品は後方へ取り出し、柔らかいトレイで受けます。\n"
            "細い首をこじらず、固ければ停止。最大距離まで必ず押す指示ではありません。\n"
            "実物嵌合・ねじ寿命・保持力・転倒・手での作業性は未検証。独立保持レビューは統合担当が調整します。\n")


def print_pack(catalog, parameters):
    (ROOT / "downloads").mkdir(exist_ok=True)
    files = [part["mesh"] for part in catalog["parts"]] + ["docs/bom.csv"]
    with zipfile.ZipFile(ROOT / "downloads/print-pack.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for url in sorted(files):
            info = zipfile.ZipInfo(url, (2026, 9, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, project_asset_path(url).read_bytes())
        archive.writestr(zipfile.ZipInfo("PRINT-README.txt", (2026, 9, 19, 0, 0, 0)),
                         print_pack_readme(catalog, parameters).encode())


def download_specs(catalog, videos):
    counts = catalog_counts(catalog)
    return [
        ("native/character-tribute.FCStd", "FreeCAD完成モデル",
         f'{counts["assembly_instances"]}個の実形状・組立配置', "FCSTD"),
        ("native/character-tribute.step", "組立STEP", "CAD交換用・mm", "STEP"),
        ("media/character-assembly.blend", "Blender組立・分解シーン", "Assembly / Disassemblyの2シーン・実キーフレーム", "BLEND"),
        ("media/model.glb", "標準3Dプレビュー", "Assembly完成時 / glTF 2.0 / m / 印刷にはSTLを使用", "GLB"),
        *[(VIDEO_ASSETS[name]["url"], title, f'{videos[name]["duration_seconds"]:g}秒・日本語字幕付き', "MP4")
          for name, title in (("assembly", "組立動画"), ("disassembly", "分解動画"))],
        ("downloads/print-pack.zip", "印刷STLと部品表の一括パック",
         f'組立{counts["assembled_unique_parts"]}＋試験片{counts["coupon_unique_parts"]}'
         f'＋治具{counts["tool_unique_parts"]}種類・色別BOM', "ZIP"),
    ]


def render_page(catalog, videos, drawings, download_links, *, parameters):
    colors, parts = catalog["colors"], catalog["parts"]
    counts = catalog_counts(catalog)
    palette, batches = [], []
    for key, color in colors.items():
        selected = [part for part in parts if part["category"] == "assembly" and part["color"] == key]
        if not selected:
            continue
        quantity = sum(part["quantity"] for part in selected)
        palette.append(f'<div class="swatch" style="--swatch:{color["hex"]}">{escape(color["name_ja"])}'
                       f'<span>{quantity} PARTS</span></div>')
        opened = " open" if key == "charcoal" else ""
        batches.append(f'<details class="color-batch"{opened}><summary>'
                       f'<i class="color-dot" style="--swatch:{color["hex"]}" aria-hidden="true"></i>'
                       f'{escape(color["name_ja"])}<span>{len(selected)}種類 / 組込{quantity}個</span></summary>'
                       f'<div class="table-wrap">{table(selected, catalog)}</div></details>')
    drawing_links = "".join(
        f'<a class="drawing-link" href="drawings/{escape(name)}"><img src="media/drawings/{Path(name).stem}.png" '
        f'width="420" height="297" loading="lazy" alt="{escape(title)}">'
        f'<b>{escape(title)}</b><span>A3 / SVG / {escape(subtitle)}</span></a>'
        for name, title, subtitle in drawings)
    replacements = {
        "PALETTE": "".join(palette), "PART_BATCHES": "".join(batches),
        "COUPONS": table([part for part in parts if part["category"] == "coupon"], catalog),
        "TOOLS": table([part for part in parts if part["category"] == "tool"], catalog),
        "DRAWINGS": drawing_links, "DOWNLOADS": download_links, "REVISION": catalog["revision"],
        "DIMENSIONS": " × ".join(f"{value:g}" for value in catalog["assembly_size_mm"]),
        "COLOR_COUNT": str(len(palette)),
        "EJECTOR_INITIAL_PUSH_MM": f'{manufacturing_contract(catalog, parameters)["max_initial_push_mm"]:g}',
        **{key.upper(): str(value) for key, value in counts.items()},
    }
    for name, video in videos.items():
        replacements.update({
            f"{name.upper()}_VIDEO_SECONDS": f'{video["duration_seconds"]:g}',
            f"{name.upper()}_VIDEO_WIDTH": str(video["width"]),
            f"{name.upper()}_VIDEO_HEIGHT": str(video["height"]),
        })
    page = (ROOT / "templates/index.html").read_text()
    for key, value in replacements.items():
        page = page.replace("{{" + key + "}}", value)
    if "{{" in page:
        raise ValueError("Unresolved site template placeholder")
    return page


def publication_urls(catalog, drawings, videos):
    urls = [(url, "download") for url, _, _, _ in download_specs(catalog, videos)]
    urls += [(f"drawings/{name}", "drawing") for name, _, _ in drawings]
    urls += [(f"media/drawings/{Path(name).stem}.png", "drawing_preview") for name, _, _ in drawings]
    urls += [(f"docs/{name}.html", "guide") for name in GUIDE_NAMES]
    urls += [(f"docs/{name}.md", "guide_source") for name in GUIDE_NAMES]
    urls += [("drawings/index.json", "drawing_index"), ("README.md", "readme"),
             ("media/finished.png", "poster"),
             ("docs/bom.csv", "bom"), ("catalog.json", "canonical_catalog"),
             ("parameters.json", "parameters"), ("shared-lock.json", "shared_contract_lock"),
             ("sources.json", "sources"), ("index.html", "entry"), ("site.css", "stylesheet"),
             ("resources/fonts/B612Mono-Bold.ttf", "font"), ("resources/fonts/OFL.txt", "font_license")]
    urls += [(part["mesh"], "print_mesh") for part in catalog["parts"]]
    urls += [(part["step"], "part_step") for part in catalog["parts"]]
    urls += [(spec["captions"], "captions") for spec in VIDEO_ASSETS.values()]
    urls += [(f"validation/{name}.json", "evidence")
             for name in ("native", "meshes", "assembly", "fixture", "print-pose", "print-pose-invariance",
                          "blender", "video", "glb")]
    urls += [(f"scripts/{name}.py", "evidence_source")
             for name in ("verify_fixture", "verify_print_pose", "verify_print_invariance", "render_drawing_previews")]
    urls += [(f"validation/{name}.json","evidence") for name in
             ("transfer-before","transfer-regression","transfer-samples","transfer-motion","transfer-video-update",
              "review-corrections")]
    urls += [(f"scripts/{name}.py","evidence_source") for name in
             ("sample_transfer_motion","verify_transfer_motion","partial_video_update","check_review_corrections")]
    urls += [("validation/web.json", "browser_evidence"),
             ("validation/drawing-previews.json", "drawing_preview_evidence")]
    return urls


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    parameters = json.loads((ROOT / "parameters.json").read_text())
    videos = publication_videos(json.loads((ROOT / "validation/video.json").read_text()))
    drawings = load_drawings()
    metadata = public_metadata(catalog, parameters, videos)
    guides()
    print_pack(catalog, parameters)
    download_links = []
    for url, title, description, kind in download_specs(catalog, videos):
        item = asset(url, "download")
        size = f'{item["bytes"]/1024/1024:.1f} MB' if item["bytes"] >= 1024*1024 else f'{item["bytes"]/1024:.0f} KB'
        download_links.append(f'<a class="download-item" href="{url}" download><span><b>{escape(title)}</b>'
                              f'<small>{escape(description)}</small></span><span class="file-type">{kind}<br>{size} ↓</span></a>')
    (ROOT / "index.html").write_text(render_page(catalog, videos, drawings, "".join(download_links),
                                               parameters=parameters))
    manifest = {
        "schema_version": 1, "id": "character-tribute", **metadata,
        "title": "@YOUR-USERNAME キャラクター記念楯", "entry": "index.html",
        "description_ja": "色別の捕捉カセット、印刷ねじと裏蓋、交換式カードで組む、全パーツ着脱可能な無接着記念楯。",
        "viewer": {"format": "glTF 2.0 binary", "url": "media/model.glb", "units": "m", "up_axis": "+Y",
                   "scene": "Assembly",
                   "print_source": "catalog.json", "note": "Static preview; not a substitute for the mm STL masters."},
        "mount": {"project_relative_directory": "projects/character-tribute",
                  "instruction": "Publish this directory preserving relative URLs, excluding ignored build/runtime files; link index.html from the shared site."},
        "parts": publication_parts(catalog),
        "assets": [asset(url, role) for url, role in publication_urls(catalog, drawings, videos)],
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("PUBLICATION_GENERATED", len(manifest["assets"]), "relative assets; independent review pending")


if __name__ == "__main__":
    main()
