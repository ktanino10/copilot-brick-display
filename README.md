# Copilot Brick Display — public template

**[3案を回して見る・ダウンロード](https://ktanino10.github.io/copilot-brick-display/?rev=5.0-legible-plaques)**
 · **[作り方](docs/build.ja.md)** · **[Fork → Issue → AI → PRで文字を変える](docs/customize.ja.md)**

**別PCで印刷する方へ：[色別ファイルの選び方と、黒→白の手動色替え](https://ktanino10.github.io/copilot-brick-display/guide.html?guide=separate-color-2026-09-19#print-another-pc)**
— A/B/Cを1案だけ選び、最初は試験片から。銘板・右ロゴの白い部分は一体レリーフで、途中の色替えが必要です。

**印刷した部品がどこに入るか分からない方へ：[ファイル → slot → 組立場所の対話3Dガイド](https://ktanino10.github.io/copilot-brick-display/assembly-guide/index.html)**
— 印刷順と組立順は違います。Bの最初は **`B-black-02.3mf` のslot 3 → `B-001`**。
[3D仕分け図・最初の台座アニメと使い方](docs/assembly.ja.md) ／ [Bのオフライン版](site/assembly-guide/B-offline.zip)。

![Bの印刷プレート内slot 3と最初の組立B-001を結ぶ実STL表示](site/assembly-guide/media/B-first-base.png)

**[実物の制作記録：Bの台座と前面モジュール（2026-09-23）](docs/build-log.ja.md)**

個人向けB版の台座が組み上がった報告と、識別情報を伏せた実写真です。全150部品の完成・保持力の合格や、
公開の汎用文字版・A/Cの実物成功を示すものではありません。

公開リビジョンは **`5.0-legible-plaques`**。黒い台座5段、大きい2行、正面右のロゴ、
無接着で交換できる前面部品を持つ非公式の卓上オブジェです。
公開の銘板は実際のCAD形状として次の仮表示を使います。実在の個人プロフィールではありません。

> Same icon, New adventures<br>
> github.com/USER

**[文字を印刷しやすくした改訂内容・実CAD比較](docs/lettering.ja.md)**：
2行目を全案10 mm、白文字を1.2 mm高へ。孔・開口・字間を広げ、背面の取付けと本体68種類は維持しました。
`USER`は実プロフィールへのリンクではない短い仮表記です。まず[文字の小試験片](site/downloads/lettering-coupons.zip)を選んだ案で印刷してください。

個人値はgitignore対象のローカルJSONへ分離できます。公開してよい値を使うforkでは、
Issue・PR・native・画像・動画・Actions artifact・Pagesにも表示されることを確認して、
明示的な公開承認モードを選びます。secretへ入れるだけでは生成物も秘密になる、とは扱いません。

## 同じ8 mmピッチ、3つの配置

| 案 | 完成寸法 W×D×H / mm | 組込部品数 | 特徴 |
| --- | --- | ---: | --- |
| A MINI RELIEF | 143.8 × 64.2 × 187.4 | 91 | 浅い顔、14段＋黒台座5段 |
| B DESK CLASSIC | 191.8 × 80.2 × 238.6 | 150 | 標準型、19段＋黒台座5段 |
| C DISPLAY SCULPT | 239.8 × 112.2 × 286.6 | 228 | 厚い側面、24段＋黒台座5段、最下段2分割 |

寸法は台座と最上部スタッド込み、部品数は銘板・ロゴ・3個のキーパー込み、試験片は別です。
文字以外の68種類のSTL、各案の配置・幅・高さ・接続寸法を維持しています。文字が0.4 mm厚くなった分だけ完成奥行きが増えています。
完成Cが256 mmより高くても、分割した各印刷部品はP1Sの公称造形体積内に収まります。
STLの一律拡大・縮小はしません。AMS・電子部品・接着剤・追加購入金具は不要です。

| 案 | FreeCAD | STEP | 印刷セット | 寸法・組立図 | Blender | 実組立動画 |
| --- | --- | --- | --- | --- | --- | --- |
| A | [FCStd](site/downloads/A/A.FCStd) | [STEP](site/downloads/A/A.step) | [ZIP](site/downloads/A/print-kit.zip) | [PDF](site/downloads/A/drawings.pdf) | [blend](site/downloads/A/A.blend) | [MP4](site/media/A-assembly.mp4) |
| B | [FCStd](site/downloads/B/B.FCStd) | [STEP](site/downloads/B/B.step) | [ZIP](site/downloads/B/print-kit.zip) | [PDF](site/downloads/B/drawings.pdf) | [blend](site/downloads/B/B.blend) | [MP4](site/media/B-assembly.mp4) |
| C | [FCStd](site/downloads/C/C.FCStd) | [STEP](site/downloads/C/C.step) | [ZIP](site/downloads/C/print-kit.zip) | [PDF](site/downloads/C/drawings.pdf) | [blend](site/downloads/C/C.blend) | [MP4](site/media/C-assembly.mp4) |

文字とロゴは独立した実レリーフです。黒から白へ、銘板は2.4 mm、ロゴは2.8 mm層後に手動色替えします。
キーパーを上へ6 mm、手前へ32 mm以上外して脇に置き、そのモジュールを45 mm以上上抜きして交換します。
3D分解100%は下側を下へ、上側を上へ広げ、段間は18.2 mm以上。表示用移動で、物理シミュレーションではありません。

## 作る前に

- [7個だけ、段階を分けて試す](docs/trial.ja.md) — 別試験の「扱いにくい・穴が塞がる」という失敗観察を反映。形状を変えず代表部品を少量選択。
- [初心者向けの作り方](docs/build.ja.md) — 条件照合、レイヤープレビュー、男女coupon、仕分け、組立・交換・停止条件。
- [設計の根拠](docs/design.md)／[再生成](docs/rebuild.md)／[公開・privateの文字変更](docs/customize.ja.md)。
- [公開テンプレートの検査記録](site/downloads/validation.json) — native、mesh、描画、配布物とprivate出力経路の検査を区別。

**実物の嵌合・keeper保持・PLA強度・耐久性・転倒は未試験です。**
個人向けBの台座・前面部品の写真報告は[制作記録](docs/build-log.ja.md)に追加しましたが、測定による物理試験とは区別しています。
0.4 mm本体／0.2 mm文字は未実機検証のbaselineです。まず試験片を刷り、閉塞・つかみにくさ・着座不良があれば全数印刷を止めます。
無理押し・打撃・穴を一個ずつ削ることを完成キットの前提にしません。成人向けの屋内装飾品で、玩具安全認証はありません。

## プライバシーと権利

個人向けの旧配布と関連する到達可能な公開履歴を清掃し、元データはprivateに保管しています。
未選択の個別バリエーションは公開配布していません。
**GitHub側の旧SHAオブジェクトや外部キャッシュまで完全消去できたとは主張しません。**
[清掃範囲・残存限界・再混入防止](docs/privacy.md)を参照してください。

GitHub・LEGO・Bambu Labの公認商品ではありません。包括ライセンスは未設定です。
フォント・Three.js等の[noticeと権利条件](docs/licensing.md)を確認してください。
