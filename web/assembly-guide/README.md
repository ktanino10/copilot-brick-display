# Shared print-to-place guide

This UI renders actual STL geometry. It does not generate or change mechanical parts.
`scripts/build_assembly_guide.py` is a root-independent input adapter; the separate
`scripts/build_public_assembly_guides.py` wrapper enforces this repository's generic public policy.
Do not use the public wrapper for private data.

## Inputs and output

```bash
npm ci
npm run build:assembly-guide
.venv/bin/python scripts/build_assembly_guide.py \
  --catalog design/catalog.json \
  --assembly site/downloads/B/assembly.json \
  --plates site/downloads/B/plates/manifest.json \
  --mesh-root site/downloads \
  --plates-root site/downloads/B/plates \
  --runtime build/assembly-guide/runtime.js \
  --template-dir web/assembly-guide \
  --output build/assembly-guide/index.html \
  --standalone
```

Requires Python + NumPy. Bundling requires the locked Three.js 0.180.0 and esbuild 0.25.10.
For reuse elsewhere, copy `viewer.js`, `model.js`, `template.html`, `style.css`, both generic builder/bundler
scripts and the build-tool manifest/lockfile or the already-built runtime. The
`index.html` under this source folder is only the public A/B/C landing page, not the viewer template.
Retain the Three.js MIT license, also embedded verbatim in the runtime banner.

The adapter reads:

- Catalog: `units: "mm"`, `revision`, `parts` keyed by ID, `colors` keyed by color, `models`.
  Each used part has `id`, `kind`, relative `stl`, `sha256`, measured `bounds`, `orientation`;
  relief parts also have `optional_color_change_z` and `letter_color`.
- Assembly: `model`, `units`, `bounds`, `placements`, `steps`, `bom`.
  Placements have `id`, `part`, `color`, `position` in mm, XYZ `rotation` in degrees,
  `step`, `role`, and optional `course`/`module`. These and the steps must exactly match the catalog model.
- Plate manifest: `units`, `sliced: false`, `printer_settings_validated: false`, `bed_nominal`,
  `plates` with `file`, `color`, and ordered `items: [{part, position, brim_box}]`.
  Optional finish data is `finish_color`, `manual_change_after_z_mm`.
- The actual binary STL files and generic 3MF files. The builder checks hashes/bounds,
  canonical six-decimal triangles, 3MF object names, occurrence order, print transforms and
  all part+color quantities. A changed input must be reconciled explicitly; there is no mismatch-ignore flag.
- The catalog model's NP3 `presentation` includes the module release/lift dimensions.

`--title` accepts escaped plain text, not HTML. No other string is interpreted as markup.
The output is the requested HTML plus a sibling `<stem>.mapping.json`.
The standalone HTML embeds CSS, the classic IIFE runtime and gzip/base64 actual STL bytes.
It needs no server or other files when opened using `file://`. There is no fetch, CDN,
telemetry or API. CSP explicitly forbids `connect-src`; do not weaken it to make tests use `eval`.
The non-standalone mode writes a shared `runtime.js` and `style.css` beside the HTML and
works under both HTTP and file URLs.

No source paths or display strings are copied from the input catalog into output metadata.
Private glyphs are nevertheless present **as geometry** when private STLs are supplied.
Such output must stay in the explicitly authorized private destination.

## Stable mapping schema, version 1

`script#assembly-guide-data` contains `{mapping, meshes}`.
The JSON sidecar contains only `mapping`, with:

- `model`, `guide_revision`, `geometry_revision`, `units`, `part_count`, `bounds`, `colors`.
- `parts[id]`: `id`, `kind`, `bounds`, `dimensions`, `sha256`, `orientation`, optional finish data.
- `plates[]`: `file`, `color`, actual `sha256`, `slots`.
- `slots[]`: stable `id` (`filename.3mf#1`), one-based `number`, `part`, `group`,
  `print_position`, `print_rotation`, `brim_box`, `suggested_placement`, `candidate_placements`.
- `groups["part|color"]`: `part`, `color`, `quantity`, all `placements`, all
  `sources: [{plate, slot, slot_id, suggested_placement}]`.
- `placements[]`: original pose/step/role fields plus zero-based `index`, `group`, `suggested_source`.
- `steps[]`: original `number/title/instances`, plus zero-based `first_index`, exclusive
  `end_index`, and `available_source_files`.
- `first_source`, `base_source_files`, and the display-only `motion` distances.
- `sliced: false`, `physical_fit_tested: false`, `slot_numbers_are_physical_markings: false`.

The suggested source is a deterministic bookkeeping example, not an identity printed on a
physical copy. Always present all same-part/same-color sources and destinations.
For B, black-02 slot 3 is uniquely B-001. All five base courses need selected parts from
black-01 through black-04, including two copies of `BASE3-06x10-T-838259` from black-04.

## Browser contract

`#guide-app[data-ready="true"]` signals readiness; `"error"` and `#guide-error` signal a failure.
Controls are:

- `#plate-select`, `#slot-list [data-slot="filename.3mf#1"]`, `#plate-isolate`.
- `.view-tools[data-scene="plate"|"assembly"] button[data-view="iso"|"front"|"side"|"top"|"back"|"bottom"]`.
- `#step-select`, `#assembly-cursor`, `#motion-progress`, `#start-first`, `#restart`.
- `#previous`, `#next`, `#play`, `#replay-step`, `#speed`, `#ghost`.
- `#source-list`, `#target-list .target-row`, `#selected-part`, `#capture-caption`.
- `#plate-viewport`, `#assembly-viewport`, and `#capture-card` are screenshot regions.

Use the controls for acceptance. `window.BrickAssemblyGuide.state()` is a read-only snapshot
with `cursor`, `empty`, `progress`, `playing`, `mode`, `step`, `activeId`, `selectedSlot`,
`selectedPlate`, `selectedSlotNumber`, `selectedPlacement`, `completedIds`, `candidateIds`,
`sourceSlots`, `assemblyPoses` and `renderError`. `mapping()` exposes the correspondence data.
`completedIds` and `cursor` are the confirmed prefix. `seatedCount`, `seatedIds` and
`activeSeated` also include the current piece when motion reaches 100%, so the visible
count and caption match its seated pose without silently advancing to the next piece.

An empty desk is distinct from a preview of the first hovering piece:
initial load, `restart()` and `setStep(0)` render no assembly meshes, return `step: 0`,
`activeId: null` and zero completed pieces. `setCursor(0)` previews the first piece.
`setStep(n)` starts immediately before that step; it never marks real-world work as complete.
The remaining capture/control API calls the same UI functions:
`setCursor(n)`, `setProgress(0..1)`, `selectSlot(id)`, `selectPlacement(id)`,
`setView(scene, direction)`, `play()`, `pause()`. A progress of 1 shows the final pose;
advancing to the next piece is a separate action.

For automation under the CSP, use locator assertions and protocol `page.evaluate`.
Playwright's string `wait_for_function` internally uses page `eval`, which the CSP forbids.
Do not add `unsafe-eval` merely for a test.

```bash
.venv/bin/python -m unittest discover -s tests -p test_assembly_guide.py -v
node tests/assembly_guide_model.mjs
.venv/bin/python tests/assembly_guide_browser.py \
  --entry build/assembly-guide/index.html --output build/guide-check
```

The last test defaults to the generic B contract. A separate private integration must
assert its own supplied input hashes without sending those files to this repository.
`--capture-media` records the same actual-mesh viewer's first seven B steps and encodes
GIF/H.264 MP4 with ffmpeg. It is not a Blender render or a physical fit test.
