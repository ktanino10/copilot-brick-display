"""Version local normal-model assets; leave the entire frozen tribute subtree untouched."""

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from design import ROOT


def main():
    revision = json.loads((ROOT / "design/parameters.json").read_text())["revision"]
    suffixes = {".js", ".css", ".json", ".png", ".svg", ".mp4", ".vtt", ".pdf", ".zip",
                ".csv", ".FCStd", ".step", ".stl", ".blend", ".3mf"}
    def version(match):
        attribute, quote, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or url.path.startswith("tribute/") or Path(url.path).suffix not in suffixes:
            return match.group()
        query = dict(parse_qsl(url.query))
        query["rev"] = revision
        value = urlunsplit(("", "", url.path, urlencode(query), url.fragment))
        return f"{attribute}={quote}{value}{quote}"
    for page in (ROOT / "site").glob("*.html"):
        page.write_text(re.sub(r'\b(src|href|poster)=(["\'])([^"\']+)\2', version, page.read_text()))
    print("Versioned only normal-model HTML assets:", revision)


if __name__ == "__main__":
    main()
