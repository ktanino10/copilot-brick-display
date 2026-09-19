"""Check the T2 contract, evidence, relative links, archive contents and privacy."""
import hashlib
import csv
import io
from html import unescape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import zipfile

from publish import (FRONT_DOWN_PARTS, GUIDE_NAMES, VIDEO_ASSETS, catalog_counts, load_drawings,
                     manufacturing_contract, print_pack_readme,
                     project_asset_path, public_metadata, publication_parts,
                     publication_urls, publication_videos)

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if "id" in values:
            self.ids.add(values["id"])
        for key in ("href", "src", "poster"):
            if key in values:
                self.links.append(values[key])


def validate_bom_categories(catalog,content):
    rows=list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    expected={part["id"]:part for part in catalog["parts"]}
    if len(rows)!=len(expected) or {row["Part ID"] for row in rows}!=set(expected):
        raise ValueError("BOM part IDs differ from the canonical catalog")
    total=0
    for row in rows:
        part=expected[row["Part ID"]]
        tools=part["tool_quantity"] if part["category"]=="tool" else 0
        if row["分類"]!=part["category"] or int(row["工具数"])!=tools:
            raise ValueError(f"BOM tool/category mismatch: {part['id']}")
        if int(row["完成品組込数"])!=part["quantity"]:
            raise ValueError(f"BOM assembly quantity mismatch: {part['id']}")
        total+=int(row["工具数"])
    if total!=catalog_counts(catalog)["tool_print_quantity"]:
        raise ValueError("BOM tool total differs from canonical tool quantities")
    return total


def validate_guide_tool_angles(catalog,text):
    expected={}
    for instance in catalog["instances"]:
        if instance["part"].startswith(("EYE-","BADGE-")):
            angle=instance["tool_tip_rotation_deg"]
            previous=expected.setdefault(instance["part"],angle)
            if previous!=angle:
                raise ValueError("Shared detail part has inconsistent tool orientations")
    if "<tr" in text:
        rows=[[re.sub(r"<[^>]+>","",unescape(c)).strip() for c in
               re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",row,re.S)]
              for row in re.findall(r"<tr[^>]*>(.*?)</tr>",text,re.S)]
    else:
        rows=[[cell.strip() for cell in line.split("|")[1:-1]]
              for line in text.splitlines() if line.startswith("|")]
    found=set()
    for row in rows:
        if len(row)<3:
            continue
        pid=row[0].split(" ")[0]
        if pid not in expected:
            continue
        match=re.search(r"(-?\d+)°",row[2])
        if match is None:
            continue
        if int(match.group(1))!=expected[pid]:
            raise ValueError(f"Guide tool angle differs from canonical {pid}: {row[2]}")
        found.add(pid)
    if found!=set(expected):
        raise ValueError("The guide is missing a canonical detail-tool angle")


def assert_no_active_adhesive(text, label):
    plain = re.sub(r"<[^>]+>", " ", unescape(text))
    compact = re.sub(r"\s+", "", plain)
    japanese = (
        r"製作リリース保留|この方式のユーザー承認は未確認",
        r"接着を省いて無接着版として組まない",
        r"完全硬化(?:後|時間|まで)",
        r"(?:接着剤?|(?:両面)?テープ|熱かしめ|溶着|溶接)"
        r"(?:が必要|を使います|を使用します|を塗|を貼|します|してください|し[、，,]|して固定|して保持|で固定|で保持)",
        r"接着剤(?:は|を)[^。!?]{0,80}(?:薄く置|塗布|流し込|硬化)",
    )
    english = (
        r"\b(?:glue|tape|heat[\s-]?stake|weld)\s+(?:the|each|all|these|your)\b",
        r"\b(?:apply|use|requires?|needs?)\s+(?:(?:a|some|a little|small amounts? of)\s+)?(?:adhesive|glue|tape)\b",
        r"\b(?:awaits?|pending|waiting for)\b[^.!?\n]{0,100}\b(?:adhesive|glue)\b",
        r"\b(?:adhesive|glue)\s+(?:approval|cure|curing)\b",
    )
    if (any(re.search(pattern, compact) for pattern in japanese)
            or any(re.search(pattern, plain, re.IGNORECASE) for pattern in english)):
        raise ValueError(f"Rejected T1 adhesive instruction/approval hold remains in {label}")


def assert_manufacturing_guidance(text, label, max_initial_push_mm=None):
    plain = re.sub(r"<[^>]+>", " ", unescape(text))
    compact = re.sub(r"\s+", "", plain)
    unsafe = (
        r"(?:すべてのSTL|全(?:部|て)の部品|T02|CAPTURE-FRAME)[^。!?]{0,30}背面を下にして(?:印刷します|置いてください)",
        r"(?:EJECTOR|押し棒)(?:で|を使って)[^。!?]{0,30}(?:最後まで押し出してください|全部取り出します|全行程を押します)",
        r"\bprint\s+all\s+parts\s+back[- ]down\b",
        r"\buse\s+the\s+(?:pusher|ejector)\s+for\s+full\s+removal\b",
    )
    for index, pattern in enumerate(unsafe):
        candidate = compact if index < 2 else plain
        for match in re.finditer(pattern, candidate, re.IGNORECASE):
            prefix = candidate[max(0, match.start() - 24):match.start()]
            if index >= 2 and re.search(r"(?:do\s+not|never|don't)\s*$", prefix, re.IGNORECASE):
                continue
            raise ValueError(f"Unsafe print orientation or full-stroke pusher instruction in {label}")
    if max_initial_push_mm is not None:
        bound = re.escape(f"{max_initial_push_mm:g}")
        required = (rf"{bound}\s*mm", r"初動|initial", r"止め|停止|\bstop\b",
                    r"フランジ|flange", r"つま|つか|掴|\bgrip\b")
        if not all(re.search(pattern, plain, re.IGNORECASE) for pattern in required):
            raise ValueError(f"Missing bounded initial push, stop, and flange-grip warning in {label}")


def browser_evidence_status(catalog, report):
    revision = report.get("manufacturing_revision", report.get("revision"))
    status, tested = report.get("status"), report.get("browser_tested")
    if (revision != catalog["manufacturing_revision"]
            or not ((status == "pass" and tested is True)
                    or (status == "blocked_environment" and tested is False))):
        raise ValueError("Browser evidence must identify the current correction and distinguish blocked from tested")
    return {"browser_status": status, "browser_tested": tested}


def verify_asset(item):
    content = project_asset_path(item["url"]).read_bytes()
    if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
        raise ValueError(f"Publication asset changed since manifest generation: {item['url']}")
    return len(content)


def validate_manifest_metadata(catalog, parameters, manifest, videos):
    expected = public_metadata(catalog, parameters, videos)
    for key, value in expected.items():
        if key == "independent_retention_review":
            # Only the integration owner may replace the publisher's pending marker after review.
            if manifest.get(key) not in ("pending_coordinated_review", "accepted_digital_only"):
                raise ValueError("Invalid coordinated review status")
        elif manifest.get(key) != value:
            raise ValueError(f"Publication metadata disagrees with the T2 catalog/evidence: {key}")
    if manifest.get("parts") != publication_parts(catalog):
        raise ValueError("Publication part/category/print quantities disagree with the catalog")


def validate_video_timelines(blender, videos):
    scenes = blender.get("scenes")
    if isinstance(scenes, dict):
        timelines = {name: scenes.get(spec["scene"]) for name, spec in VIDEO_ASSETS.items()}
        if any(not isinstance(timeline, dict) for timeline in timelines.values()):
            raise ValueError("Blender evidence must include both named scenes")
    else:
        timelines = {"assembly": blender}
        if isinstance(blender.get("disassembly"), dict):
            timelines["disassembly"] = blender["disassembly"]
        if isinstance(scenes, list) and not {spec["scene"] for spec in VIDEO_ASSETS.values()} <= set(scenes):
            raise ValueError("Blender evidence is missing an animation scene")
    for name, timeline in timelines.items():
        if (timeline.get("frame_count") != videos[name]["frames"]
                or timeline.get("fps", blender.get("fps")) != videos[name]["fps"]):
            raise ValueError(f"Blender and encoded video timeline disagree: {name}")


def validate_fixture_evidence(catalog, fixture):
    rest = next(part for part in catalog["parts"] if part["id"] == "ASSEMBLY-REST")
    clearances = [fixture.get(key) for key in (
        "front_frame_plane_above_table_mm", "minimum_relief_table_clearance_mm")]
    if (fixture.get("status") != "pass" or fixture.get("revision") != catalog["revision"]
            or fixture.get("rest_quantity") != rest["tool_quantity"]
            or fixture.get("frame_contacts_verified") is not True
            or fixture.get("rest_part_intersections") != 0
            or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
                   for value in clearances)):
        raise ValueError("Fixture evidence must verify the catalog support quantity, contacts and positive clearance")


def validate_manufacturing_evidence(catalog, parameters, reports):
    maximum = manufacturing_contract(catalog, parameters)["max_initial_push_mm"]
    pose, unchanged, assembly = (reports[name] for name in ("print-pose", "print-pose-invariance", "assembly"))
    revision = catalog["manufacturing_revision"]
    for report in (pose, unchanged, assembly):
        if (report.get("status") != "pass"
                or report.get("manufacturing_revision", report.get("revision")) != revision):
            raise ValueError("Manufacturing correction evidence is stale or incomplete")
    if set(pose["parts"]) != set(FRONT_DOWN_PARTS):
        raise ValueError("Print footprint evidence must cover both front-down masters")
    for name, part in pose["parts"].items():
        if (part.get("print_rotation_deg_xyz") != parameters["print_orientations"][name]
                or part.get("bed_contact_area_mm2", 0) <= 0 or not part.get("layer_samples")
                or any(row.get("area_outside_first_layer_footprint_mm2") != 0
                       for row in part["layer_samples"])):
            raise ValueError(f"Print footprint evidence does not establish the corrected pose: {name}")
    if set(unchanged["instances"]) != {row["id"] for row in catalog["instances"]}:
        raise ValueError("Inverse-placement evidence does not cover the canonical assembly")
    pushes = assembly.get("ejector_full_shape_validated_pushes_mm", [])
    if not pushes or 0 not in pushes or maximum not in pushes or min(pushes) < 0 or max(pushes) > maximum:
        raise ValueError("Full EJECTOR shape must be tested only through the bounded initial push")
    expected = {row["id"]: row for row in catalog["instances"] if "tool_target_xy" in row}
    actual = {row["instance"]: row for row in assembly["reverse_order_removal_and_tool_access"]
              if row.get("front_tool_target_xy") is not None}
    if set(actual) != set(expected):
        raise ValueError("Initial-push evidence must cover every captured color part")
    for name, row in actual.items():
        if (row.get("max_initial_tool_push_mm") != maximum or row.get("then_grip_rear_flange") is not True
                or row["front_tool_target_xy"] != expected[name]["tool_target_xy"]
                or row["tool_tip_rotation_deg"] != expected[name]["tool_tip_rotation_deg"]):
            raise ValueError(f"Initial push and subsequent flange grip are not specified correctly: {name}")
    overstroke = assembly.get("unsafe_overstroke_regression", {})
    if overstroke.get("push_mm", 0) <= maximum or overstroke.get("iris_intersection_mm3", 0) <= 0:
        raise ValueError("The unsafe full-removal pusher regression must remain documented")


def validate_evidence(catalog, reports):
    counts = catalog_counts(catalog)
    instances, masters = counts["assembly_instances"], counts["print_master_count"]
    ids = {part["id"] for part in catalog["parts"]}
    for name, report in reports.items():
        if report.get("status") != "pass":
            raise ValueError(f"Evidence is not passing: {name}")
    native, meshes = reports["native"], reports["meshes"]
    assembly, blender, glb = (reports[name] for name in ("assembly", "blender", "glb"))
    videos = publication_videos(reports["video"])
    if (native.get("native_reopened") is not True or native.get("instance_count") != instances
            or native.get("step_reopened_solids") != instances or set(native["individual_steps"]) != ids):
        raise ValueError("Native evidence is stale or does not cover every catalog part")
    if meshes.get("parts_checked") != masters or set(meshes["parts"]) != ids:
        raise ValueError("Mesh evidence is stale or incomplete")
    validate_fixture_evidence(catalog, reports["fixture"])
    if assembly.get("brep_pair_checks") != instances * (instances - 1) // 2:
        raise ValueError("Assembly pair evidence is not for the current instance count")
    if (native.get("physical_fit_tested") is not False or assembly.get("physical_fit_tested") is not False
            or assembly.get("safety_certified") is not False):
        raise ValueError("Digital evidence must not claim unperformed physical tests")
    if blender.get("native_reopened") is not True or blender.get("instances") != instances:
        raise ValueError("Blender evidence disagrees with the current catalog")
    validate_video_timelines(blender, videos)
    if (glb.get("instances") != instances or glb.get("meshes") != counts["assembled_unique_parts"]
            or glb.get("units") != "m" or glb.get("up_axis") != "+Y"):
        raise ValueError("GLB evidence is stale or has incorrect preview units")
    hash_checks = [
        (blender, "catalog_sha256", "catalog.json"),
        (blender, "blend_sha256", "media/character-assembly.blend"),
        (glb, "sha256", "media/model.glb"),
    ]
    hash_checks += [
        (reports["video"] if name == "assembly" else reports["video"][name], "mp4_sha256", spec["url"])
        for name, spec in VIDEO_ASSETS.items()
    ]
    for report, key, url in hash_checks:
        if report.get(key) != hashlib.sha256(project_asset_path(url).read_bytes()).hexdigest():
            raise ValueError(f"Evidence hash does not match the current asset: {url}")
    return videos


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    parameters = json.loads((ROOT / "parameters.json").read_text())
    manifest = json.loads((ROOT / "manifest.json").read_text())
    reports = {name: json.loads((ROOT / f"validation/{name}.json").read_text())
               for name in ("native", "meshes", "assembly", "fixture", "print-pose", "print-pose-invariance",
                            "blender", "video", "glb")}
    validate_manufacturing_evidence(catalog, parameters, reports)
    videos = validate_evidence(catalog, reports)
    validate_manifest_metadata(catalog, parameters, manifest, videos)
    browser = browser_evidence_status(catalog, json.loads((ROOT / "validation/web.json").read_text()))
    lock = json.loads((ROOT / "shared-lock.json").read_text())
    if (lock["commit"] != "WITHDRAWN-PRIVACY-REVISION"
            or lock["interface_id"] != catalog["shared_interface"]["id"]):
        raise ValueError("The common interface is no longer the pinned baseline")
    drawings = load_drawings()
    expected_assets = dict(publication_urls(catalog, drawings, videos))
    actual_assets = {item["url"]: item["role"] for item in manifest["assets"]}
    if len(actual_assets) != len(manifest["assets"]) or actual_assets != expected_assets:
        raise ValueError("Manifest must cover every catalog part, indexed drawing, preview, guide and evidence file")
    asset_bytes = sum(verify_asset(item) for item in manifest["assets"])
    transfer=json.loads((ROOT/"validation/transfer-motion.json").read_text())
    if (transfer.get("status")!="pass" or transfer.get("sampled_max_intersection_mm3",1)>1e-5
            or transfer.get("source_blend_sha256")!=hashlib.sha256((ROOT/"media/character-assembly.blend").read_bytes()).hexdigest()
            or transfer["continuous_conditions"]["vertical_tongue_sweep_intersection_mm3"]>1e-5):
        raise ValueError("Transfer-path evidence is stale or reports an animated collision")
    bom_tool_total=validate_bom_categories(catalog,(ROOT/"docs/bom.csv").read_bytes())
    for suffix in ("md","html"):
        validate_guide_tool_angles(catalog,(ROOT/f"docs/howto.ja.{suffix}").read_text())
    html_files = [ROOT / "index.html"] + [ROOT / f"docs/{name}.html" for name in GUIDE_NAMES]
    prose_files = html_files + [ROOT / "README.md", ROOT / "templates/index.html"]
    prose_files += [ROOT / spec["captions"] for spec in VIDEO_ASSETS.values()]
    prose_files += [ROOT / f"docs/{name}.md" for name in GUIDE_NAMES]
    prose_files += [ROOT / f"drawings/{name}" for name, _, _ in drawings]
    for path in prose_files:
        text, label = path.read_text(), str(path.relative_to(ROOT))
        assert_no_active_adhesive(text, label)
        maximum = (parameters["release_tool"]["max_initial_push_mm"]
                   if path == ROOT / "index.html" or path.name in ("howto.ja.md", "howto.ja.html") else None)
        assert_manufacturing_guidance(text, label, maximum)
    parsed = {}
    for path in html_files:
        parser = Links()
        parser.feed(path.read_text())
        parsed[path.resolve()] = parser
    checked_links = 0
    for path, parser in parsed.items():
        for value in parser.links:
            url = urlsplit(value)
            if url.scheme in ("https", "http", "mailto"):
                continue
            if url.scheme or url.netloc or unquote(url.path).startswith("/") or "\\" in unquote(url.path):
                raise ValueError(f"Nonrelative local link in {path.name}: {value}")
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            target.relative_to(ROOT)
            if not target.is_file():
                raise FileNotFoundError(f"Broken published link in {path.name}: {value}")
            if url.fragment and target in parsed and unquote(url.fragment) not in parsed[target].ids:
                raise ValueError(f"Missing page anchor: {value}")
            checked_links += 1
    with zipfile.ZipFile(ROOT / "native/character-tribute.FCStd") as native:
        if not {"Document.xml", "GuiDocument.xml"} <= set(native.namelist()):
            raise ValueError("The FreeCAD native file is not a saved native document with view metadata")
    if not (ROOT / "media/character-assembly.blend").read_bytes().startswith(b"BLENDER"):
        raise ValueError("The Blender artifact has an invalid native header")
    with zipfile.ZipFile(ROOT / "downloads/print-pack.zip") as archive:
        if validate_bom_categories(catalog,archive.read("docs/bom.csv"))!=bom_tool_total:
            raise ValueError("ZIP and published BOM tool quantities differ")
        files = {part["mesh"] for part in catalog["parts"]} | {"docs/bom.csv"}
        if set(archive.namelist()) != files | {"PRINT-README.txt"} or len(archive.namelist()) != len(files) + 1:
            raise ValueError("Print pack does not contain exactly the current masters, BOM and instructions")
        for url in files:
            if archive.read(url) != project_asset_path(url).read_bytes():
                raise ValueError(f"Print pack contains a stale file: {url}")
        note = archive.read("PRINT-README.txt").decode()
        assert_no_active_adhesive(note, "PRINT-README.txt")
        assert_manufacturing_guidance(note, "PRINT-README.txt", parameters["release_tool"]["max_initial_push_mm"])
        if note != print_pack_readme(catalog, parameters):
            raise ValueError("Print pack instructions/counts do not match T2")
    private_markers = [str(Path.home()).encode(), b"copilot-worktrees", b"session-state", b"clipboard.png"]
    scanned = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (not path.is_file() or any(p in (".venv-docs", "__pycache__", "frames", "previews", "browser-profile") for p in relative.parts)
                or path.suffix in (".log", ".FCBak") or path.name.endswith((".blend1", ".FCStd1"))):
            continue
        content = path.read_bytes()
        if path.suffix in (".FCStd", ".zip"):
            with zipfile.ZipFile(path) as archive:
                content = b"\n".join(archive.read(name) for name in archive.namelist())
        if path.name != "check_release.py" and any(marker in content for marker in private_markers):
            raise ValueError(f"Private source/path marker in public deliverable: {relative}")
        scanned += 1
    report = {"status": "pass", "scope": "static_publication_integrity", "revision": catalog["revision"],
              "manufacturing_revision": catalog["manufacturing_revision"], **browser,
              "relative_assets": len(manifest["assets"]), "asset_bytes": asset_bytes,
              "html_local_links_checked": checked_links, "public_files_privacy_scanned": scanned,
              "native_file_signatures": True, "archive_stl_count": len(catalog["parts"]),
              "all_asset_hashes_match": True, "source_photo_distributed": False,
              "bom_tool_column_total":bom_tool_total,"guide_tool_angles_match_catalog":True,
              "native_transfer_path_verified":True,
              "adhesive_required": False, "all_parts_removable": True,
              "independent_retention_review": manifest["independent_retention_review"],
              "physical_fit_tested": False, "thread_durability_tested": False, "tipping_tested": False,
              "videos": videos,
              **catalog_counts(catalog)}
    (ROOT / "validation/release.json").write_text(json.dumps(report, indent=2) + "\n")
    print("RELEASE_CHECK_PASS", report)


if __name__ == "__main__":
    main()
