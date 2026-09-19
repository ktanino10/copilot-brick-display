# Revision 3 / Five-course base and independent front modules

Current normal-model revision: **`3.0-five-course-front`**.
The user approved the actual B front/oblique/close-up preview. This approval covers appearance
and design intent only, not physical fit, strength, production qualification or independent review.
The approval and unchanged-geometry constraints are recorded in
[revision3-approval.json](../design/revision3-approval.json) and
[revision3-invariants.json](../design/revision3-invariants.json).

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

The unselected tribute product is frozen, including its old message and public artifacts.
It remains pinned to `BRICK-8-MSG-SLOT-1` at commit `WITHDRAWN-PRIVACY-REVISION`. Normal A/B/C use the separate
**`BASE-FRONT-NP3`** interface. The locked historical helper remains available; it is not silently
reinterpreted as the new module.

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
| A | 143.8 × 63.8 × 187.4 | 91 | 15 / 5 | 14 |
| B | 191.8 × 79.8 × 238.6 | 150 | 19 / 5 | 19 |
| C | 239.8 × 111.8 × 286.6 | 228 | 24 / 5 | 24 |

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
> github.com/YOUR-USERNAME

There is no handle line on the normal models. The standalone raised cyan sign and its old dock
are removed from A/B/C. The current message and logo are black-backed front inserts with white
relief, entirely inside the five-course base at **Z=4..44 mm**.

| Model | Message backing W×H | Main / URL actual cap height | Logo disc / backing width |
| --- | --- | --- | --- |
| A | 102×40 mm | 10 / 7 mm | 28 / 32 mm |
| B | 142×40 mm | 12 / 8 mm | 36 / 40 mm |
| C | 182×40 mm | 14.5 / 9 mm | 40 / 48 mm |

Barlow Condensed Black (SIL OFL, notice bundled) is shaped to the selected height without
thinning it horizontally. Actual parallel straight strokes in the raised cap faces are measured;
the design rejects gauges below 0.84 mm. Mathematical curve terminals are not represented as
uniform-width manufactured walls. In the approved B, the main line is 133.6875 mm wide and
the URL approximately 67.9915 mm; the smallest measured paired straight stroke is approximately
1.4747 mm.

The mark is vectorized from the user-provided black-circle/white silhouette image. Only the
derived normalized outline coordinates and solid relief are published, not the input raster
or its private path. A black carrier supports the black circular pad and all white relief,
including the tail and ears. This is an unofficial personal model, not an endorsed product.

Print both modules rear-face-down. The message carrier is 2.4 mm thick with 0.8 mm raised text.
The logo adds a 0.4 mm black disc before its 0.8 mm white relief. Manual black-to-white changes
occur after **2.4 mm** for text and **2.8 mm** for the logo. These are separate print plates;
do not mix other black blocks into a plate that will change to white. AMS is not required.

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
