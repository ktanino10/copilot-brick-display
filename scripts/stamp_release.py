"""Version local normal-model assets; leave the entire frozen tribute subtree untouched."""

import json
import html
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from design import ROOT


def main():
    revision = json.loads((ROOT / "design/parameters.json").read_text())["revision"]
    catalog = json.loads((ROOT / "design/catalog.json").read_text())
    index_path = ROOT / "site/index.html"
    page = index_path.read_text()
    page = re.sub(r'(<meta name="design-revision" content=")[^"]*(")', rf'\g<1>{revision}\2', page)
    page = re.sub(r'(<small id="published-revision">)[^<]*(</small>)', rf'\g<1>{revision}\2', page)
    standard = next(model for model in catalog["models"] if model["id"] == "B")
    dimensions = lambda model: " × ".join(str(value) for value in model["actual_mm"])
    page = re.sub(r'(<dd id="model-dimensions">).*?( <span>mm</span></dd>)',
                  rf'\g<1>{dimensions(standard)}\2', page)
    models = {model["id"]: model for model in catalog["models"]}
    def comparison(match):
        return match[1] + dimensions(models[match[2]]) + match[3]
    page = re.sub(r'(<article><a href="\?model=([ABC])#workbench".*?<dt>実寸 / mm</dt><dd>)[^<]*(</dd>)',
                  comparison, page)
    for number, text in enumerate(catalog["message"]["lines"], 1):
        page = re.sub(rf'(<(?:strong|span) id="message-line-{number}"[^>]*>)[^<]*(</(?:strong|span)>)',
                      lambda match: match[1] + html.escape(text) + match[2], page)
    page = re.sub(r'(id="base-front-preview"[^>]* alt=")[^"]*(")',
                  r'\1実CAD由来の汎用B台座。右ロゴと短い仮表示USER\2', page)
    index_path.write_text(page)
    suffixes = {".html", ".js", ".css", ".json", ".png", ".svg", ".mp4", ".vtt", ".pdf", ".zip",
                ".csv", ".FCStd", ".step", ".stl", ".blend", ".3mf"}
    def version(match):
        attribute, quote, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or url.path.startswith("tribute/") or (
                Path(url.path).suffix not in suffixes and url.path != "./"):
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
