# Design contract / 設計の正本

## Data flow and ownership

`design/parameters.json` and `scripts/design.py` define the fixed grid, three discrete layouts,
exact message, instance IDs, colors, quantities and numbered steps. `design/catalog.json`
is generated from them, then enriched with measurements from real FreeCAD solids.
`scripts/freecad_geometry.py` is the sole mechanical shape generator.

FreeCAD BREP → native FCStd / STEP / print STL → the same STL meshes in Blender and the web viewer.
FreeCAD TechDraw hidden-line projections form the manufacturing views. Instruction plan views
are placement diagrams from catalogue bounds, explicitly distinct from section/manufacturing views.
No original photograph is included. There are no electrical parts.

One mechanical owner integrates changes. A separate manufacturing engineer provided bounded
process advice; a separate mechanical reviewer reviews a fixed snapshot. These are distinct
from a physical prototype, a license from a brand owner, and a safety certification.
The role separation is inspired by the public
[AI Hardware Engineering Team architecture](https://github.com/ktanino10/ai-hardware-engineering-team/blob/main/docs/architecture.md).
No other project's circuit, run ledger, assembly, or safety status is inherited.

## Nominal dimensions, sources, and choices

The manufacturer-filed patent [WO2019106129A1](https://patents.google.com/patent/WO2019106129A1/en)
describes an **approximately** 32×16×9.6 mm four-by-two brick and an approximately 4.8 mm stud.
It is not an FDM manufacturing standard. The 8 mm grid / 3.2 mm plate convention is also
reported by the museum and community references in [sources.json](../design/sources.json).
Those references disagree on stud measurements and stud height. We do not turn those
measurements into a claim about all commercial bricks.

The following are **our adjustable design candidates**, not an official LEGO specification:
stud height 1.8 mm; total body gap 0.2 mm; 0.04 mm default radial female clearance;
1.6 mm roof (1.0 mm on a 3.2 mm plate); 3.2 mm tube inner bore; 1.2 mm roof-support ribs.
All regular `BR-*` parts and the underside of `MSG-DOCK` target standard stud-grid connections.
`MSG-CARD` uses the separate slot below. Tube internal bores are **not** an accessory interface.

### Connection equations (mm)

Let `p=8`, reference stud radius `r=4.8/2`, total body gap `g=0.2`, and radial clearance `c`.
Local nominal grid origin is `(0,0)`.

| Feature | Equation | Default example |
| --- | --- | --- |
| Outer faces | `g/2 .. n*p-g/2` | 2-wide body 15.8 mm |
| Stud centers | `((i+0.5)*p, (j+0.5)*p)` | 4, 12, 20… |
| Printed male diameter | `4.8 + stud_diameter_correction` | 4.8 mm |
| Inside wall coordinate | `p/2-r-c` | 1.56 mm from nominal edge |
| Physical outer wall thickness | `p/2-r-c-g/2` | 1.46 mm |
| Multi-row tube outer radius | `p/sqrt(2)-r-c` | 3.216854 mm |
| One-row central-post radius | `p/2-r-c` | 1.56 mm |
| Tube wall, radial | `tube_radius - 3.2/2` | 1.616854 mm |
| Rib locations / width | `x=i*p`, `y=j*p` / 1.2 mm | nominal-stud clearance ≥1.0 mm |
| Normal roof headroom over stud | `9.6-1.6-1.8` | 6.2 mm |
| Thin-plate / dock headroom | `2.2-1.8` | 0.4 mm |

The tube formula is derived from the diagonal distance between an interstitial tube and the
four surrounding studs. It is not chosen independently of the stud grid.
The default female surfaces have a positive gap to an ideal 4.8 mm reference stud.
**Nominal tangency/gap does not prove clutch**: print roughness, actual commercial diameter,
material elasticity, cooling, wear and printer compensation matter. Negative-clearance coupons
deliberately test interference and are not a mandate to force a fit.

The stud has a 0.25 mm high radial lead-in at the tip; female outer-wall openings and tube/post
tips have a 0.20 mm radial entry relief over 0.30 mm. The grid ribs already clear a reference
stud by at least 1.0 mm and do not rely on an entry chamfer for insertion.
No pitch or placement is scaled for different model sizes.

## The three layouts

| Model | Target envelope | CAD envelope including top studs | Face / goggle / side depth | Parts |
| --- | --- | --- | --- | --- |
| A | 144×64×~150 | 143.8×63.8×149.0 mm | 16 / 24 / 24 mm nominal grid | 74 |
| B | 192×80×~200 | 191.8×79.8×200.2 mm | 32 / 40 / 48 mm nominal grid | 129 |
| C | 240×112×~250 | 239.8×111.8×248.2 mm | 48 / 64 / 80 mm nominal grid | 203 |

Nominal depth entries are grid lengths; a single body's outside length is 0.2 mm less.
A has 14 body courses and a 3.2 mm crest; B has 19 courses and a 6.4 mm crest;
C has 24 courses and a 6.4 mm crest. The silhouettes, green-bar locations, forward relief,
side thicknesses, course partitions and base layout differ.

Runs use 2/4-stud alternating joint starts (with a 5-stud run where necessary to avoid a tiny
end cantilever). A part spans its full designed depth, avoiding continuous unconnected
front/back walls. Newly widening rim runs retain support from the previous course.
Final graph checks include both C base halves, all body parts, the front dock and the card.
The two C base halves are tied across their seam by the front dock and a first-course body brick.

## Shared external message module

Contract ID: `BRICK-8-MSG-SLOT-1`, in [interface.json](../design/interface.json).

- `MSG-DOCK`: nominal 12×2 studs; actual body 95.8×15.8×9.6 mm; 24 underside positions,
  no upper studs; 2.2 mm deep underside cavity.
- Slot: 88.4×2.4 mm, depth 4.8; local `x=3.8..92.2`, `y=2.8..5.2`, `z=4.8..9.6`.
- `MSG-CARD`: print orientation `x=0..88`, `y=0..24`, `z=0..2`, letters to `z=2.6`.
  Its first 4.8 mm in local Y is smooth.
- Assembled card relative to dock: translation `(4,5,4.8)` mm, rotation +90° around X.
  This gives 0.4 mm total width and length clearance. It is a loose gravity slot, not a snap fit.
- The final card slides up without the goggles obstructing it. Install the dock before the body.
  Neither component is a handle.

The card is independent from the main object, printed flat, and can be replaced.
Exactly three lines are used, with no added year count, thanks, or period:
`@YOUR-USERNAME` / `Same icon, New adventures` / `github.com/YOUR-USERNAME`.
The optional color change after z=2.0 mm gives the cyan/black appearance shown in the media.

## Manufacturing dispositions

| Raised issue | Design disposition | Still unverified physically |
| --- | --- | --- |
| Tubes alone leave long unsupported roof corridors | 1.2 mm grid ribs added; straight roof spans bounded to 6.8 mm; bores 3.2 mm | Actual bridge sag and toolpaths |
| 0.2 mm roof headroom on thin plates is fragile | Thin roof 1.0 mm and dock cavity 2.2 mm give 0.4 mm nominal headroom | Printed flatness and seating |
| A 240 mm single base plus brim is too near bed limits | C base split into identical 15×14-stud halves | Warping, plate exclusions, seam rigidity |
| Male and female fit need independent calibration | Separate diameter and radial-clearance sweeps | Clutch, force, repeatability |
| Dense small plaque letters do not print well vertically | Separate flat-printed card; 0.2 mm recommendation; optional manual color swap | Actual letter fidelity and slot fit |

## Evidence boundary

Boolean zero-interference, watertight meshes, native-file reopen, a connected nominal stud graph,
and assembly animations are digital checks. The material centroid calculation assumes fully
solid CAD material, not a sliced infill distribution. It only checks whether the projection is
inside the base footprint; it is not a tipping-force or strength result.

Physical fit, friction/retention, fatigue, PLA strength, finished mass, printing time, heat resistance,
and the assembled object's tip behavior remain **unverified**. No G-code or blanket production
approval is issued. See [the beginner workflow](build.ja.md) before printing.
