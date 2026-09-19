"""Vector projections of the delivered CAD meshes; dimensions come from the native catalog."""
import csv
from collections import defaultdict
from html import escape
import json
import math
from pathlib import Path

from mesh_audit import read_stl

ROOT = Path(__file__).resolve().parents[1]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(vector):
    length = math.sqrt(dot(vector, vector))
    return tuple(value / length for value in vector)


def text(x, y, content, size=3, fill="#172f3e"):
    return f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" fill="{fill}">{escape(str(content))}</text>'


def line(x1, y1, x2, y2, **attributes):
    attrs = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attributes.items())
    return f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="#526b78" stroke-width=".3" {attrs}/>'


def dimension(x1, x2, y, label):
    return (line(x1, y, x2, y, marker_start="url(#arrow)", marker_end="url(#arrow)") +
            line(x1, y-2, x1, y+2) + line(x2, y-2, x2, y+2) +
            text((x1+x2)/2-5, y-1.5, label, 3))


def page(title, content, filename):
    header = ('<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">'
              '<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" '
              'orient="auto-start-reverse"><path d="M 9 1 L 1 5 L 9 9" fill="none" stroke="#526b78"/></marker></defs>'
              '<rect width="420" height="297" fill="white"/><g font-family="sans-serif">'
              '<rect x="5" y="5" width="410" height="287" fill="none" stroke="#92a6ac" stroke-width=".3"/>')
    footer = text(12, 283, "CHARACTER TRIBUTE / T1 / mm / CAD-derived vector projection", 3)
    footer += text(12, 289, "縮尺は印刷設定に依存。寸法は数値を優先。実物嵌合・強度・安全認証は未確認。", 2.8)
    svg = header + text(12, 15, title, 5) + content + footer + "</g></svg>\n"
    (ROOT / "drawings" / filename).write_text(svg)


def load_geometry(catalog):
    parts = {part["id"]: part for part in catalog["parts"]}
    meshes = {part["id"]: read_stl(ROOT / part["mesh"]) for part in catalog["parts"]}
    geometry = []
    for item in catalog["instances"]:
        vertices, faces = meshes[item["part"]]
        angle = math.radians(item["rotation_deg_xyz"][0])
        c, s = math.cos(angle), math.sin(angle)
        x, y, z = item["position_mm"]
        world = [(p[0]+x, p[1]*c-p[2]*s+y, p[1]*s+p[2]*c+z) for p in vertices]
        geometry.append({"instance": item, "part": parts[item["part"]], "vertices": world,
                         "print_vertices": vertices, "faces": faces})
    return geometry, meshes


def projection(geometry, view, x, y, scale, colors):
    normal = unit(view)
    right = (1, 0, 0) if abs(normal[2]) > .999 else unit(cross((0, 0, 1), normal))
    up = cross(normal, right)
    projected = [(dot(point, right), dot(point, up))
                 for group in geometry for point in group["vertices"]]
    umin, umax = min(p[0] for p in projected), max(p[0] for p in projected)
    vmin, vmax = min(p[1] for p in projected), max(p[1] for p in projected)
    def locate(point):
        return x + (dot(point, right)-umin)*scale, y + (vmax-dot(point, up))*scale
    light = unit((.3, -.6, 1))
    triangles = []
    for group in geometry:
        color = colors[group["part"]["color"]]["hex"]
        edges, normals = defaultdict(list), []
        for face_index, indices in enumerate(group["faces"]):
            p, q, r = [group["vertices"][i] for i in indices]
            n = cross(tuple(q[i]-p[i] for i in range(3)), tuple(r[i]-p[i] for i in range(3)))
            normals.append(unit(n))
            for a, b in zip(indices, indices[1:]+indices[:1]):
                edges[tuple(sorted((a, b)))].append(face_index)
            if dot(n, normal) <= 1e-9:
                continue
            face_color = color
            change = group["part"].get("optional_color_change_z_mm")
            if change is not None and max(group["print_vertices"][i][2] for i in indices) > change + .001:
                face_color = colors["charcoal"]["hex"]
            shade = .78 + .22 * max(0, dot(unit(n), light))
            channels = [int(int(face_color[i:i+2], 16)*shade) for i in (1, 3, 5)]
            fill = "#" + "".join(f"{value:02x}" for value in channels)
            points = " ".join(f"{u:.3f},{v:.3f}" for u, v in map(locate, (p, q, r)))
            triangles.append((dot(tuple((p[i]+q[i]+r[i])/3 for i in range(3)), normal),
                              f'<polygon points="{points}" fill="{fill}" stroke="{fill}" stroke-width=".018" stroke-linejoin="round"/>'))
        for (a, b), adjacent in edges.items():
            facing = [dot(normals[index], normal) > 1e-8 for index in adjacent]
            if not any(facing):
                continue
            if all(facing) and dot(normals[adjacent[0]], normals[adjacent[1]]) > .85:
                continue
            p, q = group["vertices"][a], group["vertices"][b]
            start, end = locate(p), locate(q)
            depth = dot(tuple((p[i]+q[i])/2 for i in range(3)), normal) + 1e-4
            fragment = (f'<path d="M{start[0]:.3f},{start[1]:.3f} L{end[0]:.3f},{end[1]:.3f}" '
                        'fill="none" stroke="#152936" stroke-opacity=".65" stroke-width=".10"/>')
            triangles.append((depth, fragment))
    return ("".join(fragment for _, fragment in sorted(triangles)), locate,
            ((umax-umin)*scale, (vmax-vmin)*scale))


def expanded_views(geometry, catalog, meshes):
    colors = catalog["colors"]
    parameters = json.loads((ROOT / "parameters.json").read_text())
    fit = parameters["stand"]
    alignment = parameters["alignment"]
    message = catalog["shared_interface"]["message"]
    brick = catalog["shared_interface"]["brick"]
    gauges = json.loads((ROOT / "validation/assembly.json").read_text())["text"]
    exploded = []
    for group in geometry:
        item = group["instance"]
        if item["id"] == "stand":
            delta = (0, 0, 0)
        elif item["id"] == "message-dock":
            delta = (0, -45, 12)
        elif item["id"] == "message-card":
            delta = (0, -80, 40)
        else:
            delta = (0, -max(0, 12.8-item["position_mm"][1])*5, 48)
        exploded.append({**group, "vertices": [tuple(p[i]+delta[i] for i in range(3))
                                               for p in group["vertices"]]})
    drawing, locate, _ = projection(exploded, (1, -2, 1.3), 16, 30, .70, colors)
    content = drawing + text(280, 30, "ID / 色 / 数 / 工程", 3.5)
    unique = [part for part in catalog["parts"] if part["category"] == "assembly"]
    for index, part in enumerate(unique):
        group = next(g for g in exploded if g["part"]["id"] == part["id"])
        center = [sum(p[i] for p in group["vertices"])/len(group["vertices"]) for i in range(3)]
        sx, sy = locate(center)
        y = 41+index*10.4
        content += line(sx, sy, 273, y-1, stroke_dasharray="1 1")
        content += text(278, y, f'{part["id"]}  {colors[part["color"]]["name_ja"]} ×{part["quantity"]}', 3)
        content += text(278, y+4, f'{part["name_ja"]} / 工程 {group["instance"]["step"]}', 2.4)
    page("分解図 / EXPLODED ASSEMBLY（分離距離は説明用）", content, "exploded.svg")
    for category, filename, title in (
            ("assembly", "part-dimensions.svg", "色別部品図 / PRINT-LOCAL PARTS"),
            ("coupon", "fit-coupons.svg", "試験片図 / FIT BEFORE PRINTING THE DISPLAY")):
        parts = [part for part in catalog["parts"] if part["category"] == category]
        content = text(12, 23, "寸法は最大外形 X × Y × Z mm（突起を含む）。完成品への組込数と試験片数を区別。", 3)
        cell_h = 48 if category == "assembly" else 78
        for index, part in enumerate(parts):
            col, row = index % 4, index // 4
            x, y = 12+col*100, 31+row*cell_h
            vertices, faces = meshes[part["id"]]
            group = {"part": part, "vertices": vertices, "print_vertices": vertices, "faces": faces}
            view = (0, 0, -1) if part["id"].startswith("FIT-F") else (1, -2, 3)
            width, length, height = part["bounds_mm"]
            scale = min(42/max(width, length, 1), (cell_h-17)/max(width, length, 1))
            image, _, _ = projection([group], view, x, y+8, scale, colors)
            content += image
            content += text(x, y+3, part["id"], 3.2)
            content += text(x+47, y+11, colors[part["color"]]["name_ja"], 2.8)
            count = part["quantity"] if category == "assembly" else 1
            content += text(x+47, y+17, f'{"組込" if category == "assembly" else "試験"} ×{count}', 2.8)
            content += text(x+47, y+23, f"{width:.2f} × {length:.2f}", 2.6)
            content += text(x+47, y+29, f"× {height:.2f} mm", 2.6)
            if category == "coupon":
                spec = part.get("shared_spec", {})
                if "male_correction" in spec:
                    content += text(x+47, y+39, f'φ{4.8+spec["male_correction"]:.2f}', 3)
                if "female_clearance" in spec:
                    content += text(x+47, y+39, f'半径補正 {spec["female_clearance"]:+.2f}', 2.6)
                if part["id"] == "T90":
                    content += text(x+47, y+39, "A/B/C/D = 6.5/6.7/", 2.4)
                    content += text(x+47, y+44, "6.9/7.1 mm", 2.4)
            content += line(x, y+cell_h-3, x+96, y+cell_h-3)
        page(title, content, filename)
    stand = [group for group in geometry if group["instance"]["id"] == "stand"]
    diagram, locate, _ = projection(stand, (0, 0, 1), 15, 41, 1.05, colors)
    content = diagram + text(15, 35, "T01 上面（実CADメッシュ）", 3.5)
    a, b = locate((-fit["slot_width"]/2, fit["slot_y_min"], fit["height"])), locate(
        (fit["slot_width"]/2, fit["slot_y_min"], fit["height"]))
    content += dimension(a[0], b[0], a[1]+15, f'{fit["slot_width"]:g}')
    p, q = locate((-44, -32, 9.6)), locate((-36, -32, 9.6))
    content += dimension(p[0], q[0], p[1]+9, "8")
    notes = [
        ("背板ソケット", f'{fit["slot_width"]:g} × {fit["slot_depth"]:g} / 舌80.0 × 6.4',
         f'全体隙間 X{fit["slot_width"]-80:.2f}・Y{fit["slot_depth"]-6.4:.2f} / 差込32.0'),
        ("共有スタッド", f'12 × 2 / pitch{brick["pitch"]:g} / φ{brick["reference_stud_diameter"]+brick["stud_diameter_correction"]:g}候補',
         f'高さ{brick["stud_height"]:g}、面取り{brick["stud_lead_in"]:g} / 実物clutch未検証'),
        ("共有ドック", "95.8 × 15.8 × 9.6", f'下面socket深{message["dock_socket_depth"]:g} / ABSへ無理押ししない'),
        ("文字カードの溝", f'{message["slot_length"]:g} × {message["slot_width"]:g} / 深さ{message["slot_depth"]:g}',
         f'カード{message["card_width"]:g} × {message["card_height"]:g} × {message["card_thickness"]:g} / 文字浮出{message["text_relief"]:g}'),
        ("カードの遊び", "幅・厚みとも全体0.4 = 片側0.2", "下端4.8は無文字 / 上から抜き差し・無接着"),
        ("色タイル用の角ピン",
         f'{alignment["pin_width"]:g}角 × 高{alignment["pin_height"]:g} / 穴{alignment["socket_width"]:g}角 × 深{alignment["socket_depth"]:g}',
         f'片側{(alignment["socket_width"]-alignment["pin_width"])/2:.2f} / 市販互換ではない')
    ]
    for index, (heading, value, note) in enumerate(notes):
        y = 39+index*33
        content += text(225, y, heading, 4) + text(225, y+7, value, 3.2) + text(225, y+14, note, 2.6)
    content += text(15, 183, "CANDIDATE DIMENSIONS ≠ GUARANTEED PRINT TOLERANCE", 3)
    for i, note in enumerate([
            "上記は設計した隙間・補正値です。プリンターの達成精度や保持力を保証しません。",
            "T90/T91 は背板厚み、T92/T93 は位置決め、FIT-* は共有ブロック接続の試験片。",
            "最も緩い候補から確認し、白化・割れ・強い抵抗があれば中止します。",
            "補正は該当パラメーターだけを変更して再生成。STL全体の拡大縮小は禁止。",
            f'文字ストローク最小実測{gauges["minimum_parallel_straight_stroke_mm"]:.3f} mm、独立島外形{gauges["minimum_separate_glyph_island_bbox_mm"]:.3f} mm。',
            "文字は0.2mmノズルを使用し、スライサーで細い字画・句読点を確認します。"]):
        content += text(15, 194+i*8, note, 2.8)
    page("接続・隙間・最小形状 / INTERFACE DETAILS", content, "interface-details.svg")


def main():
    (ROOT / "drawings").mkdir(exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    catalog = json.loads((ROOT / "catalog.json").read_text())
    colors = catalog["colors"]
    geometry, meshes = load_geometry(catalog)
    front, _, fb = projection(geometry, (0, -1, 0), 14, 109, .7, colors)
    top, _, tb = projection(geometry, (0, 0, 1), 14, 31, .7, colors)
    side, _, sb = projection(geometry, (1, 0, 0), 191, 109, .7, colors)
    content = front + top + side
    content += text(14, 105, "正面 / FRONT") + text(14, 27, "上面 / TOP") + text(191, 105, "右側面 / RIGHT")
    content += dimension(14, 14+fb[0], 258, "176") + dimension(191, 191+sb[0], 258, "96")
    content += line(148, 109, 148, 109+fb[1], marker_start="url(#arrow)", marker_end="url(#arrow)")
    content += text(150, 180, "201.6")
    notes = [
        "完成寸法 176 × 96 × 201.6 mm", "本図の配置縮尺 0.70:1 / A3",
        "幅・高さはブロック数と板形状で決定", "接続ピッチは固定 8 mm",
        "台座単体の最大高さ 41.6 mm", "背板は幅160 × 高さ160 ＋ 舌32 mm",
        "メッセージ部は本体から取り外し可能", "カードの黒文字は任意の手動色替え例",
        "線・面は実CAD由来STLの投影", "メッシュの線形偏差設定 0.05 mm",
        "主要寸法は保存済みBRepと照合", "画面の見た目から嵌合を判断しない"
    ]
    for index, note in enumerate(notes):
        content += text(285, 43+index*7, note, 3)
    page("三面図 / ORTHOGRAPHIC ASSEMBLY", content, "three-views.svg")
    iso, _, _ = projection(geometry, (1, -2, 1.3), 22, 32, .96, colors)
    content = iso + text(270, 42, "@YOUR-USERNAME", 6)
    content += text(270, 52, "Same icon, New adventures", 3.5)
    content += text(270, 60, "github.com/YOUR-USERNAME", 3.5)
    for index, note in enumerate(["20種類 / 組込29個 / 7色", "卓上用の段差レリーフ", "防護用の盾ではありません",
                                  "市販ブロックとの接続は試験前提", "AMS不要。色別単色部品で構成",
                                  "PLA / 0.4 mm基準・文字は0.2 mm推奨", "非公式の個人記念品"]):
        content += text(270, 85+index*9, note, 3.5)
    page("完成図 / CAD ASSEMBLY", content, "assembly-isometric.svg")
    expanded_views(geometry, catalog, meshes)
    with (ROOT / "docs/bom.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["Part ID", "部品名", "色", "完成品組込数", "試験用推奨数", "最大X mm", "最大Y mm", "最大Z mm",
                         "組立工程", "配置ID", "STL", "STEP"])
        for part in catalog["parts"]:
            instances = [item for item in catalog["instances"] if item["part"] == part["id"]]
            writer.writerow([part["id"], part["name_ja"], colors[part["color"]]["name_ja"], part["quantity"],
                             1 if part["category"] == "coupon" else 0, *[round(v, 3) for v in part["bounds_mm"]],
                             ",".join(map(str, sorted({item["step"] for item in instances}))) or "0 試験",
                             ",".join(item["id"] for item in instances), part["mesh"], part["step"]])
    print("DRAWINGS_AND_BOM_GENERATED")


if __name__ == "__main__":
    main()
