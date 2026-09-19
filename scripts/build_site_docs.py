"""Publish the maintained documentation without keeping a second hand-edited copy."""

import html
import json
import re
import shutil
from pathlib import Path

import markdown

from design import ROOT


def links(value):
    replacements = {
        "../site/": "", "../design/": "downloads/",
        "build.ja.md": "guide.html", "design.md": "technical.html",
        "rebuild.md": "rebuild.html", "licensing.md": "notices.html",
        "trial.ja.md": "trial.html",
    }
    def replace(match):
        url = match.group(1)
        for old, new in replacements.items():
            if url.startswith(old):
                url = new + url[len(old):]
                break
        return f'href="{html.escape(url, quote=True)}"'
    return re.sub(r'href="([^"]+)"', replace, value)


def main():
    for source, target, title in [
        ("build.ja.md", "guide.html", "作り方"),
        ("design.md", "technical.html", "寸法の根拠と設計"),
        ("rebuild.md", "rebuild.html", "編集・再生成"),
        ("licensing.md", "notices.html", "権利・依存ライブラリ"),
        ("trial.ja.md", "trial.html", "7個の段階試作・閉塞を先に確認"),
    ]:
        body = links(markdown.markdown((ROOT / "docs" / source).read_text(),
                                      extensions=["tables", "fenced_code", "toc"]))
        guide = ""
        if target == "guide.html":
            guide = ('<p class="doc-note"><strong>全数印刷の前に。</strong> '
                     '<a href="trial.html?guidance=trial-2026-09-19">既存coupon → 7個の実部品 → 選択案の台座・前面へ</a>。'
                     '閉塞・つかみにくさ・着座不良があれば止めます。7個は完成品の合格試験ではありません。</p>'
                     '<section class="stage-guide" aria-label="各案の番号付き組立図">'
                     '<h2>選んだ案の工程図</h2><p>各図の配置番号はBOM・3D・動画と共通です。手前は図の下です。</p>'
                     '<label for="guide-model">案を選ぶ</label><select id="guide-model"><option>A</option><option selected>B</option><option>C</option></select>'
                     '<label for="guide-step">工程を選ぶ</label><select id="guide-step"></select>'
                     '<figure><img id="guide-drawing" alt="選択工程の配置図" src="drawings/B/step-01.svg"></figure>'
                     '<p><a id="guide-pdf" href="downloads/B/drawings.pdf">全工程のPDFを保存 ↓</a></p></section>')
        page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Brick Portrait</title><link rel="stylesheet" href="style.css"><link rel="icon" href="icon.svg"></head>
<body><header class="site-header"><a class="brand" href="./">BRICK<br>PORTRAIT</a>
<nav><a href="./#workbench">3Dとダウンロード</a><a href="guide.html">作り方</a><a href="technical.html">設計</a></nav></header>
<main class="document"><div class="doc-nav"><a href="./">← 模型のページへ</a><a href="guide.html">作り方</a><a href="rebuild.html">再生成</a></div>
{guide}{body}</main><footer class="site-footer"><a class="brand" href="./">BRICK PORTRAIT</a>
<p>非公式・成人向け卓上オブジェ。実物の嵌合、保持力、耐久性、転倒は未検証です。</p>
<a href="notices.html">権利・依存ライブラリ</a></footer>
{"<script type='module' src='guide.js'></script>" if guide else ""}</body></html>'''
        (ROOT / "site" / target).write_text(page)
    for name in ["parameters.json", "interface.json", "sources.json", "revision3-approval.json", "revision3-invariants.json"]:
        shutil.copyfile(ROOT / "design" / name, ROOT / "site/downloads" / name)
    shutil.copyfile(ROOT / "resources/fonts/barlow-condensed/OFL.txt", ROOT / "site/vendor/Barlow-OFL.txt")
    from stamp_release import main as stamp
    stamp()
    print("Published maintained guides, staged trial instructions, technical design and notices.")


if __name__ == "__main__":
    main()
