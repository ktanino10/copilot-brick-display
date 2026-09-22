# Revision 3 / Five-course base and independent front modules

Current normal-model revision: **`5.0-legible-plaques`**.

**Manufacturing guidance update `trial-2026-09-19`: no geometry change.**
A [separate public 4 mm trial report](https://github.com/ktanino10/octoprints-brick-kit-downloads/blob/be956ae14d2aac1601a4a2a87f2e49675a36979e/feedback/2026-09-19/README.md)
describes handling difficulty and plastic-obstructed holes. Its actual sliced input/settings and
root cause were not established. This is failure evidence for another design, not a physical
pass for A/B/C or a reason to import its clearance values, media, geometry or license.
Our normal 8 mm stud/tube blocks, shallow keeper sockets and reserved-front-row base/keyway
parts still need layer-preview and real handling checks.
[The staged seven-piece selection](trial.ja.md) adds only unchanged current STL and small BOMs,
reuses existing fit coupons, and stops bulk printing on obstruction, poor grip or failed seating.
The existing 0.4/0.2 mm recommendations remain untested baselines.

The five-course layout is retained, but public message geometry now uses explicit placeholders.
No historical personal preview is republished as evidence for the generic text.
The non-text shape and placement contract is recorded in
[public-template-invariants.json](../design/public-template-invariants.json).
It is not a physical fit, strength or production qualification.

## One geometric source

`design/parameters.json` and `scripts/design.py` define pitch, courses, unique part IDs,
colors/finishes, quantities, placements and numbered steps. `design/catalog.json` is generated
and populated with actual FreeCAD measurements. `scripts/freecad_geometry.py` owns the unchanged
brick family; `scripts/front_nameplate.py` owns the new front interfaces and reliefs.

Actual FreeCAD BREP → FCStd / STEP / mm STL → the same meshes in Blender and the WebGL viewer.
TechDraw projections and planar sections are used for manufacturing drawings. Numbered plan
views are explicitly placement diagrams from the same catalogue. No raster-only or texture-only
lettering/logo substitutes for the delivered solid geometry.

Unchanged face/crest parts keep their original STL hashes and move only **+38.4 mm in Z**.
The source/cache recipes and B preview parts are reused instead of recalculating unchanged solids.
The five-course base is visible throughout the assembly sequence, so affected scenes, drawings
and movie frames are genuinely regenerated from the revised placements.

The unselected individual variant is preserved privately and is not distributed or regenerated.
Normal A/B/C use **`BASE-FRONT-NP3`**. Private historical interfaces and personal inputs are not
fetched from withdrawn revisions to rebuild this public template.

## Nominal references versus design choices

The LEGO-filed patent [WO2019106129A1](https://patents.google.com/patent/WO2019106129A1/en)
describes an approximate 32×16×9.6 mm four-by-two brick and approximate 4.8 mm knobs.
It does not specify this project's FDM tolerances. Museum and community references in
[sources.json](../design/sources.json) support the 8 mm grid / 3.2 mm plate convention
but disagree about some measured stud dimensions.

Our adjustable candidates remain: 1.8 mm stud height, 0.2 mm total body gap, default female
radial clearance +0.04 mm, usual roof 1.6 mm, thin-plate roof 1.0 mm, internal tube bore
3.2 mm and roof ribs 1.2 mm. Internal bores are not a claimed commercial accessory interface.

| Feature | Constraint / default |
| --- | --- |
| Body sides | `0.1 .. 8*n−0.1`; stud centers `4+8*i` |
| Inside-wall coordinate | `4−2.4−c = 1.56 mm`; physical outer wall 1.46 mm |
| Multi-row tube outside radius | `8/sqrt(2)−2.4−c = 3.216854 mm` |
| One-row post radius | `4−2.4−c = 1.56 mm` |
| Tube radial wall | 1.616854 mm |
| Grid ribs | 1.2 mm at nominal row/column boundaries; reference stud clearance ≥1.0 mm |
| Orthogonal roof span | ≤6.8 mm between ribs; tube bores 3.2 mm |
| Thin plate headroom | `3.2−1.0−1.8 = 0.4 mm` |

An ideal reference stud has nominal positive clearance at the default setting. This does not
prove frictional clutch. Independent male-diameter and female-clearance coupons must be printed
and tested with actual commercial and printed mates. PLA is not ABS; do not force, lever or hammer.

## Real five-course bases

| Model | Actual W×D×H, mm | Installed parts | Base blocks / courses | Unchanged face courses |
| --- | --- | --- | --- | --- |
| A | 143.8 × 64.2 × 187.4 | 91 | 15 / 5 | 14 |
| B | 191.8 × 80.2 × 238.6 | 150 | 19 / 5 | 19 |
| C | 239.8 × 112.2 × 286.6 | 228 | 24 / 5 | 24 |

The base body is **48 mm = 5×9.6 mm**, with independent, printable, separable blocks—not one
large solid box with drawn seams. Upper courses alternate six-stud runs and half-offset
three/six-stud runs. C retains two 15×14-stud bottom halves; subsequent courses span their seam.
Each block spans its designed depth, so front and rear are not unrelated thin skins.

The first front 8 mm row is deliberately reserved for the two vertical channels:
its top studs are removed and its underside is reinforced rather than a commercial socket.
Rows starting at Y=12 mm keep the fixed grid. The lowest face parts start at Z=48 mm behind
the front interfaces. Neither the face nor the block pitch is scaled.

C's assembled height exceeding the printer's 256 mm nominal volume is not a printing violation:
only individual parts are printed. The largest B footprint plus 6 mm external brim is
203.8×91.8 mm; each C bottom half plus brim is 131.8×123.8 mm. Actual plate exclusions,
toolpaths, warping and first layers still require a slicer and real print check.

## Two-line message and right-hand logo

The exact text is:

> Same icon, New adventures<br>
> github.com/USER

There is no handle line on the normal models. The standalone raised cyan sign and its old dock
are removed from A/B/C. The current message and logo are black-backed front inserts with white
relief, entirely inside the five-course base at **Z=4..44 mm**.

| Model | Message backing W×H | Main / URL actual cap height | Logo disc / backing width |
| --- | --- | --- | --- |
| A | 102×40 mm | 10 / 10 mm | 28 / 32 mm |
| B | 142×40 mm | 12 / 10 mm | 36 / 40 mm |
| C | 182×40 mm | 14.5 / 10 mm | 40 / 48 mm |

Barlow Condensed Bold is used for the main line, preserving its X scale and declared ink height;
Black is enlarged uniformly to10mm for the shorter URL placeholder. Existing kerning is preserved
when adequate, otherwise additional spacing is inserted. Inner counters and the e's right opening
are enlarged without inflating the entire outline. `USER` is an explicit placeholder, not a profile link.
In B the actual ink widths are132.1301 and77.4228mm within134mm; the carrier remains142×40mm.
See [the measured typography change](lettering.ja.md) and `validation/lettering.json` for
central-band counter chords, actual BRep gaps, approximate open-pocket escape diameters,
straight positive strokes and persistent material-neck indicators. A uses explicitly lower
main-line gap/counter targets to fit without thinning or shortening its text.
These are not physical-print measurements or guarantees for every mathematical curve terminal.

The mark is vectorized from the user-provided black-circle/white silhouette image. Only the
derived normalized outline coordinates and solid relief are published, not the input raster
or its private path. A black carrier supports the black circular pad and all white relief,
including the tail and ears. This is an unofficial personal model, not an endorsed product.

Print both modules rear-face-down. The message carrier is 2.4 mm thick with 1.2 mm raised text.
The logo adds a 0.4 mm black disc before its 0.8 mm white relief. Manual black-to-white changes
occur after **2.4 mm** for text and **2.8 mm** for the logo. These are separate print plates;
do not mix other black blocks into a plate that will change to white. AMS is not required.
The extra0.4mm of text projects forward toY=-0.30, increasing only the assembled depth by0.4mm.
The original68 non-text masters, carrier geometry, installation poses, width and height are unchanged.

## Positive geometry and removal

Each module has a wider rear face and a front face narrowed by 2 mm per X side.
The default receiver side allowance is 0.2 mm; small C15/C20/C25 receiver coupons are provided.
The back-to-front transition is 2.4 mm deep, with a 0.8 mm initial flat back and 1.2 mm vertical
edge relief. The printable widening slope is no steeper than 45° to vertical.

The matching dovetail channels run vertically through the five aligned courses. Shaped bottom
seats stop downward motion. Their side geometry blocks frontward and lateral pulling;
**two message keepers and one separate logo keeper** block upward escape. Keepers engage the
second stud row. Their physical clutch is a calibration requirement, not an assumed certified force.

For replacement, lift the relevant keeper(s) approximately 6 mm, move them at least 32 mm forward and set them aside,
then slide that module straight up at least 45 mm before taking it forward. The other front
module can remain installed. Face parts are behind this path, with nominal Y clearance.
Never lift the entire object by a module, keeper, head or goggles.

Digital checks test final solids, blocked translations, released vertical samples, and the
staged viewer route. They do not prove arbitrary forced motion, elastic deformation, wear,
human grip strength, clutch force or printed durability.

## Strong vertical exploded view

0% is exactly the completed catalogue pose. The initial slider phases first lift the keepers,
move them forward, then lift and move both front modules clear. The forward distance is computed
as at least the keeper's 16 mm nominal depth plus the module's 14 mm forward travel plus a 2 mm
display clearance: 32 mm. The requested minimum `keeper_forward_mm` cannot override that safety envelope. The remaining range separates
courses around a central reference: lower courses move down and upper courses move up.

At 100%, each neighboring body/base course receives 20 mm relative display displacement.
The resulting clear gap, including 1.8 mm studs, is at least **18.2 mm**. All five base courses
participate. Small front modules are displayed below the base only after the safe initial
clearance route. This is explanatory movement, not an instruction to pull the whole model apart
simultaneously or a physical simulation.

Cached local bounds are rotated once and translated per update; no full-vertex scan or new
geometry is created every frame. Camera target, orthographic frustum and clipping use visible
exploded bounds while preserving the current view direction. Actual desktop/mobile 0/50/100%
screenshots, gap checks, return-to-zero, selection and assembly-control checks are release gates.

## Review and physical boundary

One mechanical owner integrates the change; the same separate mechanical reviewer reviews a
fixed changed snapshot and its final presentations. Native reopen, STEP/STL consistency,
watertight meshes, contact/retention geometry, body hashes, BOM/steps, actual Blender scenes,
video decode and public download hashes are recorded separately.

The material centroid is a uniform solid-CAD proxy, not sliced mass or a measured tipping load.
The increased height requires a fresh real-world stability check on a low, flat, safe surface.
Physical fit, printed-thread or stud wear, PLA strength, clutch, heat resistance, print time/mass,
tip resistance and toy safety remain **unverified**. Print the calibration pieces first.
