"""Dimensioned SVG/PDF from actual FreeCAD projections and canonical placements."""

from __future__ import annotations

import html
import io
import json
import re
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from design import ROOT

INK, BLUE, GRAY = "#142c41", "#2952a6", "#587085"
WIDTH, HEIGHT = 1200, 850


def text(x, y, value, size=14, color=INK, weight="normal", anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="Helvetica,Arial,sans-serif" font-size="{size}" '
            f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(str(value))}</text>')


def line(x1, y1, x2, y2, color=GRAY, width=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'


def dimension(x1, y1, x2, y2, label):
    out = line(x1, y1, x2, y2, BLUE)
    if abs(y2 - y1) < 1e-7:
        out += line(x1, y1 - 5, x1, y1 + 5, BLUE) + line(x2, y2 - 5, x2, y2 + 5, BLUE)
        out += text((x1 + x2) / 2, y1 - 9, label, 14, BLUE, anchor="middle")
    else:
        out += line(x1 - 5, y1, x1 + 5, y1, BLUE) + line(x2 - 5, y2, x2 + 5, y2, BLUE)
        out += text(x1 - 8, (y1 + y2) / 2, label, 13, BLUE, anchor="end")
    return out


def sheet(title, subtitle, content):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297.5mm" viewBox="0 0 {WIDTH} {HEIGHT}">'
        '<rect width="1200" height="850" fill="white"/>'
        + text(42, 42, "BRICK PORTRAIT / PUBLIC TEMPLATE / 5-COURSE BASE / DIGITAL PROTOTYPE", 12, GRAY)
        + text(42, 79, title, 27, weight="bold")
        + text(42, 107, subtitle, 13, GRAY)
        + line(42, 127, 1158, 127, "#c5d3df")
        + content
        + line(42, 801, 1158, 801, "#c5d3df")
        + text(42, 824, "UNITS mm | Fixed 8 mm pitch | Physical fit / strength / stability NOT tested", 11, GRAY)
        + text(1158, 824, "Do not scale STL. Calibrate male + female coupons first.", 11, GRAY, anchor="end")
        + "</svg>"
    )


def fragment(path, stroke=.18, color=INK):
    value = Path(path).read_text()
    value = re.sub(r'\s+id=\s*"[^"]*"', "", value)
    value = re.sub(r'stroke-width="[\d.]+"', f'stroke-width="{stroke}"', value)
    return value.replace('stroke="rgb(0, 0, 0)"', f'stroke="{color}"').replace('stroke="#000000"', f'stroke="{color}"')


def projection(path, view, x, bottom, scale, x_offset=0, stroke=.18, color=INK):
    rotations = {"front": "rotate(90)", "side": "rotate(-90)", "top": "", "bottom": "scale(-1,1)"}
    # TechDraw's exported basis is measured with an asymmetric test solid.
    native = fragment(path, stroke, color)
    transform = "" if 'data-coordinate-system="screen"' in native else rotations[view]
    return (f'<g transform="translate({x - x_offset * scale},{bottom}) scale({scale}) {transform}">'
            + native + "</g>")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return path


def pdf_from_svgs(paths, target):
    pdf = canvas.Canvas(str(target), pagesize=(840, 595), pageCompression=1)
    pdf.setTitle(target.stem)
    pdf.setAuthor("Copilot Brick Display contributors")
    for path in paths:
        drawing = svg2rlg(str(path))
        if drawing is None:
            raise ValueError(f"Could not parse generated drawing: {path.name}")
        factor = min(840 / drawing.width, 595 / drawing.height)
        pdf.saveState()
        pdf.scale(factor, factor)
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.restoreState()
        pdf.showPage()
    pdf.save()


def model_overview(model):
    key = model["id"]
    w, d, h = model["actual_mm"]
    scale = min(430 / w, 420 / h)
    folder = ROOT / "build/projections" / key
    content = text(100, 163, "FRONT / face towards -Y", 14, weight="bold")
    content += projection(folder / "front.svg", "front", 115, 610, scale, model["bounds"][0][0])
    content += dimension(115, 648, 115 + w * scale, 648, f"{w:g}")
    content += dimension(84, 610 - h * scale, 84, 610, f"{h:g}")
    content += text(680, 163, "RIGHT SIDE", 14, weight="bold")
    content += projection(folder / "side.svg", "side", 730, 610, scale, model["bounds"][0][1])
    content += dimension(730, 648, 730 + d * scale, 648, f"{d:g}")
    top_scale = min(300 / w, 100 / d)
    content += text(740, 670, "TOP / front at bottom", 12, weight="bold")
    content += projection(folder / "top.svg", "top", 755, 785, top_scale, model["bounds"][0][0])
    content += text(100, 706, f"{model['part_count']} assembled parts / {len(model['steps'])} numbered stages", 15)
    content += text(100, 733, f"Target: {' x '.join(map(str, model['target_mm']))} (approx. height)", 13, GRAY)
    content += text(100, 758, f"Measured CAD envelope: {w:g} x {d:g} x {h:g} incl. top studs", 13, BLUE)
    return sheet(f"{key} / {model['name']}", "Actual FreeCAD TechDraw projections; drawing dimensions, not a fit certification.", content)


def part_sheet(part, c):
    low, high = part["bounds"]
    w, d, h = [b - a for a, b in zip(low, high)]
    scale = min(370 / w, 200 / max(h, 5), 240 / d, 8)
    folder = ROOT / "build/projections/parts" / part["id"]
    content = text(95, 171, "FRONT", 13, weight="bold")
    content += projection(folder / "front.svg", "front", 110, 440, scale, low[0])
    content += dimension(110, 475, 110 + w * scale, 475, f"{w:.2f}")
    content += dimension(78, 440 - h * scale, 78, 440, f"{h:.2f}")
    content += text(570, 171, "SIDE", 13, weight="bold")
    content += projection(folder / "side.svg", "side", 585, 440, scale, low[1])
    content += dimension(585, 475, 585 + d * scale, 475, f"{d:.2f}")
    plan_scale = min(370 / w, 220 / d, 7)
    content += text(95, 525, "TOP / PRINT ORIENTATION", 13, weight="bold")
    content += projection(folder / "top.svg", "top", 110, 772, plan_scale, low[0])
    content += text(585, 526, "BOTTOM / REAL CAVITIES", 13, weight="bold")
    content += projection(folder / "bottom.svg", "bottom", 600, 772, plan_scale, low[0])
    info = [f"Kind: {part['kind']}", f"STL: {part['id']}.stl", "STL units: mm / scale 100%"]
    if "studs" in part:
        info += [f"Grid: {part['studs'][0]} x {part['studs'][1]} @ 8.00",
                 f"Body height: {part['height']:.2f}"]
    if part.get("top_studs"):
        diameter = 4.8 + part.get("male_correction", c["interface"]["stud_diameter_correction"])
        info += [f"Stud: dia {diameter:.2f} x 1.80 high", "Tip lead-in: 0.25 high / radial"]
    if part.get("socket"):
        clearance = part.get("female_clearance", c["interface"]["female_radial_clearance"])
        info += [f"Female radial c: {clearance:+.2f}", f"Outer wall: {1.5-clearance:.2f}",
                 "Tube bore: 3.20 (not accessory fit)", "Roof ribs: 1.20; bridge gap <=6.80"]
    if part["kind"] in ("front_base", "front_fit_socket"):
        info += ["Front row reserved (no stud/socket)", "NP3 dovetail side allowance: 0.20",
                 "See front-interface.svg for sections"]
    if part["kind"] in ("front_plaque", "front_logo"):
        info += ["Flat rear on bed / relief up", "Carrier 2.40; side taper 2.00",
                 f"Black to white after {part['optional_color_change_z']:.2f}",
                 "White relief: 0.80; do not scale",
                 "Overall installed Z: 4.00 .. 44.00"]
    if part["kind"] == "front_plaque":
        info += c["message"]["lines"]
    if part["kind"] == "front_keeper":
        info += ["Socket row at local Y=12.00", "Flat front stop covers module top",
                 "Lift 6mm, then forward >=32mm and aside"]
    for index, value in enumerate(info):
        content += text(908, 196 + index * 23, value, 10, GRAY)
    return sheet(part["id"], "Three orthographic views + underside from the actual solid. Exterior heights include studs / text.", content)


def exploded_sheet(model, metadata):
    h = metadata["exploded_heights"][model["id"]]
    w = model["actual_mm"][0]
    scale = min(580 / h, 570 / w)
    z_min = metadata["exploded_bounds"][model["id"]][0][2]
    content = projection(ROOT / "build/projections" / model["id"] / "exploded.svg",
                         "front", 180, 772 + z_min * scale, scale, model["bounds"][0][0], .16)
    content += text(800, 199, "EXPLODED FRONT", 18, weight="bold")
    for index, value in enumerate([
        "Actual solids, displaced only for this view.",
        "Exact WebGL 100% offsets, centered up/down.",
        "Do not measure assembly height here.",
        "Use overview for final outside dimensions.",
        "Insert parts downward in numbered order.",
        "Front modules release before spreading.",
        "Stud engagement != verified physical clutch.",
    ]):
        content += text(800, 239 + 29 * index, value, 12, GRAY)
    content += text(800, 495, "TEXT / flat printing view", 13, weight="bold")
    content += projection(ROOT / f"build/projections/parts/NP3-TEXT-{model['id']}/top.svg",
                          "top", 800, 615, min(1.8, 320 / model["message_width"]))
    content += text(800, 665, "RIGHT LOGO / supported relief", 13, weight="bold")
    content += projection(ROOT / f"build/projections/parts/NP3-LOGO-{model['id']}/top.svg",
                          "top", 800, 782, 2.2)
    return sheet(f"{model['id']} / EXPLODED ASSEMBLY", "CAD-derived exploded view; displacement is illustrative, dimensions are not changed.", content)


def stage_sheet(model, step, c):
    bw, bd = [n * 8 for n in model["base_studs"]]
    scale = min(650 / bw, 440 / bd)
    x0, y_bottom = 75, 690
    content = text(75, 163, "PLAN VIEW / front at bottom / NEW parts in color", 14, weight="bold")
    content += f'<rect x="{x0}" y="{y_bottom-bd*scale}" width="{bw*scale}" height="{bd*scale}" fill="#edf3f8" stroke="#b7c8d6"/>'
    for x in range(0, round(bw) + 1, 8):
        content += line(x0 + x * scale, y_bottom - bd * scale, x0 + x * scale, y_bottom, "#d0dde8", .5)
    for y in range(0, round(bd) + 1, 8):
        content += line(x0, y_bottom - y * scale, x0 + bw * scale, y_bottom - y * scale, "#d0dde8", .5)
    additions = []
    for item in model["placements"]:
        if item["step"] > step["number"]:
            continue
        part = c["parts"][item["part"]]
        lo, hi = part["bounds"]
        x, y, z = item["position"]
        if item.get("role") == "front_module":
            x1, y1, dx, dy = x, y - hi[2], hi[0], hi[2]
        else:
            x1, y1, dx, dy = x + lo[0], y + lo[1], hi[0] - lo[0], hi[1] - lo[1]
        active = item["step"] == step["number"]
        color = c["colors"][item["color"]]["hex"] if active else "#d3dfe9"
        content += (f'<rect x="{x0+x1*scale}" y="{y_bottom-(y1+dy)*scale}" width="{dx*scale}" height="{dy*scale}" '
                    f'fill="{color}" stroke="{"#142c41" if active else "#b7c8d6"}" stroke-width="{1 if active else .5}"/>')
        if active:
            additions.append(item)
            content += text(x0 + (x1 + dx / 2) * scale, y_bottom - (y1 + dy / 2) * scale + 4,
                            item["id"].split("-")[1], min(13, max(8, dx * scale / 3)), "white", "bold", "middle")
    content += dimension(x0, 725, x0 + bw * scale, 725, f"nominal {bw:g} / grid 8.00")
    content += text(75, 766, "FRONT (-Y)  /  new parts enter from above (+Z)", 14, BLUE)
    content += text(795, 190, f"ADD {len(additions)} PART(S)", 17, weight="bold")
    for index, item in enumerate(additions):
        yy = 227 + index * 44
        content += text(795, yy, f"{item['id']}  {item['color'].upper()}", 12, weight="bold")
        content += text(795, yy + 17, f"{item['part']}  @ {','.join(f'{v:g}' for v in item['position'])}", 10, GRAY)
    if step["number"] == 1 and model["id"] == "C":
        content += text(795, 570, "Arrange two halves side-by-side.", 12, BLUE)
        content += text(795, 592, "Next course spans the center seam.", 12, BLUE)
    title = f"{model['id']} / STEP {step['number']:02d} OF {len(model['steps']):02d}"
    return sheet(title, "Placement diagram from canonical part bounds. IDs match native CAD, BOM, viewer and animation.", content)


def bom_sheet(model, rows, page_number):
    content = text(55, 164, "PART ID", 12, weight="bold") + text(440, 164, "COLOR", 12, weight="bold")
    content += text(650, 164, "QTY", 12, weight="bold") + text(745, 164, "PRINT FILE", 12, weight="bold")
    for index, row in enumerate(rows):
        yy = 193 + 22 * index
        content += text(55, yy, row["part"], 11) + text(440, yy, row["color"], 11)
        content += text(660, yy, row["quantity"], 11) + text(745, yy, row["stl"], 10, GRAY)
    content += text(55, 748, "TEXT: black -> white at 2.4mm; LOGO: black -> white at 2.8mm. Separate plates.", 11, BLUE)
    content += text(55, 774, f"Assembly: {model['part_count']} pieces, including 2 front modules + 3 keepers. Coupons separate.", 12, BLUE)
    return sheet(f"{model['id']} / COLOR BOM / {page_number}", "One STL geometry may be printed in several colors. Use the quantities for this model only.", content)


def interface_sheet(c):
    base = ROOT / "build/projections/interface"
    content = text(90, 169, "SECTION: Y = 4.00 / TWO 2x2 BRICKS", 14, weight="bold")
    for label, color in [("lower", BLUE), ("upper", INK)]:
        content += projection(base / f"{label}-section.svg", "front", 155, 645, 18, 0, .07, color)
        content += projection(base / f"{label}-plan.svg", "top", 765, 505, 17, 0, .035, color)
    content += dimension(155, 689, 155 + 16 * 18, 689, "8.00 nominal pitch x 2")
    content += text(715, 169, "JOINT SECTION: Z = 10.50", 14, weight="bold")
    content += text(715, 194, "Actual wall, tube, rib + mating stud outlines", 12, GRAY)
    lines = [
        "Blue: lower brick / black: upper socket",
        "Reference stud dia 4.80; candidate height 1.80",
        "Radial clearance c=+0.04 (default; untested)",
        "Inside wall offset 1.56 / wall thickness 1.46",
        "Tube OD 6.433708 / ID 3.20; grid rib 1.20",
        "Tip lead-in 0.25 / female lead-in 0.20 x 0.30",
        "Roof 1.60; thin plate roof 1.00",
        "Thin plate / keeper: nominal headroom 0.40",
        "No forced fit. Tune male and female separately.",
    ]
    for index, value in enumerate(lines):
        content += text(680, 547 + index * 25, value, 12, GRAY)
    return sheet("INTERFACE / SECTION & CLEARANCE", "Project design candidates, NOT a proprietary tolerance standard. Geometry from FreeCAD planar sections.", content)


def front_interface_sheet(c):
    folder = ROOT / "build/projections/interface"
    content = text(70, 164, "B / HORIZONTAL SECTION Z=24 / FRONT 8mm BAND", 14, weight="bold")
    for name, color in (("base", INK), ("modules", BLUE)):
        content += projection(folder / f"front-{name}-plan.svg", "top", 70, 255, 5, 0, .10, color)
        content += projection(folder / f"front-{name}-side.svg", "side", 150, 720, 7, 0, .10, color)
    content += dimension(70 + 4 * 5, 285, 70 + 146 * 5, 285, "B message: 142.00")
    content += dimension(70 + 148 * 5, 320, 70 + 188 * 5, 320, "B logo carrier: 40.00")
    content += text(70, 352, "VERTICAL SECTION X=40", 13, weight="bold")
    content += dimension(105, 720 - 48 * 7, 105, 720, "48.00")
    for i, value in enumerate([
        "Blue: installed modules; black: actual receiver / keepers",
        "Carrier thickness2.40 / rear flat0.80 / edge relief1.20",
        "Rear width -> front width: 2.00 inset on each X side",
        "Default side clearance0.20; coupon candidates0.15/0.20/0.25",
        "Text backY=3.30; logo backY=3.70; relief frontY=0.10",
        "Both front modules fit in Z=4.00..44.00, inside48mm base",
        "3 separate up-stops: text2 / logo1; stud-grid mounting",
        "Remove: up-stops up6, forward>=32; module up45",
        "Thread / glue / magnet / purchased fastener not required",
        "Physical clutch, retention, flatness and stability NOT tested",
    ]):
        content += text(365, 388 + i * 32, value, 13, GRAY)
    return sheet("NP3 / BASE-FRONT CAPTURE & REMOVAL",
                 "Actual BREP sections; precise dimensions apply to the nominal model, not guaranteed printed fit.", content)


def main():
    c = json.loads((ROOT / "design/catalog.json").read_text())
    metadata = json.loads((ROOT / "build/drawing-metadata.json").read_text())
    for model in c["models"]:
        assert abs(metadata["exploded_bounds"][model["id"]][0][1] + 31.9) < .001, "Regenerate stale keeper-route drawing"
    output = ROOT / "site/drawings"
    part_paths = []
    for part in c["parts"].values():
        part_paths.append(save(output / "parts" / f"{part['id']}.svg", part_sheet(part, c)))
    pdf_from_svgs(part_paths, ROOT / "site/downloads/part-drawings.pdf")
    interface = save(output / "interface.svg", interface_sheet(c))
    front_interface = save(output / "front-interface.svg", front_interface_sheet(c))
    pdf_from_svgs([interface, front_interface], ROOT / "site/downloads/interface.pdf")
    for model in c["models"]:
        folder = output / model["id"]
        pages = [save(folder / "overview.svg", model_overview(model)),
                 save(folder / "exploded.svg", exploded_sheet(model, metadata)), interface, front_interface]
        for index in range(0, len(model["bom"]), 25):
            pages.append(save(folder / f"bom-{index // 25 + 1}.svg",
                              bom_sheet(model, model["bom"][index:index + 25], index // 25 + 1)))
        for step in model["steps"]:
            pages.append(save(folder / f"step-{step['number']:02d}.svg", stage_sheet(model, step, c)))
        used = sorted({item["part"] for item in model["placements"]})
        pages += [output / "parts" / f"{key}.svg" for key in used]
        pdf_from_svgs(pages, ROOT / "site/downloads" / model["id"] / "drawings.pdf")
        print(f"{model['id']}: {len(pages)} pages, actual projections + all numbered stages")


if __name__ == "__main__":
    main()
