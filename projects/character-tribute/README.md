# @YOUR-USERNAME — キャラクター記念楯 / T2

ユーザー提供のキャラクター画像から、新しく設計した色別の段差モザイクです。
**ユーザーは「無接着・全パーツ取り外し／再組立可能」を選択・確認済みです。**
T1の接着方式は却下しました。`046a48e` は過去の比較用基準であり、現行の製作仕様ではありません。
接着剤・テープ・熱かしめ・溶着は使いません。追加購入金具も不要です。

**デジタル試作です。実物の嵌合・ねじ寿命・保持力・転倒・手での作業性は未検証です。**
方式のユーザー確認と、独立保持レビューや物理試験への合格を区別してください。
独立保持レビューは統合担当が同じ独立レビュアーと調整します。この文書では承認を付与しません。

## 大きさと構成

設計寸法は **幅176 × 奥行96 × 高さ201.6 mm**。固定8 mmの共通接続は変更していません。
STL全体を拡大・縮小して大きさを調整しません。

現行T2の [catalog.json](catalog.json) の部品区分と配置を集計すると、
**組立42種類・78個、試験片15種類、治具2種類、印刷マスター合計59種類**です。
治具は `EJECTOR` ×1、`ASSEMBLY-REST` ×2。試験片・治具は完成品の組込数に含みません。
色部品は通常インサート61個、左右の3部品式の目6個、2部品式バッジ2個、計69個です。
製造是正T2-R1ではT02とCAPTURE-FRAMEの提供STL・個別STEPを**前面下向き**に変更しました。
すでに方向設定済みなので追加で回転しません。他部品の印刷姿勢と、逆配置後の完成形は変更していません。

- `T02` 前枠の肩と、`T03` 裏蓋で色部品のフランジを前後から捕捉します。摩擦だけで保持する設計ではありません。
- `T04` は交換可能な独自の印刷粗ねじ **TR11.2-P3.2**。4本で裏蓋を固定します。標準M12金具ではありません。
- `T01` 台座、共通 `MSG-DOCK` / `MSG-CARD` は従来の共通仕様のままです。
- 裏蓋を外した後、色部品はすべて後方へ取り出せます。目は瞳→虹彩→白目、バッジはM→白の順です。
- EJECTORは**初動だけ最大3.5 mm**で工具を止め、露出した後ろのフランジをつまんで残りを引き抜きます。
  押し棒だけで最後まで押し出しません。是正内容は [変更記録](docs/t2-change-review.ja.md) を参照してください。

![CAD形状から作成した完成像（実物写真ではありません）](media/finished.png)

```text
@YOUR-USERNAME
Same icon, New adventures
github.com/YOUR-USERNAME
```

この3行は本体とは別の交換式カードだけに入ります。文面・大文字・comma・URLは変更しません。
バッグ・人物・元写真は配布しません。

## 使うファイル

| 内容 | ファイル |
| --- | --- |
| 製作ページ | [index.html](index.html) |
| 日本語の作り方・分解方法 | [HTML](docs/howto.ja.html) / [Markdown](docs/howto.ja.md) |
| FreeCAD完成モデル / 組立STEP | [FCStd](native/character-tribute.FCStd) / [STEP](native/character-tribute.step) |
| 印刷マスター / 個別STEP | [meshes/](meshes/) / [native/parts/](native/parts/) |
| 色・数量・配置・工程 | [catalog.json](catalog.json) / [部品表CSV](docs/bom.csv) |
| 全図面と図面目録 | [drawings/](drawings/) / [index.json](drawings/index.json) |
| Blenderネイティブ（Assembly / Disassemblyの2シーン） | [character-assembly.blend](media/character-assembly.blend) |
| 組立動画 / 日本語字幕 | [assembly.mp4](media/assembly.mp4) / [assembly.ja.vtt](media/assembly.ja.vtt) |
| 分解動画 / 日本語字幕 | [disassembly.mp4](media/disassembly.mp4) / [disassembly.ja.vtt](media/disassembly.ja.vtt) |
| 両動画の仕様・全フレーム検査 | [video.json](validation/video.json) |
| サイト統合用相対URL・hash・試作状態 | [manifest.json](manifest.json) |
| 検証範囲 / T2変更とレビュー境界 | [検証](docs/validation.ja.md) / [変更記録](docs/t2-change-review.ja.md) |

同じ.blend内に実キーフレームを持つ `Assembly` と `Disassembly` があり、動画・字幕はそれぞれ別ファイルです。
各動画の尺・fps・フレーム数・解像度は動画検査JSONからサイトへ反映します。固定の尺や合算の長さを前提にしません。
GLBは `Assembly` の完成状態だけを出力します。
立てた表示姿勢は観察用です。実際は2個の `ASSEMBLY-REST` で前枠の外側リムを支持し、
顔・目の突出部を荷重から守って前面下向きで組みます。動画の速度は印刷時間・実作業時間ではありません。

## 正本と再生成

入力は [parameters.json](parameters.json)、共通部品の固定参照は [shared-lock.json](shared-lock.json) です。
共通版 `WITHDRAWN-PRIVACY-REVISION` のスタッド、ドック、文字カード、`FIT-*` を使用します。
生成されたカタログが部品・色・数量・配置・工程の唯一の正本です。**カタログを手で編集しません。**
サイトの部品表・印刷パック・数量はこのカタログから、図面一覧は `drawings/index.json` から生成します。
フォントはB612 Mono Bold、ライセンスは [OFL](resources/fonts/OFL.txt) を同梱しています。

[再生成手順](docs/reproduce.ja.md) に従い、同じT2のCAD・図面・BOM・メディア・証拠をそろえてから公開します。
公開処理は `independent_retention_review: pending_coordinated_review` を出力し、独立承認を自動付与しません。

## まず試験片から

本体より先に `THREAD-C40` と別途印刷した実物 `T04`、`CAPTURE-FRAME/COVER` と実物 `IN-W-1x1` を試します。
台座舌の `T90/T91`、共通嵌合の `FIT-*` も本番の材料・色・ノズルで確認してください。
実機未検証の0.4/0.2 mm PLA設定を出発点とし、固い部品を無理に押し込みません。
自動でプリンターを操作・送信する仕組みはありません。

T2の保存FCStd/STEPの78配置と59種類のSTLは監査済みです。保存ネイティブの全対検査は、
カタログの `n × (n−1) / 2`（現行78個で3003組）に対応します。全69色部品の前後・横方向の止め面、
4本のねじの螺旋解除と直線引抜きの阻止、指定順の解除・押し棒接触などは対応する検査JSONで確認してください。
メディア・公開データも同じT2の証拠にそろえる必要があります。過去版の検査は流用しません。
デジタルの正の当たり面や抜き経路は、実物の耐久性を保証しません。

成人向けの非公式な個人記念品です。防護用の盾でも安全認証済みの子ども向け玩具でもありません。
任天堂・LEGO・GitHubの公認品とは称しません。寸法の出典と試作候補の区別は [sources.json](sources.json) を参照してください。
