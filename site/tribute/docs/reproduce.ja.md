# 再生成とソースの扱い

## 入力・出力の関係

`parameters.json` が自作レリーフ・台座の入力です。`shared-lock.json` は共通コネクター・カード・試験片の固定参照です。
`scripts/build.py` は実FreeCAD/OpenCASCADEを使い、FCStd、STEP、印刷用STL、`catalog.json` を出力します。
カタログの部品ID・色・個数・配置・工程から、部品表、図、Blender、サイト用manifestを生成します。
生成済みのカタログだけを編集してSTLと食い違わせないでください。

共有ファイルは、同じリポジトリ内の正本をSHA256照合して使用します。
まだ正本が統合されていない作業ブランチでは、同じリポジトリの固定Gitオブジェクトを読みます。
別の作業フォルダーを読んだり実行したりしません。どちらも無ければ明示的に失敗します。
共有ジオメトリーを自作の近似コネクターで置き換えません。

## 実行確認した環境

FreeCAD 1.1.3、Blender 5.1.1、FFmpeg/ffprobe 8.1、macOS。
異なる版ではネイティブAPI・フォント・メッシュの差を再確認してください。
Qt offscreenではOpenGLビュー操作を行わず、保存後のネイティブ再読込は別の純Appプロセスで行います。
画面上のプレビューがなくても、保存・再読込した実BRepを検査しています。

以下はリポジトリのルートで実行します。実行ファイルの場所は自分のインストールに合わせてください。
別の長時間レンダーが動いている場合は、時間帯を分けます。他人のプロセスは終了しません。

## CAD・STL・検査

```bash
export FREECAD_RESOURCES=/Applications/FreeCAD.app/Contents/Resources
export PYTHONPATH="$FREECAD_RESOURCES/lib"
export QT_QPA_PLATFORM=offscreen
export PYTHONDONTWRITEBYTECODE=1

"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/test_relief.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/build.py
python3 projects/character-tribute/scripts/mesh_audit.py
"$FREECAD_RESOURCES/bin/python" projects/character-tribute/scripts/verify_assembly.py
python3 projects/character-tribute/scripts/drawings.py
```

`build.py` はFCStdと組立STEPを保存した後、`verify_native.py` を別プロセスで実行します。
メッシュ検査はFreeCADの判定だけでなく、独立したbinary STLパーサーで各辺・頂点link・向き・体積を検査します。
文字検査はフォントを別作品へ置き換えず、実カードSTEPの浮き出し文字の頂面を測ります。

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

`blender_scene.py` はSTLを実寸で読み、mmからBlenderのmへ単位換算するだけです。
これは印刷用STLのスケール変更ではありません。カタログの配置と色を共有します。
保存する.blendには実際の位置・表示キーフレームと工程マーカーがあります。
再読込・完成時の全配置・アニメーション進行を確認した後、504枚のPNGをレンダーします。

動画はH.264 640×640 / 24fps / 21秒です。全フレームをdecodeし、異なる組立状態を持つことも確認します。
日本語はMP4の既定mov_text字幕とWebVTTで提供します。
この実行環境のFFmpegはdrawtextフィルターを持たないため、焼き込み字幕とはしていません。

GLBは完成フレームを明示して出力する標準3Dプレビューです。Y-up・m単位で、印刷用STLの代用品ではありません。
BlenderのPythonエラーが終了コード0にならないよう、実行時に`--python-exit-code 1`を付けます。

BlenderがUI用に保存するFile BrowserのローカルディレクトリーはAPIで相対化します。
PNGは文字メタデータだけを取り除き、画素を変更しません。
バイナリのネイティブ形状を偽物へ置き換える処理ではありません。

## ガイドHTML・manifest

HTML変換だけにPython-Markdownを使用します。ルートの依存関係は変更しません。

```bash
python3 -m venv projects/character-tribute/.venv-docs
projects/character-tribute/.venv-docs/bin/pip install \
  -r projects/character-tribute/requirements-docs.txt
projects/character-tribute/.venv-docs/bin/python \
  projects/character-tribute/scripts/publish.py
python3 projects/character-tribute/scripts/check_release.py
```

ガイド本文の正本はMarkdownです。HTMLを直接編集しないでください。
図面のPNGプレビューを更新する場合は、同じ専用環境へ `requirements-test.txt` をインストールし、
`scripts/test_site.py --drawings-only` を実行してから `publish.py` を再実行します。
この処理は既存のChromeをheadlessで使用します。必要なら環境変数`CHROME`で実行ファイルを指定できます。
ブラウザーを追加ダウンロードしたり、普段使うブラウザープロファイルを操作したりしません。
公開ページには軽いPNGプレビューを使い、寸法入りの元SVGへリンクしています。

サイトのファイル参照は相対URLのみで、各種データはこのプロジェクトフォルダー内にあります。
統合担当はフォルダー全体をPagesの同じ相対配置に置き、入口`index.html`へリンクできます。
ソース写真、私有の絶対パス、セッション履歴、認証情報、試し書きのログは公開しません。
