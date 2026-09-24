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
        "../web/assembly-guide/README.md": "https://github.com/ktanino10/copilot-brick-display/blob/main/web/assembly-guide/README.md",
        "build.ja.md": "guide.html", "design.md": "technical.html",
        "rebuild.md": "rebuild.html", "licensing.md": "notices.html",
        "trial.ja.md": "trial.html",
        "customize.ja.md": "customize.html", "privacy.md": "privacy.html",
        "assembly.ja.md": "assembly.html",
        "lettering.ja.md": "lettering.html",
        "build-log.ja.md": "build-log.html",
    }
    def replace(match):
        attribute, url = match.groups()
        for old, new in replacements.items():
            if url.startswith(old):
                url = new + url[len(old):]
                break
        return f'{attribute}="{html.escape(url, quote=True)}"'
    return re.sub(r'\b(href|src)="([^"]+)"', replace, value)


def main():
    for source, target, title in [
        ("build.ja.md", "guide.html", "作り方"),
        ("design.md", "technical.html", "寸法の根拠と設計"),
        ("rebuild.md", "rebuild.html", "編集・再生成"),
        ("licensing.md", "notices.html", "権利・依存ライブラリ"),
        ("trial.ja.md", "trial.html", "7個の段階試作・閉塞を先に確認"),
        ("customize.ja.md", "customize.html", "Fork・Issue・AIで表示文字を変更"),
        ("privacy.md", "privacy.html", "公開テンプレートとプライバシーの境界"),
        ("assembly.ja.md", "assembly.html", "印刷ファイルから組み立てる3Dガイド"),
        ("lettering.ja.md", "lettering.html", "銘板の印刷しやすさ・小文字試験片"),
        ("build-log.ja.md", "build-log.html", "制作記録 — Bの台座から顔下部へ"),
    ]:
        body = links(markdown.markdown((ROOT / "docs" / source).read_text(),
                                      extensions=["tables", "fenced_code", "toc"]))
        guide = ""
        if target == "guide.html":
            guide = ('<p class="doc-note"><strong>刷ったパーツはどこに入る？</strong> '
                     '<a href="assembly.html">ファイル → slot → 組立場所の3Dガイド</a>。'
                     'Bの最初はblack-02のslot 3。印刷順は組立順ではありません。</p>'
                     '<p class="doc-note"><strong>別PCで、色別に印刷する方へ。</strong> '
                     '<a href="#print-another-pc">A/B/Cの保存先・色ごとの3MF・黒→白の手動交換を順に確認</a>。'
                     '1案だけ選びます。公開データは汎用placeholderで、個人用ファイルは含みません。</p>'
                     '<p class="doc-note"><strong>全数印刷の前に。</strong> '
                     '<a href="trial.html?guidance=trial-2026-09-19">既存coupon → 7個の実部品 → 選択案の台座・前面へ</a>。'
                     '閉塞・つかみにくさ・着座不良があれば止めます。7個は完成品の合格試験ではありません。</p>'
                     '<section class="stage-guide" aria-label="各案の番号付き組立図">'
                     '<h2>選んだ案の工程図</h2><p>各図の配置番号はBOM・3D・動画と共通です。手前は図の下です。</p>'
                     '<p id="guide-data-error" role="alert" hidden></p>'
                     '<label for="guide-model">案を選ぶ</label><select id="guide-model"><option>A</option><option selected>B</option><option>C</option></select>'
                     '<label for="guide-step">工程を選ぶ</label><select id="guide-step"></select>'
                     '<figure><img id="guide-drawing" alt="選択工程の配置図" src="drawings/B/step-01.svg"></figure>'
                     '<p><a id="guide-pdf" href="downloads/B/drawings.pdf">全工程のPDFを保存 ↓</a></p></section>')
        page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Brick Portrait</title><link rel="stylesheet" href="style.css"><link rel="icon" href="icon.svg"></head>
<body><header class="site-header"><a class="brand" href="./">BRICK<br>PORTRAIT</a>
<nav><a href="./#workbench">3Dとダウンロード</a><a href="guide.html">作り方</a><a href="customize.html">文字を変える</a></nav></header>
<main class="document"><div class="doc-nav"><a href="./">← 模型のページへ</a><a href="guide.html">作り方</a><a href="rebuild.html">再生成</a></div>
{guide}{body}</main><footer class="site-footer"><a class="brand" href="./">BRICK PORTRAIT</a>
<p>非公式・成人向け卓上オブジェ。実物の嵌合、保持力、耐久性、転倒は未検証です。</p>
<a href="notices.html">権利・依存ライブラリ</a></footer>
{"<script type='module' src='guide.js'></script>" if guide else ""}</body></html>'''
        (ROOT / "site" / target).write_text(page)
    for name in ["parameters.json", "interface.json", "sources.json", "publication-policy.json", "public-template-invariants.json", "personalization.private.example.json"]:
        shutil.copyfile(ROOT / "design" / name, ROOT / "site/downloads" / name)
    shutil.copyfile(ROOT / "resources/fonts/barlow-condensed/OFL.txt", ROOT / "site/vendor/Barlow-OFL.txt")
    shutil.copyfile(ROOT / "validation/lettering.json", ROOT / "site/downloads/lettering.json")
    from stamp_release import main as stamp
    stamp()
    print("Published maintained guides, staged trial instructions, technical design and notices.")


if __name__ == "__main__":
    main()
