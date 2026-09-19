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
    footer = text(12, 283, "CHARACTER TRIBUTE / T2 / mm / removable mechanical capture", 3)
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
    retention = parameters["retention"]
    message = catalog["shared_interface"]["message"]
    brick = catalog["shared_interface"]["brick"]
    gauges = json.loads((ROOT / "validation/assembly.json").read_text())["text"]
    sheets=[]
    def emit(title,content,file,subtitle):
        page(title,content,file)
        sheets.append({"file":file,"title":title.split(" / ")[0],"subtitle":subtitle})
    exploded = []
    for group in geometry:
        item = group["instance"]
        if item["id"] in ("stand","message-dock","message-card"):
            continue
        delta = (0,{1:0,2:32,3:64,4:96,5:128,6:176,7:208}[item["step"]],0)
        exploded.append({**group, "vertices": [tuple(p[i]+delta[i] for i in range(3))
                                               for p in group["vertices"]]})
    drawing, locate, _ = projection(exploded, (1, 2, 1.1), 14, 35, .62, colors)
    content = drawing + text(274, 30, "後方へ分離 / 寸法ではありません", 3.5)
    callouts=[("capture-frame","T02 前枠"),("tile-001","IN-* 色インサート61個"),
              ("eye-left-white","EYE-W 白目 ×2"),("eye-left-iris","EYE-B 虹彩 ×2"),
              ("eye-left-pupil","EYE-K 瞳 ×2"),("badge-white","BADGE-W 白い丸"),
              ("badge-m","BADGE-M M"),("back-cover","T03 着脱裏蓋")]
    callouts += [(f"screw-{i}",f"T04 印刷粗ねじ {i}/4") for i in range(1,5)]
    for index,(instance,label) in enumerate(callouts):
        group = next(g for g in exploded if g["instance"]["id"] == instance)
        center = [sum(p[i] for p in group["vertices"])/len(group["vertices"]) for i in range(3)]
        sx, sy = locate(center)
        y = 44+index*16
        content += line(sx,sy,269,y-1,stroke_dasharray="1 1")
        content += text(273,y,label,3)
    content += text(273,249,"ねじ→裏蓋→瞳→虹彩/M→白→色部品",2.6)
    emit("分解図 / REARWARD EXPLODED VIEW",content,"exploded.svg","POSITIVE CAPTURE / REVERSE RELEASE")
    back,locate,_=projection(geometry,(1,2,1.3),18,31,.93,colors)
    content=back+text(272,40,"背面の粗ねじ4本で裏蓋を保持",4)
    for i in range(1,5):
        instance=next(g for g in geometry if g["instance"]["id"]==f"screw-{i}")
        center=[sum(p[j] for p in instance["vertices"])/len(instance["vertices"]) for j in range(3)]
        x,y=locate(center)
        content+=line(x,y,268,65+i*18,stroke_dasharray="1 1")+text(272,67+i*18,f"T04 / {i}",3)
    for i,note in enumerate(["手で締め、背面から見て反時計回りに外す。",
                              "標準Mねじではありません。専用T04を使用。",
                              "実物の保持力・着脱耐久は試作待ち。",
                              "裏蓋を外す前に、前面を支持台で保護。"]):
        content+=text(272,175+i*11,note,2.7)
    emit("背面図 / REMOVABLE BACK COVER",content,"assembly-back.svg","FOUR REPLACEABLE SCREWS")
    for category,base,title in (("assembly","part-dimensions","組込部品図"),("aux","fit-coupons","試験片・工具図")):
        entries=[p for p in catalog["parts"] if (p["category"]=="assembly")== (category=="assembly")]
        for offset in range(0,len(entries),20):
            content=text(12,23,"印刷座標の最大外形 / mm。工具・試験片は完成品の組込数と別です。",3)
            for index,part in enumerate(entries[offset:offset+20]):
                x,y=12+index%4*100,31+index//4*48
                vertices,faces=meshes[part["id"]]
                group={"part":part,"vertices":vertices,"print_vertices":vertices,"faces":faces}
                w,h,d=part["bounds_mm"]
                view=(0,0,-1) if part["id"].startswith("FIT-F") else (1,-2,3)
                image,_,_=projection([group],view,x,y+8,min(40/max(w,h,d,1),29/max(w,h,d,1)),colors)
                content+=image+text(x,y+3,part["id"],3)
                count=part["quantity"] if category=="assembly" else part.get("tool_quantity",1)
                content+=text(x+47,y+11,colors[part["color"]]["name_ja"],2.7)
                content+=text(x+47,y+17,f'{part["category"]} ×{count}',2.5)
                content+=text(x+47,y+23,f"{w:.2f} × {h:.2f}",2.6)+text(x+47,y+29,f"× {d:.2f} mm",2.6)
                if part.get("print_rotation_deg_xyz")==[180,0,0]:
                    content+=text(x+47,y+36,"前面ベッド / STL補正済み",2.3,"#b62731")
                content+=line(x,y+45,x+96,y+45)
            number=offset//20+1
            file=f"{base}{'' if number==1 else '-'+str(number)}.svg"
            emit(f"{title} / {number}",content,file,"CAD PRINT MASTERS")
    front,locate,_=projection(geometry,(0,-1,0),18,34,.95,colors)
    content=front+text(230,33,"後ろへ外すための前面接触点",4)
    targets=[("tile-001","通常インサート：面の中央"),("eye-left-white","白目：左の白い縁"),
             ("eye-left-iris","虹彩：下の青い帯"),("eye-left-pupil","瞳：中央"),
             ("badge-m","M：左の縦画"),("badge-white","白い丸：Mを外した後の下縁")]
    for i,(name,label) in enumerate(targets):
        item=next(g["instance"] for g in geometry if g["instance"]["id"]==name)
        tx,ty=item["tool_target_xy"]
        x,y=locate((tx,parameters["board"]["back_y"]-item["front_z"],parameters["board"]["bottom_z"]+ty))
        content+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.4" fill="#df303b"/>'
        content+=line(x,y,226,54+i*25,stroke_dasharray="1 1")+text(230,55+i*25,label,2.8)
        content+=text(230,62+i*25,f'座標({tx:g}, {ty:g}) / 先端回転 {item["tool_tip_rotation_deg"]}°',2.6)
    content+=text(230,219,"先端1.6×2.4 mm。初期押出は最大3.5 mm。",2.7)
    content+=text(230,228,"ここで工具を止め、フランジを指で引き抜く。",2.7)
    content+=text(230,237,"工具で最後まで押さない。9.5 mm押込は禁止。",2.7)
    emit("取り出し工具の接触点 / RELEASE ACCESS",content,"tool-access.svg","PUSH THEN GRIP THE REAR FLANGE")
    content=""
    parts={p["id"]:p for p in catalog["parts"]}
    for pid,offset,color in [("CAPTURE-FRAME",(0,0,0),"#426071"),("CAPTURE-COVER",(0,0,0),"#303841"),
                             ("IN-W-1x1",(-12,0,0),"#df303b"),("T04",(12,0,-16),"#187dd0")]:
        vertices,faces=meshes[pid]
        origin=parts[pid]["print_origin_mm"]
        angle=math.radians(-parts[pid].get("print_rotation_deg_xyz",[0,0,0])[0])
        c,s=math.cos(angle),math.sin(angle)
        raw=[tuple(p[i]+origin[i] for i in range(3)) for p in vertices]
        vertices=[(p[0]+offset[0],p[1]*c-p[2]*s+offset[1],p[1]*s+p[2]*c+offset[2]) for p in raw]
        segments=set()
        for indices in faces:
            triangle=[vertices[i] for i in indices]
            hits=[]
            for a,b in zip(triangle,triangle[1:]+triangle[:1]):
                if abs(a[1])<1e-7:hits.append((a[0],a[2]))
                if a[1]*b[1]<0:
                    f=-a[1]/(b[1]-a[1])
                    hits.append((a[0]+f*(b[0]-a[0]),a[2]+f*(b[2]-a[2])))
            points=sorted(set((round(a,5),round(b,5)) for a,b in hits))
            if len(points)==2:segments.add(tuple(points))
        for a,b in segments:
            content+=f'<path d="M{25+(a[0]+25)*4:.3f},{110-a[1]*4:.3f} L{25+(b[0]+25)*4:.3f},{110-b[1]*4:.3f}" fill="none" stroke="{color}" stroke-width=".24"/>'
        content+=text(25,198+list(["CAPTURE-FRAME","CAPTURE-COVER","IN-W-1x1","T04"]).index(pid)*9,pid,3,color)
    content+=text(18,27,"実CADメッシュ Y=0 断面。線色は部品の識別用。",3)
    notes = [
        ("前後の正の捕捉","窓6.0 / 軸5.6 / フランジ7.6","1セルの場合。重なり0.8、横遊び後も0.6。"),
        ("前枠・裏蓋","前枠6.4 / フランジ厚1.6 / 後ポケット1.8","後退側は裏蓋の段差で停止。摩擦で保持しない。"),
        ("交換用印刷粗ねじ","TR11.2-P3.2 / minor8.8 / 有効掛かり9.6","半径クリアランス0.3、軸形状余裕0.15。"),
        ("先に試す試験片","THREAD-C40→C30→C20 / 実T04ねじ","捕捉台は実IN-W-1x1＋T04を共用。"),
        ("文字moduleは共通正本","カード88×24×2 / 溝88.4×2.4×4.8","共通12×2の8mmピッチ / 実物clutch未確認。")
    ]
    for index, (heading, value, note) in enumerate(notes):
        y=40+index*39
        content+=text(238,y,heading,3.8)+text(238,y+8,value,2.8)+text(238,y+16,note,2.6)
    content+=text(18,248,f'文字直線ストローク実測{gauges["minimum_parallel_straight_stroke_mm"]:.3f} mm。0.2mmノズルを使用。',3)
    content+=text(18,260,"ねじ締結力、クリープ、着脱耐久は未試験。数値は設計候補で保証公差ではありません。",2.8)
    emit("捕捉・ねじ断面 / RETENTION SECTION",content,"interface-details.svg","ACTUAL CAD SECTION / NO ADHESIVE")
    return sheets


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
    count=sum(p["category"]=="assembly" for p in catalog["parts"])
    for index, note in enumerate([f'{count}種類 / 組込{len(catalog["instances"])}個 / 7色', "全パーツ取り外し・再組立可能", "防護用の盾ではありません",
                                  "市販ブロックとの接続は試験前提", "AMS不要。色別単色部品で構成",
                                  "PLA / 0.4 mm基準・文字は0.2 mm推奨", "非公式の個人記念品"]):
        content += text(270, 85+index*9, note, 3.5)
    page("完成図 / CAD ASSEMBLY", content, "assembly-isometric.svg")
    sheets=[{"file":"assembly-isometric.svg","title":"完成図","subtitle":"T2 FULLY REMOVABLE"},
            {"file":"three-views.svg","title":"三面図","subtitle":"FRONT / TOP / RIGHT"}]
    sheets+=expanded_views(geometry,catalog,meshes)
    (ROOT/"drawings/index.json").write_text(json.dumps({"revision":"T2","sheets":sheets},ensure_ascii=False,indent=2)+"\n")
    with (ROOT / "docs/bom.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["Part ID", "部品名", "色", "分類", "完成品組込数", "試験用推奨数", "工具数", "最大X mm", "最大Y mm", "最大Z mm",
                         "組立工程", "配置ID", "STL", "STEP"])
        for part in catalog["parts"]:
            instances = [item for item in catalog["instances"] if item["part"] == part["id"]]
            writer.writerow([part["id"], part["name_ja"], colors[part["color"]]["name_ja"],part["category"],part["quantity"],
                             1 if part["category"] == "coupon" else 0,part.get("tool_quantity",0),
                             *[round(v, 3) for v in part["bounds_mm"]],
                             ",".join(map(str, sorted({item["step"] for item in instances}))) or "0 試験",
                             ",".join(item["id"] for item in instances), part["mesh"], part["step"]])
    print("DRAWINGS_AND_BOM_GENERATED")


if __name__ == "__main__":
    main()
