# 検証範囲と残る物理試験 / T2

## 動画・手順・部品表の追加整合

MR-T2-03は旧保存nativeのAssembly392 / Disassembly185で約263.892 mm³を再現し、
完成CADを変更せず動画の移動経路を是正しました。
[実native経路検査](../validation/transfer-motion.json) は、整数・小数フレームの最大干渉0、
水平移動中の高さ余裕18 mm、正対後の垂直舌掃引干渉0を記録します。
閉じたレリーフ全体は同じZ補間で剛体移動し、台座は机上から浮かせません。
[旧問題の再現](../validation/transfer-regression.json) と [差分render範囲](../validation/transfer-video-update.json) も保存します。

BADGE-Wの工具角度はカタログと同じ90°です。Markdown/HTMLの工具表を正本と比較します。
BOMの工具数列はcategory=toolだけを数え、couponは0、合計3を公開CSVとZIP内CSVへ共通のassertで確認します。
これらの一致も、実物試験や最終独立受入を代替するものではありません。と残る物理試験 / T2

これは無接着・全パーツ着脱可能な**デジタル試作**の検証範囲です。
ユーザーによる方式の選択は確認済みで、T1の接着方式は却下しました。
実機の製造承認、独立レビューへの合格、玩具認証、互換性保証とは別です。

部品・色・数量・配置・工程は [catalog.json](../catalog.json) が唯一の正本です。
現行T2の集計は組立42種類・78個、試験片15種類、治具2種類、合計59マスターです。
EJECTORは1個、ASSEMBLY-RESTは2個で、試験片・治具を完成品の78個へ足しません。

## 証拠の読み方

下表はT2公開時に照合する検査項目です。生成途中のフォルダーでは過去版のJSON・動画・図面が残る場合があります。
**同じT2のカタログ、配置数、ファイルhashに一致しない検査結果を合格証として流用しません。**
`check_release.py` は数量・全対数・メディアhash・図面目録・公開ファイルhashの不一致をエラーにします。
同じ独立レビュアーからHIGH/CRITICAL指摘はなく、MEDIUMの印刷姿勢と工具過大押しを製造是正T2-R1で扱います。
下記の追加証拠やソース修正だけで、これらの是正が独立受容済みになったとは宣言しません。

| 項目 | T2で照合する内容 | 証拠 |
| --- | --- | --- |
| FreeCAD / STEP | 保存後に別の純Appプロセスで再読込。現行の78配置・78 solids、全59種類の個別STEP | [native.json](../validation/native.json) |
| STLの閉体 | 現行59マスターについて各辺2面、向き、頂点link、単一shell、正の符号付き体積 | [meshes.json](../validation/meshes.json) |
| 外形・共通接続 | 176 × 96 × 201.6 mm、固定8 mm、共通版WITHDRAWN-PRIVACY-REVISIONのMSG-DOCK/CARD | [assembly.json](../validation/assembly.json) / [固定参照](../shared-lock.json) |
| ベッド範囲 | 256 mmの造形範囲と片側8 mmブリム。メッシュ偏差0.05 mmを考慮したbounds照合 | [meshes.json](../validation/meshes.json) |
| 印刷接地 | T02 / CAPTURE-FRAMEをX軸180°回転して前面下にした保存印刷STEP。接地断面と後続層の投影を確認。提供STLは方向設定済み | [print-pose.json](../validation/print-pose.json) |
| 組立形状の不変性 | 印刷回転の逆を組立配置へ反映。6e065f5の完成形と全配置を照合。他部品の印刷姿勢は変更しない | [print-pose-invariance.json](../validation/print-pose-invariance.json) |
| BRep全対 | `n × (n−1) / 2`。現行78個なら3003組。過去版の対数は非適用 | [assembly.json](../validation/assembly.json) |
| 正の捕捉 | 保存ネイティブの全69色部品で前後・横方向の止め面を確認。通常部品は名目0.8 mm／片側へ寄った最小0.6 mmの掛かり | [保持回帰テスト](../scripts/test_retention.py) / [assembly.json](../validation/assembly.json) |
| 色部品の取り外し | 蓋と先行部品を除いた部品単体の後方0.2 / 1 / 4 / 12 / 24 mm経路。工具の許可ストロークではなく、初動後のフランジ把持・引抜きを含む | [保持回帰テスト](../scripts/test_retention.py) / [assembly.json](../validation/assembly.json) |
| ねじの成立 | 真の螺旋山と雌側切削。単なる円筒へのBoolean退化を回帰テストで拒否。4本の実経路で直線引抜きの衝突と螺旋解除、背面の頭へのアクセスを確認 | [保持回帰テスト](../scripts/test_retention.py) / [assembly.json](../validation/assembly.json) |
| 押し棒 | 全EJECTOR形状を0..3.5 mmの初動サンプルで検査。最大3.5 mmで工具を止め、フランジをつまんで残りを引き抜く。先端だけの接触検査ではない | [カタログの押し位置・回転](../catalog.json) / [assembly.json](../validation/assembly.json) |
| 前面下向きの支持治具 | 保存ネイティブ＋実ASSEMBLY-REST STEPで支持台2個の衝突0・前枠だけへの接触を確認。構造前面は机上12 mm、目などの突出部の最小隙間は約5.6 mm | [fixture.json](../validation/fixture.json) / [検査スクリプト](../scripts/verify_fixture.py) |
| 楯・カードと文字 | 直立時の楯とカードの上方取り外し。カード88 × 24 × 2 mm＋文字0.6 mm、溝88.4 × 2.4 mm。直線ストローク最小0.4105 mm／文字島最小外形0.4812 mm→0.2 mmノズル | [assembly.json](../validation/assembly.json) |
| Blender / GLB | カタログと同じ配置・完成外形・hash。同じ.blend内のAssembly / Disassemblyに実キーフレーム。GLBはAssembly完成時だけを出力したm・Y-upの表示用 | [blender.json](../validation/blender.json) / [glb.json](../validation/glb.json) |
| 両動画 | assembly.mp4とdisassembly.mp4を個別に全フレームdecode。各々の尺・fps・解像度・フレーム数・hashを検査JSONから取得。各動画の日本語字幕とWebVTT | [video.json](../validation/video.json) |
| 公開内容 | 図面目録の全SVGと対応PNG、相対URL、SHA256、一括パックの全マスター、T1作業指示の除去、私有パスと元写真の非配布 | [release.json](../validation/release.json) |
| ブラウザー実表示 | 現在はChromeが専用プロファイルでDevTools接続前にクラッシュする環境起因のblocked。新しいブラウザー合格を主張しない | [web.json](../validation/web.json) |
| SVGプレビュー | render_drawing_previews.pyが標準rsvg-convertでCAD由来SVGをPNGへ変換。元SVG・出力PNGのhashを記録。ブラウザーでのレイアウト・再生検査ではない | [drawing-previews.json](../validation/drawing-previews.json) / [生成スクリプト](../scripts/render_drawing_previews.py) |

ネイティブ78 solids、全59メッシュ、保存ネイティブの3003組と保持・解除経路のT2検査は合格しています。
曲面のSTEP再読込による体積積分差は、検査JSONで宣言した有界の数値許容差で照合します。
支持治具の配置は作業台上の印刷原点 `[-84, -136, 0]` / `[68, -136, 0]` mmです。
これは前枠局所座標の支持パッドx≈±76、図柄y=24..136 mmとは異なる座標表現です。
支持と隙間の証拠は剛体CADの結果であり、実物の反り・机の水平・治具の安定性を保証しません。
動画・図面・公開データなどが再生成中である間は、この幾何検査だけを根拠に「全公開検査完了」としません。
`validation/video.json` の主レコードが組立、`disassembly` が分解です。双方の全フレームdecodeとMP4のhashが必要です。
図面のページ数は固定しません。[drawings/index.json](../drawings/index.json) に基本6枚と追加ページを列挙します。

## デジタル検証の限界

CADはプリンターの誤差、PLAの弾性、ねじ山の積層強度・摩耗、手指の動きを再現していません。
0.2 mmの遊びと前後の止め面を持つ捕捉は摩擦保持の仮定ではありませんが、
名目形状で捕捉できることと、印刷物が軽い力で外せることは別です。
目の瞳→虹彩→白目、バッジのM→白という先行取り外し条件を満たした経路検査です。
指定された離散位置・ねじの連動経路の確認であり、全連続時刻の弾性や人間工学の証明ではありません。
**EJECTORを瞳と一緒に9.5 mmまで進めると虹彩に約0.8112 mm³の衝突が生じます。**
この反例を残し、工具は初動だけ最大3.5 mmで停止させます。露出したフランジをつかんで残りを引き抜き、
押し棒で全行程を通しません。上限以内でフランジをつかめなければ中止します。
印刷接地の是正も、全ての橋・オーバーハング・ねじの実印刷品質を認証するものではありません。

静的公開検査のpassはファイル・hash・リンク等の整合性についてです。
`scope: static_publication_integrity` と別記したブラウザー状態を読み、
ソース回帰やlibrsvg変換だけで新しいChrome検査が通ったことにしません。
統合担当による正常なChrome環境での後続検査が必要です。

幾何学的重心の計算は均質な完全ソリッドの参考値で、実際の充填率・密度・反りを含みません。
過去版の重心や転倒余裕の数値はT2へ転記しません。
測定した重量・印刷時間・保持力・繰り返し寿命・転倒角の値はありません。
造形範囲内でも、スライサーの除外領域・サポート・実際のプレート配置は別途確認が必要です。

## 実物で残る確認

1. 本番と同じPLA・色・ノズル・層高・温度・補正を記録し、THREAD-C40から実物T04で試験。
2. CAPTURE-FRAME/COVERと実物IN-W-1x1・T04で保持、意図した解除、再組立を確認。
3. FIT-*で市販品→印刷品、印刷品→市販品、印刷品同士を別々に確認。T90/T91と本番の長い舌も確認。
4. 手回しねじの抵抗・白化・割れ・摩耗と、取り外した部品のフランジを確認。寿命やトルクの合格値は未設定。
5. 2個のASSEMBLY-RESTによる前面保護、EJECTOR初動最大3.5 mmで停止してフランジをつまむ作業性、指定順の取り外しを実物で確認。
6. 平らな机で反り・傾き・脱落を確認。転倒・振動・長期使用への耐性は未試験のままと明記。

公開メタデータは `adhesive_required: false`、`all_parts_removable: true`、
`physical_fit_tested: false`、`thread_durability_tested: false`、`tipping_tested: false` とします。
0.4/0.2 mmのPLA設定は未印刷の出発点であり、自動プリンター操作は行いません。

## 独立保持レビュー

既定値は **`independent_retention_review: pending_coordinated_review`** です。
統合担当だけが、共通部品・元の3案と調整した**同じ独立レビュアー**によるT2の確認後、
`accepted_digital_only` を設定できます。公開ジェネレーターやこの文書は承認を付与しません。
その状態になっても実物の嵌合・耐久性・転倒試験は未検証のままです。
[T2の変更とレビュー境界](t2-change-review.ja.md) も参照してください。
