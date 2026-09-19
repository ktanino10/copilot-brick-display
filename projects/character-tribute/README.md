# @YOUR-USERNAME — キャラクター記念楯

ユーザー提供のキャラクター画像をもとに、新しく設計した色別の段差レリーフです。
写真を貼った模型ではなく、**20種類・29個の印刷部品**で構成します。バッグ・人物・元写真は含みません。

**設計寸法：幅176 × 奥行96 × 高さ201.6 mm。**
20cm級の卓上品を目標に、160 × 160 mmの背板と、9.6 mmの台座＋32 mmの支持部を選びました。
接続ピッチは8 mmのままです。STL全体を拡大・縮小して大きさを調整しません。

![CAD形状から作成した完成像](media/finished.png)

```text
@YOUR-USERNAME
Same icon, New adventures
github.com/YOUR-USERNAME
```

この3行は**本体とは別の交換式カード**です。カード・ドック・背板と台座の接続は接着しません。
色レリーフは、緩い位置決め用の角ピンと少量のPLA対応接着剤を使う構成です。
小さな色部品まで無接着で保持する仕様ではありません。

## 使うファイル

| 内容 | ファイル |
| --- | --- |
| 製作ページ | [index.html](index.html) |
| 日本語の作り方 | [HTML](docs/howto.ja.html) / [Markdown](docs/howto.ja.md) |
| FreeCAD完成モデル | [character-tribute.FCStd](native/character-tribute.FCStd) |
| 組立STEP | [character-tribute.step](native/character-tribute.step) |
| 印刷用32種類（本体20＋試験片12） | [meshes/](meshes/) |
| 個別部品STEP | [native/parts/](native/parts/) |
| 完成図・三面図・分解図・部品図・接続図 | [drawings/](drawings/) |
| 色別・個数・配置・工程の部品表 | [bom.csv](docs/bom.csv) |
| Blenderネイティブ組立アニメーション | [character-assembly.blend](media/character-assembly.blend) |
| 組立動画（21秒・24fps） | [assembly.mp4](media/assembly.mp4) / [日本語字幕](media/assembly.ja.vtt) |
| サイト統合用の相対URL一覧 | [manifest.json](manifest.json) |
| 実施した検査と未確認事項 | [検証範囲](docs/validation.ja.md) / [機械検査JSON](validation/assembly.json) |

MP4は実Blenderシーンの504フレームから生成しています。日本語字幕は埋め込み字幕とWebVTTです。
字幕を表示できないプレイヤーでは、製作ページか作り方と一緒に参照してください。
動画の速度は印刷時間・接着剤の硬化時間を表しません。

## 正本と再生成

入力は [parameters.json](parameters.json)、共有部品の固定参照は [shared-lock.json](shared-lock.json) です。
生成される [catalog.json](catalog.json) が、各STL、色、個数、配置、工程をつなぐ正本です。
図面・Blender・部品表・サイトはこのカタログを読み、形状を描き直しません。

共有スタッド、ドック、文字カード、8種類のブロック嵌合試験片は、固定した共通ジェネレーターを
そのまま呼び出します。独自の代替コネクターではありません。フォントはB612 Mono Bold、
ライセンスは [OFL](resources/fonts/OFL.txt) を同梱しています。

[再生成手順](docs/reproduce.ja.md) を参照してください。共通ソースのSHA256不一致や不足はエラーにします。
FreeCADの保存済み形状を手動で変更した場合は、カタログからの再生成結果と混在させないでください。

## デジタル検証と物理試験は別です

実際のFCStd/STEP再読込、閉じたmanifold STL、正の体積、寸法・配置、406組のBRep干渉、
支持接点、挿入方向、256 mm造形範囲と8 mmブリム、文字の細さを確認しています。
**PLAと市販ABSブロックのclutch、反り、接着強度、転倒・落下への耐性は未試験です。**
本体より先に試験片を印刷し、実物に強く押し込まないでください。

成人向けの非公式な個人記念品です。防護用の盾ではなく、子ども向け玩具の安全認証もありません。
任天堂・LEGO・GitHubの公認品とは称しません。寸法の出典と採用候補の区別は
[sources.json](sources.json) に記載しています。
