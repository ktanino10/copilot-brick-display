# 再生成とソースの扱い / T2

## 入力・出力の関係

T2はユーザー確認済みの無接着・全パーツ着脱／再組立方式です。T1の接着方式は却下しました。
`parameters.json` がモザイク・捕捉枠・裏蓋・印刷ねじ・台座の入力です。
`shared-lock.json` は共通コネクター・カード・試験片の固定参照（`WITHDRAWN-PRIVACY-REVISION`）です。
`scripts/build.py` は実FreeCAD/OpenCASCADEを使い、FCStd、STEP、印刷用STL、`catalog.json` を出力します。
カタログの部品ID・色・個数・配置・工程から、部品表、図、Blender、サイト用manifestを生成します。
**生成済みのカタログを手編集しません。** `assembly` / `coupon` / `tool` を区別し、
治具の必要数には `tool_quantity` を使います。試験片・治具を完成品の配置数へ足しません。
`tool_target_xy` / `tool_tip_rotation_deg` は各色部品を取り出す接触位置・先端回転の正本です。

共有ファイルは、同じリポジトリ内の正本をSHA256照合して使用します。
まだ正本が統合されていない作業ブランチでは、同じリポジトリの固定Gitオブジェクトを読みます。
別の作業フォルダーを読んだり実行したりしません。どちらも無ければ明示的に失敗します。
共有ジオメトリーを自作の近似コネクターで置き換えません。

## 実行環境と再生成の順番

既存の生成環境はFreeCAD 1.1.3、Blender 5.1.1、FFmpeg/ffprobe 8.1、macOSです。
異なる版ではネイティブAPI・フォント・メッシュの差を再確認してください。
Qt offscreenではOpenGLビュー操作を行わず、保存後のネイティブ再読込は別の純Appプロセスで行います。
画面上のプレビューがなくても、保存・再読込した実BRepを検査しています。

以下はリポジトリのルートで実行します。実行ファイルの場所は自分のインストールに合わせてください。
別の長時間レンダーが動いている場合は、時間帯を分けます。他人のプロセスは終了しません。
CAD・検査→図面／BOM→Blender／動画／GLB→図面プレビュー→公開生成→リリース／ブラウザー検査の順です。
同じ版のデータがそろう前に `publish.py` を実行して、T1とT2の出力を混在させないでください。

## CAD・STL・検査

```bash
export FREECAD_RESOURCES=/Applications/FreeCAD.app/Contents/Resources
export PYTHONPATH="$FREECAD_RESOURCES/lib"
export QT_QPA_PLATFORM=offscreen
export PYTHONDONTWRITEBYTECODE=1

"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/test_retention.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/build.py
python3 projects/character-tribute/scripts/mesh_audit.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/verify_assembly.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/verify_fixture.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/verify_print_pose.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/verify_print_invariance.py
python3 projects/character-tribute/scripts/drawings.py
```

`build.py` はFCStdと組立STEPを保存した後、`verify_native.py` を別プロセスで実行します。
メッシュ検査はFreeCADの判定だけでなく、独立したbinary STLパーサーで各辺・頂点link・向き・体積を検査します。
文字検査はフォントを別作品へ置き換えず、実カードSTEPの浮き出し文字の頂面を測ります。
保持回帰テストは前後の正の止め面、先行部品を除いた後方への解除、押し棒の接触と残部の隙間を検査します。
EJECTORは `release_tool.max_initial_push_mm` の初動上限3.5 mmまで、先端だけでなく全工具形状を検査します。
その位置で工具を止め、露出した後ろのフランジをつまんで残りを引き抜く条件を、
`then_grip_rear_flange` と各解除レコードで保持します。9.5 mmの危険な過大押しで虹彩に衝突する回帰も残します。
部品単体の解除経路と、工具を進めてよい初動区間を同じものとして扱いません。
印刷ねじと雌側は本番関数を共用し、単なる円筒へのBoolean退化を受け入れません。
全対数はカタログの配置数 `n × (n−1) / 2` から決めます。過去版の固定対数は使いません。
`verify_fixture.py` は保存済みネイティブと実際のASSEMBLY-REST STEPで、前面下向きの作業台上の姿勢を検査します。
支持台の数、前枠との接触、他部品との非干渉、突出部と机の隙間を [fixture.json](../validation/fixture.json) に記録します。
公開manifestにはこのJSONと [検査スクリプト](../scripts/verify_fixture.py) の相対URL・hashも含めます。

### 製造是正T2-R1の印刷姿勢

T02とCAPTURE-FRAMEだけをX軸180°回転した印刷マスターへ変更します。
提供STL・個別STEPは**前面をベッドへ向ける方向設定済み**です。印刷者が追加回転する手順ではありません。
`parameters.json` の `print_orientations` と、生成カタログの `print_rotation_deg_xyz` /
`print_orientation` に記録します。他部品の印刷姿勢は変更しません。
配置の `raw_position_mm` / `raw_rotation_deg_xyz` は元の配置値を保持します。
提供印刷マスターを組立へ戻す際は、逆回転を織り込んだ有効配置を使い、raw値をそのまま重ねて適用しません。

`verify_print_pose.py` は保存済み印刷STEPの最初の接地断面と後続層の投影を検査し、
旧姿勢のような「4ボスだけが接地し、パネルがZ8 mmから始まる」状態を除外します。
[print-pose.json](../validation/print-pose.json) は接地証拠であり、全オーバーハングや実物ねじの印刷保証ではありません。
組立配置には印刷回転の逆を反映し、[print-pose-invariance.json](../validation/print-pose-invariance.json) で
基準 `6e065f5` から完成状態の形状・配置が変わらないことを照合します。逆変換を二重に適用しません。
公開処理はこれらのJSONと検査スクリプトをmanifestへ含めます。是正の独立受容は自動付与しません。

図面生成は基本6枚のファイル名を維持し、追加ページを許可します。
`drawings/index.json` の形式は次のとおりです（配列には全ページを列挙します）。

```json
{
  "revision": "T2",
  "sheets": [
    {"file": "assembly-isometric.svg", "title": "完成図", "subtitle": "CAD ASSEMBLY"}
  ]
}
```

`publish.py` の `DRAWINGS` はこの目録から導出します。ページ一覧を公開コードに重複手入力しません。
目録中の各 `name.svg` には `media/drawings/name.png` が必要です。
基本ページの欠落・重複・フォルダー外への参照・T2以外の目録はエラーにします。

## Blenderと動画

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --threads 1 --python-exit-code 1 \
  --python projects/character-tribute/scripts/blender_scene.py

/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --threads 1 --python-exit-code 1 \
  --python projects/character-tribute/scripts/render_frames.py

python3 projects/character-tribute/scripts/encode_video.py

/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --threads 1 --python-exit-code 1 \
  --python projects/character-tribute/scripts/export_glb.py
```

`blender_scene.py` は印刷用STLを読み、mmからBlenderのmへ単位換算し、
印刷回転の逆を含むカタログの組立配置を一度だけ適用します。
これは印刷用STLのスケール変更ではありません。カタログの配置と色を共有します。
同じ.blendに実際の組立用 `Assembly` と分解用 `Disassembly` の2シーンを保存します。
各シーンに独立した位置・表示キーフレームと工程マーカーが必要です。
組立工程は前枠1、通常インサート2、白目／白バッジ3、虹彩／M4、瞳5、裏蓋6、ねじ7、台座8、ドック9、カード10。
分解はねじを回して抜く→裏蓋→瞳／虹彩／白目、M／白バッジなど、実際に先行部品を除く順を表します。
ねじは軸移動だけでなく回転を連動させます。動画で立てた姿勢を使う場合は、
実作業は2個のASSEMBLY-RESTで前面を保護して前面下向きで行うことを字幕で明示します。
両動画・字幕とtool-access図には、初動押し最大3.5 mm→工具を止める→フランジをつまんで残りを引き抜く、
という区別を明示します。押し棒を全行程の取り外し工具として描写しません。
再読込・完成配置・組立と分解の進行を確認してから、各シーンの範囲に従ってPNGをレンダーします。
動画と字幕は `media/assembly.mp4` / `media/assembly.ja.vtt`、
`media/disassembly.mp4` / `media/disassembly.ja.vtt` に分けます。片方の映像を両方のファイル名で配布しません。

動画は全フレームをdecodeし、異なる組立・分解状態を持つことも確認します。
**尺・fps・解像度・フレーム数は固定しません。** 公開処理は `validation/video.json` の
主レコードを組立、`disassembly` エントリーを分解として個別に読みます。
それぞれの `encoded_stream`（`duration`、`avg_frame_rate`、`width`、`height`）と
`frame_count`（またはストリームの `nb_frames`）、`decoded_frames` / `decode_errors` を照合します。
フレーム数が両方にある場合は一致が必要です。主レコードの `status: pass` に加え、
分解側にstatusを記録する場合もpassでなければ公開できません。
双方の `mp4_sha256` が実ファイルと一致する必要があります。片方だけの検査結果は受け入れません。
Blenderのシーン別検査は `scenes.Assembly` / `scenes.Disassembly` の各 `frame_count` / `fps`、
または主レコードと `disassembly` の同名フィールドがある場合に各動画と照合します。
日本語はMP4の既定mov_text字幕とWebVTTで提供します。
この実行環境のFFmpegはdrawtextフィルターを持たないため、焼き込み字幕とはしていません。

GLBは **Assemblyシーンの完成フレームだけ**を明示して出力する標準3Dプレビューです。
Disassemblyの終端状態を出力しません。Y-up・m単位で、印刷用STLの代用品ではありません。
BlenderのPythonエラーが終了コード0にならないよう、実行時に`--python-exit-code 1`を付けます。

BlenderがUI用に保存するFile BrowserのローカルディレクトリーはAPIで相対化します。
PNGは文字メタデータだけを取り除き、画素を変更しません。
バイナリのネイティブ形状を偽物へ置き換える処理ではありません。

## ソースだけの回帰確認

生成途中でも、以下はファイルを生成せず、標準Pythonで実行できます。

```bash
python3 -B projects/character-tribute/scripts/test_site.py --source-only
```

カタログ由来の集計・治具数量、追加図面、独立した2動画の可変仕様と字幕、相対URLとhash、
無接着の公開状態、T1の作業指示の拒否、方向設定済みマスター、初動押しの上限と停止・つかみへの切替、
HTMLテンプレートの部品行を検査します。
これはCAD、実動画、Chrome表示、物理試験や独立レビューの代わりではありません。

## ガイドHTML・manifest・公開検査

HTML変換だけにPython-Markdownを使用します。ルートの依存関係は変更しません。
以下の専用環境がなければ作成し、必要な依存がない場合だけrequirementsをインストールします。
**現在のmacOS Chromeは専用プロファイルでDevTools接続前にクラッシュし、実ブラウザー検査は環境起因でblockedです。**
図面PNGの生成にはChromeを使わず、インストール済みの標準 `rsvg-convert` を呼ぶ
`scripts/render_drawing_previews.py` を使います。下記のブラウザー検査だけは正常なChrome環境向けで、
起動できないままpassと記録しません。

```bash
python3 -m venv projects/character-tribute/.venv-docs
projects/character-tribute/.venv-docs/bin/pip install \
  -r projects/character-tribute/requirements-docs.txt
projects/character-tribute/.venv-docs/bin/pip install \
  -r projects/character-tribute/requirements-test.txt

python3 -B projects/character-tribute/scripts/render_drawing_previews.py

PYTHONDONTWRITEBYTECODE=1 projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/publish.py
PYTHONDONTWRITEBYTECODE=1 projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/test_site.py

PYTHONDONTWRITEBYTECODE=1 projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/publish.py
python3 -B projects/character-tribute/scripts/check_release.py
```

ブラウザー実行後の再公開は、更新された `validation/web.json` のhashを反映するためです。
[render_drawing_previews.py](../scripts/render_drawing_previews.py) は図面目録にあるCAD由来SVGから対応するPNGを生成し、
[drawing-previews.json](../validation/drawing-previews.json) に元SVGと出力PNGそれぞれのhashを記録します。
このrsvg-convertによる変換はChrome検査の代替ではありません。
`web.json` は理由付きの `blocked_environment` / `browser_tested: false` を保ち、
統合担当がLinux CIのフルChromeで後続検査を行います。

文書・テンプレートの修正後、必要な生成物と正直なブラウザー状態レコードがそろえば、静的公開検査は次で実行できます。

```bash
PYTHONDONTWRITEBYTECODE=1 projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/test_site.py --source-only
projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/publish.py
python3 -B projects/character-tribute/scripts/check_release.py
```

ガイド本文の正本はMarkdownです。HTMLを直接編集しないでください。
図面更新後は `render_drawing_previews.py` でPNGとその証拠をそろえてから公開します。
実ブラウザー検査の `test_site.py` は既存Chromeを使用します。必要なら環境変数`CHROME`で実行ファイルを指定できます。
ブラウザーを追加ダウンロードしたり、普段使うブラウザープロファイルを操作したりしません。
公開ページには軽いPNGプレビューを使い、寸法入りの元SVGへリンクしています。
Chrome検査は全カタログ部品行、実際の色区分・治具数量、両プレイヤーの動画メタデータと字幕URL、図面目録を照合します。
ソース回帰・SVG変換・静的リンク検査の合格を、ブラウザー実表示の合格へ読み替えません。
`check_release.py` のpassは `scope: static_publication_integrity` であり、`browser_status` と `browser_tested` を別記します。

`publish.py` はガイド4本、入口HTML、全マスター入りZIP、manifestを生成します。
印刷パックの説明と公開メタデータにも `adhesive_required: false`、`all_parts_removable: true` を反映します。
manifestの `videos.assembly` / `videos.disassembly` に各MP4・字幕・シーン名・実測仕様を記録します。
従来の `video` は `videos.assembly` と同じ内容で残し、両MP4と両WebVTTを相対URL／hash一覧に含めます。
`manufacturing_revision`、各部品の印刷回転・向き・原点、`release_tool` の初動上限・フランジ把持条件も記録します。
独立保持レビューは常に `pending_coordinated_review` から開始します。
最終公開生成後、統合担当だけが同じ独立レビュアーによる確認を経て `accepted_digital_only` を設定できます。
`check_release.py` はその入力値を検査結果へ写すだけで、承認しません。
再度 `publish.py` を実行すると既定のpendingに戻るため、レビュー対象の最終hashをそろえてから統合してください。

サイトのファイル参照は相対URLのみで、各種データはこのプロジェクトフォルダー内にあります。
統合担当はフォルダー全体をPagesの同じ相対配置に置き、入口`index.html`へリンクできます。
ソース写真、私有の絶対パス、セッション履歴、認証情報、試し書きのログは公開しません。
実物の嵌合・ねじ寿命・転倒は未検証のままです。プリンターへの自動送信・自動操作は行いません。
