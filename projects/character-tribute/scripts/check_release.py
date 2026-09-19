"""Check publication links, native signatures, hashes, archive contents and privacy."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import zipfile

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


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    manifest = json.loads((ROOT / "manifest.json").read_text())
    expected_message = ["@YOUR-USERNAME", "Same icon, New adventures", "github.com/YOUR-USERNAME"]
    if catalog["message"] != expected_message or manifest["message"] != expected_message:
        raise ValueError("Confirmed message changed")
    if manifest["physical_fit_tested"] or manifest["safety_certified"]:
        raise ValueError("Publication must not claim unperformed physical tests or certification")
    asset_bytes = 0
    for item in manifest["assets"]:
        if urlsplit(item["url"]).scheme or item["url"].startswith("/") or ".." in Path(item["url"]).parts:
            raise ValueError(f"Asset is not a project-local relative URL: {item['url']}")
        content = (ROOT / item["url"]).read_bytes()
        if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Publication asset changed since manifest generation: {item['url']}")
        asset_bytes += len(content)
    html_files = [ROOT / "index.html"] + sorted((ROOT / "docs").glob("*.html"))
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
            if url.scheme or url.netloc or url.path.startswith("/"):
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
        for part in catalog["parts"]:
            if archive.read(part["mesh"]) != (ROOT / part["mesh"]).read_bytes():
                raise ValueError(f"Print pack contains a stale mesh: {part['id']}")
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
    report = {"status": "pass", "relative_assets": len(manifest["assets"]), "asset_bytes": asset_bytes,
              "html_local_links_checked": checked_links, "public_files_privacy_scanned": scanned,
              "native_file_signatures": True, "archive_stl_count": len(catalog["parts"]),
              "all_asset_hashes_match": True, "source_photo_distributed": False,
              "physical_fit_tested": False}
    (ROOT / "validation/release.json").write_text(json.dumps(report, indent=2) + "\n")
    print("RELEASE_CHECK_PASS", report)


if __name__ == "__main__":
    main()
