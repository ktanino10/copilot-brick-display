"""Create the complete native/STEP/STL assembly; run with FreeCAD's Python."""
import json
from pathlib import Path
import subprocess
import sys

import FreeCAD as App

from export_artifacts import export_artifacts
from relief_geometry import relief_depths, relief_shapes
from shared_source import load_shared
from stand_geometry import custom_coupons, stand_body

ROOT = Path(__file__).resolve().parents[1]


def build_shapes(data):
    common, shared, interface, shared_catalog = load_shared(ROOT)
    if data["message"] != shared["message"]["lines"]:
        raise ValueError("Confirmed message differs from shared message source")
    if data["nominal_pitch"] != shared["interface"]["pitch"]:
        raise ValueError("Nominal pitch differs from shared interface")
    shapes = relief_shapes(data)
    specs = {p["id"]: {"name_ja": p["name_ja"], "color": p["color"],
                       "category": "assembly", "source": "parameters.json"}
             for p in data["parts"]}
    stand = stand_body(data)
    origin = data["stand"]["dock_origin"]
    pitch = data["nominal_pitch"]
    studs = [common.stud_shape(origin[0] + (x + .5) * pitch,
                              origin[1] + (y + .5) * pitch, origin[2], shared["interface"])
             for x in range(12) for y in range(2)]
    shapes = {"T01": stand.multiFuse(studs).removeSplitter(), **shapes}
    specs["T01"] = {"name_ja": "台座・背板ソケット・共通24スタッド", "color": "charcoal",
                     "category": "assembly", "source": "parameters.json + shared stud_shape"}
    depths = relief_depths(data)
    instances = [{"id": "stand", "part": "T01", "parent": None, "step": 1,
                  "position_mm": [0, 0, 0], "rotation_x_deg": 0}]
    for item in data["instances"]:
        instances.append({**item, "parent": item["parent"] or "stand",
                          "position_mm": [item["xy"][0], data["board"]["back_y"] - depths[item["id"]],
                                          data["board"]["bottom_z"] + item["xy"][1]],
                          "rotation_x_deg": 90})
    for spec in shared_catalog["parts"].values():
        part_id = spec["id"]
        if part_id not in ("MSG-DOCK", "MSG-CARD") and not part_id.startswith("FIT-"):
            continue
        shapes[part_id] = common.shape_for(spec, shared, ROOT)
        is_card = part_id == "MSG-CARD"
        specs[part_id] = {"name_ja": "交換文字カード" if is_card else
                         "共通メッセージドック" if part_id == "MSG-DOCK" else "共通嵌合試験片",
                         "color": "white" if is_card else "charcoal",
                         "category": "coupon" if part_id.startswith("FIT-") else "assembly",
                         "source": f"shared design/catalog.json#{part_id}",
                         "shared_spec": spec}
        if is_card:
            specs[part_id]["optional_color_change_z_mm"] = shared["message"]["card_thickness"]
    instances += [
        {"id": "message-dock", "part": "MSG-DOCK", "parent": "stand", "step": 9,
         "position_mm": origin, "rotation_x_deg": 0},
        {"id": "message-card", "part": "MSG-CARD", "parent": "message-dock", "step": 10,
         "position_mm": [origin[0] + 4, origin[1] + 5, origin[2] + 4.8], "rotation_x_deg": 90}
    ]
    names = ["背板ソケット試験片 A–D", "背板厚6.4の試験舌", "色タイル位置決め試験台", "色タイル試験蓋"]
    for (part_id, shape), name in zip(custom_coupons(data).items(), names):
        shapes[part_id] = shape
        specs[part_id] = {"name_ja": name, "color": "charcoal", "category": "coupon",
                         "source": "parameters.json#custom_coupons"}
    return specs, shapes, instances, interface


def main():
    from PySide6 import QtWidgets
    import FreeCADGui as Gui
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    Gui.showMainWindow()
    data = json.loads((ROOT / "parameters.json").read_text())
    print("CAD_BUILD_SHAPES", flush=True)
    specs, shapes, instances, interface = build_shapes(data)
    catalog = export_artifacts(ROOT, data, specs, shapes, instances)
    catalog["shared_interface"] = interface
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    Gui.getMainWindow().close()
    print("CAD_VERIFY_NATIVE_SUBPROCESS", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/verify_native.py")], check=True)
    print(f"EXPORTED {len(shapes)} unique printable parts, {len(instances)} assembly instances; native reopened",
          flush=True)


if __name__ == "__main__":
    main()
