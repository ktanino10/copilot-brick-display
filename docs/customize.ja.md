# 自分用の文字へ変更する — Fork → Issue → AI → PR

公開デフォルトの `github.com/YOUR-USERNAME` は仮表示です。実在する相手のプロフィールとしてリンクしていません。
通常A/B/Cの5段台座、右ロゴ、8 mmピッチ、無接着の交換構造を保ち、文字銘板だけを変更することから始めます。

**公開してよい文字かどうかを先に決めてください。**
公開Issue・コメント・PR・commit・CAD・画像・動画・Actions artifact・Pagesへ入れた名前やhandleは公開され得ます。
GitHub Actionsのsecretに入れても、生成した文字形状や画像、ログ、PRまで隠れるわけではありません。

## 1. 公開ルートと非公開ルート

| 目的 | 選ぶ方法 | 実値を置く場所 |
| --- | --- | --- |
| 本人の同意等があり、表示を公開してよい | 自分のpublic forkでIssue／PRを使う | 公開になると理解した上で、forkの設定とIssueへ |
| 氏名・handleを公開したくない | ローカルのgit管理外入力、または権利・条件を守った独立private repo | `.private/personalization.json`など。公開Issueにはplaceholderだけ |

**公開repoのforkは公開で、forkだけをprivateへ変更することはできません。**
private repoであっても、そのPagesが公開になる場合があります。repoとサイトの公開範囲は別々に確認してください。
モデル・フォント・ロゴの権利条件を確認し、未設定の包括ライセンスを勝手に補いません。

## 2. 自分のforkを準備する

GitHubで **Fork → Owner／名前 → 必要ならdefault branch only → Create fork** を選びます。
自分のforkをcloneし、IssueとPRの対象も自分のforkにします。個別カスタムをupstreamへ勝手にPRしません。
IssuesタブやActionsが使えない場合は、自分のrepo設定・権限・組織policyを確認します。

Copilot cloud agentを使うには、対象repoへのwrite accessと、そのrepoでの有効化が必要です。
対象の有料Copilotプラン、Business／Enterpriseの管理者policy、repoのopt-outを確認してください。
実行にはActions minutesとAI creditsが使われます。ここで新しいAppや外部サービスを自動インストールする必要はありません。

## 3. コピペできるIssue本文

Issueフォーム「表示文字のカスタマイズ」も利用できます。以下はすべて仮の値です。
公開が許されない実名・個人handleは、この本文へ入れないでください。

```text
目的:
自分のfork内で、通常モデルの交換銘板を変更する。

対象モデル: B（A / B / Cから選ぶ）
表示行1: YOUR DISPLAY NAME
表示行2: github.com/YOUR-USERNAME
任意のhandle: 必要なら行1または行2に明示する。自動で3行目を追加しない。
公開区分: placeholderのみ / 公開してよい値 / 実値は非公開入力

公開してよい値の場合:
- 本文・commit・PR・CAD・描画・Actions artifact・Pagesにも表示されると理解している。
- 自分のforkのdesign/parameters.jsonのmessage.linesだけを入力正本として変更する。
- design/publication-policy.jsonをpublic_personalizationにし、
  public_text_approved:trueとするのは、公開が許された場合だけ。

非公開入力の場合:
- 公開Issueはplaceholderのままにする。
- 実値はローカルの.private/personalization.jsonで扱い、
  private出力を公開branch/PR/artifact/Pagesへ入れない。

変更しないもの:
5段黒台座、右ロゴ、8 mmピッチ、取付け寸法、無接着保持、
顔の形・色、上下分解の完成配置。

必須:
- 入力はコードではなく文字列データとして検査する。
- 不明glyph、長すぎる行、最小stroke不足、領域超過は明示停止する。
  無音切捨てや、横方向を押し潰す縮小で無理に収めない。
- 通常は銘板だけを再生成。取付け寸法を変える必要があれば理由とpreviewを示して相談。
- FreeCAD/Blender/ffmpegをpreflightし、実行したものだけ実行済みと記載。
- 公開カスタムでは、その変更が見えるnative/STEP/STL/図面/BOM/ZIP/
  Blender画像・動画/Web表示を同じ入力・配置へ一致させる。
- 実CAD由来の正面／拡大preview、保存後の再読込、mesh・文字・保持経路・リンクを確認。
- 既存の未変更部品をhash確認して再利用し、不要な全形状再設計をしない。
- 実物の嵌合・保持・強度・転倒は未試験のまま。試験片を先に刷る手順を保つ。
- 自分のforkのmain宛にPRを作る。reviewとmerge前に勝手にPagesを更新しない。
```

## 4. Copilotへ割り当てる

Issueの **Assignees → Copilot** を選び、必要なら **Optional prompt** を追加します。
対象repoとbase branchは、write accessがある自分のforkのmainを選びます。
タイトル・本文・割当時点までのコメント・追加指示が入力として扱われます。

**割当後にIssueへ追記しても、自動で追加作業が始まるとは限りません。**
作成されたPRへ `@copilot` を付けて追加指示を伝えます。
個人値の公開範囲が変わる場合は、その前に止めて確認してください。

## 5. 他のAIへ同じ依頼を渡す

GitHub統合済みのClaude／Codex等は、account／organizationのpolicyで有効になっていて
UIに表示される場合に、Issue割当・Agents UI・PR mentionを使用できます。提供状態はpublic previewを含みます。
partner-built Agent Appsは、owner側へのApp導入・agent機能有効化・該当policy・初回OAuth等が前提です。

**任意のbot名をAssigneesへ入力すれば動く、とは限りません。**
未統合のAIやローカルIDE assistantには、上のIssue本文とこのrepoの再生成手順を渡し、
自分のforkでbranchを作成してPRへ戻すよう依頼します。private値を扱う場合は、利用先のデータ管理policyも確認します。

## 6. ローカルで非公開の銘板を実際に生成する

公開repoのままでも、入力と出力をgitignore対象の`.private/`へ置けます。

```bash
mkdir -p .private
cp design/personalization.private.example.json .private/personalization.json
```

このローカルJSONだけを編集します。厳密なschemaは`schema_version`、`visibility`、`model`、`lines`です。
`visibility`は`private`、modelはA/B/C、linesは正確な2行です。
現在の文字セットは英字・数字と指定された基本記号です。日本語など未対応glyphは勝手な代替や脱落にせず停止します。
必要ならフォントと字形の対応を別途検討してください。

FreeCADに対応するPython executableとmodule directoryを自分の環境で指定して実行します。
実際のパスを公開Issueへ貼る必要はありません。

```bash
FREECAD_USER_HOME="$PWD/.private/freecad-profile" QT_QPA_PLATFORM=offscreen \
  PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/personalize_plate.py \
  --config .private/personalization.json --output .private/generated
```

実際の`plate.FCStd`、`plate.step`、mm単位`plate.stl`、CAD由来`plate.svg`、
private manifestが`.private/generated/B/`などに保存されます。
既存出力があれば上書きせず停止します。別の値を試すときは新しいprivate出力先を指定します。
公開済みの形状や入力正本は変更しません。

既存のgenericな完成FCStdがローカルにあれば、`--assembly`で銘板だけを差し替えたprivateな完成FCStd／STEPも保存できます。
**privateコマンドは公開Web画像・動画を個人化しません。** それらは引き続きgenericな表示です。
private生成物をGitHubへ添付した時点で秘密が保たれるとは限らないため、public PRへ持ち込まないでください。

## 7. 公開カスタムの再生成と、環境が足りない場合

公開が承認されたforkでは、`design/parameters.json`の`message.lines`と
`design/publication-policy.json`の明示承認を入力にします。
[再生成手順](rebuild.md)のFreeCAD → STL/図面 → Blender → 文書/パッケージ → 検査を実行します。
最初に変更した銘板の実幅・高さ・strokeと正面previewを確認します。

cloud agentはGitHub Actions基盤の一時環境で動きますが、FreeCAD／Blenderが存在する保証はありません。
ツールがなければ **BLOCKED: native regeneration not executed** と明記し、
必要なコード・入力・実行手順をPRに残します。承認済みのローカル環境で上の実生成を行い、
保存／再読込／動画decodeの証拠とともにPRへ戻してください。
拡張子だけのnative、未実行generator、別レンダラーの絵を実成果物として納品しません。

## 8. PRを確認し、自分のPagesへ

文字の正確さ、公開してよいデータだけか、0%完成形と分解経路、実寸、
CAD・STL・画像・動画・ZIPの一致、試験片と未検証事項を人が確認します。
PRは自分のforkのmainへmergeします。個人カスタムをupstreamへ勝手に送らないでください。

既存workflowを利用する場合は、forkの **Settings → Pages → Build and deployment → Source = GitHub Actions** を選びます。
一律に`/docs`や別branch sourceへ変更する手順ではありません。
Actionsの有効化・deployment permissions・環境policy・fork自身のrepo URLとPages subpathを確認し、
`scripts/verify_published.py --base https://YOUR-OWNER.github.io/YOUR-REPOSITORY/`で実公開ファイルを照合します。
履歴・画像・CADに実値を残したくない場合は、ここでpublic Pagesへ進みません。

## 公式文書（2026-09-19確認）

- [IssueをCopilotへ割り当てる](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-on-github#assigning-an-issue-to-copilot)
- [cloud agentの利用条件・実行環境](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent)
- [GitHub統合の第三者coding agents](https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents)
- [Agent Appsの前提条件](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-agent-apps)
- [Forkの作成](https://docs.github.com/en/pull-requests/how-tos/work-with-forks/fork-a-repo)／[Forkの公開範囲](https://docs.github.com/en/pull-requests/reference/forks)
- [Pagesの公開元設定](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
