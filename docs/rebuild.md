# Rebuild / 再生成

## Inputs and tools

- `design/parameters.json`: edit this for fit candidates, message or layout dimensions.
- `scripts/design.py`: discrete A/B/C layout and ID/step rules.
- `scripts/freecad_geometry.py`: the only source for mechanical solids.
- `scripts/front_nameplate.py`: five-course front receivers, independent plaque/logo and keeper geometry.
- `resources/github-mark-relief.json`: normalized user-supplied mark contours; no input raster is distributed.
- Real FreeCAD 1.1.3, Blender 5.1.1 and ffmpeg 8.1 were used for the delivered native files.
- Python 3.11 with `requirements.txt`, and Node.js with `package-lock.json`.
- The bundled B612 Mono Bold font is under SIL OFL; its notice is next to the font.

FreeCAD must expose its `FreeCAD`, `Part`, `MeshPart`, `TechDraw` and `FreeCADGui` modules
to the **matching embedded Python**, not an unrelated system Python.
Set `FREECAD_PYTHON` to that executable and `FREECAD_LIB` to its module directory on your installation.
No personal machine path is hardcoded in this repository.
On a desktop, use a separate headless process rather than taking over an already open document.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run vendor

python3 scripts/design.py
.venv/bin/python -m unittest discover -s tests -v

FREECAD_USER_HOME="$PWD/build/freecad-profile" QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=2 \
  PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/freecad_build.py

PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/verify_cad.py
.venv/bin/python scripts/verify_meshes.py
PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/verify_front_nameplate.py
node tests/motion.mjs
PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/freecad_details.py
.venv/bin/python scripts/build_drawings.py
.venv/bin/python scripts/package_prints.py
```

`freecad_build.py` saves genuine FCStd files with view colors, STEP, per-part binary STL,
and hidden-line CAD projections. It uses Qt's offscreen backend, not the user's interactive CAD
document. On the tested macOS package Qt warns that offscreen OpenGL widgets are unsupported;
solid generation, TechDraw projections, native appearance serialization and subsequent reopen
are verified separately. No screenshot is substituted for a native model.

Intermediate BREP caches and render frames live under ignored `build/`. A cache key includes
the mechanical source and parameter hashes. A changed fit value requires regenerating the full
affected set, not mixing an old STL with new documentation.

## Blender and media

```bash
blender --background --factory-startup --threads 2 \
  --python scripts/blender_scene.py -- --model A
blender --background --factory-startup --threads 2 site/downloads/A/A.blend \
  --python scripts/blender_verify.py -- --model A
python3 scripts/render_movies.py --model A
.venv/bin/python scripts/sanitize_artifacts.py --model A
blender --background --factory-startup --threads 2 site/downloads/A/A.blend \
  --python scripts/blender_verify.py -- --model A
```

Repeat sequentially for B and C; do not launch multiple high-CPU renders.
The scene contains the actual delivered STL meshes, original instance IDs and catalogue transforms.
Geometry is converted from millimetres to metres explicitly; the Blender scene uses metric units.
Blender Workbench is used as an actual studio renderer, not a physics simulation.
Objects arrive in the numbered assembly order, followed by a completed-object turntable.
The still and frames are rendered by Blender. ffmpeg encodes H.264/yuv420p MP4 with faststart.
The native `.blend` and every movie are reopened/decoded independently.

The black text module changes to white after 2.4 mm; the independent logo changes after 2.8 mm.
White relief is real geometry, not a texture. Print the two modules on separate plates; no AMS is required.

For a geometry-identical prior cache, `--reuse-baseline` checks unchanged brick-function ASTs,
the interface and delivered mesh hashes. `--reuse-preview` reuses the approved B geometry only
when its recipe and per-part inputs match. Modified metadata does not justify unverified geometry reuse.
The non-text meshes, dimensions and placements are checked against `design/public-template-invariants.json`.
The unselected individual variant is withheld from public distribution and is not rebuilt by this workflow.
Public parameters are checked against `design/publication-policy.json`. For private values, use
the separate ignored-output command in [the customization guide](customize.ja.md), not the public build.

## Static site

### Print-file to assembly guide (no CAD or Blender regeneration)

The common viewer has an [explicit input/mapping/offline contract](../web/assembly-guide/README.md).
Its source data is the already-verified catalog, model assembly, actual print-plate manifests,
STL and 3MF files. It verifies every print occurrence against the assembly by part ID and color.
It does not invent a one-to-one physical identity for interchangeable copies.

```bash
npm ci
npm run build:assembly-guide
.venv/bin/python scripts/build_public_assembly_guides.py
.venv/bin/python -m unittest discover -s tests -p test_assembly_guide.py -v
node tests/assembly_guide_model.mjs
.venv/bin/python tests/assembly_guide_browser.py \
  --entry site/assembly-guide/B.html --all-models --capture-media
```

Only the public wrapper enforces the generic publication policy. For private input, use the
root-independent `build_assembly_guide.py` with explicit paths and `--standalone` in the
private destination; do not regenerate the public catalog with private text.
The offline ZIPs contain a self-contained HTML viewer, correspondence JSON and the Three.js
MIT notice. They contain no printer profile or G-code. Runtime bundling adds no network dependency.
The annotated new guide images/video are captured from this real STL viewer, not claimed to be
new Blender renders. The existing native scenes and movies remain unchanged.

```bash
python3 -m http.server 8000 --directory site
npm test
BASE_URL=http://127.0.0.1:8000/ npm run test:web
```

For a repository-subpath check, serve the parent directory with a `copilot-brick-display`
mapping or use the local prefix server in `scripts/serve.py`.
The Playwright test can use `BROWSER_PATH` to select an installed browser, otherwise install its
matching Chromium using `npx playwright install chromium`.
The runtime Three.js files and MIT notice are vendored: the public viewer does not need a CDN.

GitHub Pages deploys only `site/` using the checked-in workflow. Source, native files, drawings,
media, messages and notices are public; original photos, personal paths and session history are not.
Do not commit `build/`, virtual environments, dependencies, generated frame sequences, or credentials.

## After a design edit

1. Regenerate layout and geometry; run unit, BREP, mesh and assembly checks.
2. Rebuild projections, PDFs, BOM/print bundles, 3MF layouts, Blender scenes and videos.
3. Confirm catalogue/mesh hashes, color/quantity/placement correspondence and reachable assembly.
4. Request independent review of the fixed changed snapshot. A previous review is not blanket approval.
5. Audit the public package and deploy. **Print calibration coupons again before printing the object.**
