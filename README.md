# Copilot Brick Display / Brick Portrait

**[3案を回して見る・ダウンロード](https://ktanino10.github.io/copilot-brick-display/)**
 · **[日本語の作り方](https://ktanino10.github.io/copilot-brick-display/guide.html)**

**現行リビジョン：`3.0-five-course-front`。黒い台座5段・大きい2行・正面右の独立ロゴ。**

5色のPLAを、一段ずつ組み立てる卓上オブジェ。Bambu Lab P1S、0.4 mm / 0.2 mmノズルを想定し、
色別に印刷して組みます。AMS・電子部品・モーター・電池・配線・接着剤は不要です。
スタッドと裏面の空洞・チューブ・屋根リブを持つ実体CADで、装飾の溝だけを付けた塊ではありません。

**デジタル設計の納品と、実物の製作検証は別です。実物との嵌合・保持力・強度・転倒は未試験です。**
本体の前に、[小さなオス／メス試験片](site/downloads/fit-coupons.zip)から始めてください。
市販LEGOへの互換保証・製造安全認証・玩具安全認証はしていません。

## 同じ8 mmピッチ、異なる3つの配置

寸法は台座と最上部スタッドを含む、幅 × 奥行 × 高さです。部品数は銘板・ロゴ・3個の上止め込み、試験片は別です。

| 案 | 目標 / mm | CAD実寸 / mm | 部品 | デザイン |
| --- | --- | --- | --- | --- |
| A MINI RELIEF | 144 × 64 × 約188 | **143.8 × 63.8 × 187.4** | **91** | 16 mm厚の顔、14段＋台座5段 |
| B DESK CLASSIC | 192 × 80 × 約238 | **191.8 × 79.8 × 238.6** | **150** | 32 mm厚の顔、19段＋台座5段。標準型 |
| C DISPLAY SCULPT | 240 × 112 × 約288 | **239.8 × 111.8 × 286.6** | **228** | 48 mm厚の顔、24段＋台座5段。最下段は2分割 |

奥行きの説明はグリッドの名目値で、個々の部品外形は隙間分0.2 mm小さくなります。
**STLの倍率変更で作った3案ではありません。STLを拡大・縮小すると接続ピッチも変わります。**

## そのまま開ける成果物

| 案 | FreeCAD | STEP | 印刷STL・BOMセット | 寸法・組立PDF | Blender | 組立MP4 |
| --- | --- | --- | --- | --- | --- | --- |
| A | [A.FCStd](site/downloads/A/A.FCStd) | [STEP](site/downloads/A/A.step) | [ZIP](site/downloads/A/print-kit.zip) | [図面](site/downloads/A/drawings.pdf) | [A.blend](site/downloads/A/A.blend) | [動画](site/media/A-assembly.mp4) |
| B | [B.FCStd](site/downloads/B/B.FCStd) | [STEP](site/downloads/B/B.step) | [ZIP](site/downloads/B/print-kit.zip) | [図面](site/downloads/B/drawings.pdf) | [B.blend](site/downloads/B/B.blend) | [動画](site/media/B-assembly.mp4) |
| C | [C.FCStd](site/downloads/C/C.FCStd) | [STEP](site/downloads/C/C.step) | [ZIP](site/downloads/C/print-kit.zip) | [図面](site/downloads/C/drawings.pdf) | [C.blend](site/downloads/C/C.blend) | [動画](site/media/C-assembly.mp4) |

全71種類のSTLには8種類のスタッド試験片と4種類の前面キー溝試験片も含みます。
[全印刷部品の寸法図](site/downloads/part-drawings.pdf)、
[接続断面](site/drawings/interface.svg)、
[測定記録シート](site/downloads/fit-log.csv)、
各案の色別汎用3MFもサイトから取得できます。3MFは形状配置のみで、スライス済みデータやG-codeではありません。

FCStdは実FreeCADで保存した部品ID・色・配置・工程グループ付きのモデルです。
表示範囲が合わない場合はFreeCADの「全体表示」（V、F）を使います。
Blenderの最終配置は同じSTLとカタログに照合され、動画は実レンダーされた工程順の組立＋完成形の回転表示です。
動画を物理シミュレーションや保持力の試験として扱わないでください。

## 台座正面で、独立して交換できるメッセージとロゴ

黒台座を独立した9.6 mm段で5段、合計48 mmにしました。顔の形・配色は変えず38.4 mm上へ移動しています。
正面の左に大きな2行銘板、右に黒丸・白いGitHubマークの実レリーフを配置し、いずれも台座高の内側に納めました。
銘板2個・ロゴ1個の取り外せるキーパーで上抜けを止めます。先に該当キーパーを上へ外して手前へ逃がし、
モジュールを上に抜くことで別々に交換できます。接着剤や購入金具は使いません。
黒い裏面をベッドにして印刷し、銘板は2.4 mm、ロゴは2.8 mmの層後に白へ手動色替えします。AMSは不要です。

> Same icon, New adventures<br>
> github.com/YOUR-USERNAME

「分解して見る」の100%は、下側を下へ・上側を上へ広げます。本体・台座各段の隙間は18.2 mm以上です。
モジュールは先にキー溝から離脱させ、実際の表示範囲へカメラを合わせます。印刷形状を拡縮する操作や物理シミュレーションではありません。

## 作る前に読むもの

- **[作り方・印刷条件・試験・困ったとき](docs/build.ja.md)** — 初心者向けの全工程。PLAの脆さ、0.4 / 0.2 mm設定、色別BOM、組立順。
- **[設計の根拠と拘束式](docs/design.md)** — nominal寸法と印刷補正を分離。壁・チューブ・リブ・頭上余白・接続仕様。
- **[編集・再生成](docs/rebuild.md)** — 実FreeCAD、Blender、ffmpegを使って再生成する手順。
- **[要求との対応](design/requirements.json)** / **[一次・二次資料](design/sources.json)** / **[共通インターフェース](design/interface.json)**。
- **[デジタル検証記録](site/downloads/validation.json)** / **[今回の独立機械レビュー](validation/revision3-review.md)** — 何を確認し、何が未確認か。

正本は`design/parameters.json`と`scripts/design.py`、形状の生成元は`scripts/freecad_geometry.py`です。
派生するCAD・STL・寸法・BOM・工程・3D・Blenderを、別々の架空形状として手描きしていません。

## 境界・権利

並行設計の別作品`projects/character-tribute/`は、A/B/Cのバリエーションではありません。
ユーザーの確定要件は**小色レリーフまで無接着・全パーツ着脱可能**です。旧接着案は不採用で、
追加作品はT2-R1として、独立した機械・全出力のデジタルレビューを通過しました。
[追加作品の状態と境界](docs/tribute-release.md)を参照してください。
旧接着版の製作ダウンロードは取り下げたままです。原3案の無接着仕様は変わりません。
[追加作品のT2-R1](https://ktanino10.github.io/copilot-brick-display/tribute/)は、176 × 96 × 201.6 mm・78組込部品、
組立／分解の実動画と全59印刷マスターを持つ別ページです。公開はLinuxフルChrome検査の通過を条件とします。

成人向けの屋内装飾品です。小部品・破片、PLAの割れ・熱変形に注意し、子ども向け玩具として使わないでください。
市販品へ無理に押し込む、こじる、ハンマーで叩くことはしません。頭・ゴーグル・カードを持って運ばず、台座を両手で支えます。

非公式の自作モデルで、LEGO・GitHub・Bambu Labの公式商品ではありません。原写真、私有履歴、認証情報は含めていません。
プロジェクト全体の包括ライセンスは未設定です。[権利と依存ライブラリのnotice](docs/licensing.md)を参照してください。
役割分離と証拠付き引継ぎは[AI Hardware Engineering Team](https://github.com/ktanino10/ai-hardware-engineering-team)の考え方を参考にし、
元プロジェクトの回路・設計・共有台帳は変更していません。
