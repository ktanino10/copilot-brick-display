"""Print occurrence/assembly correspondence must not invent identities or move any input."""

from collections import Counter
from copy import deepcopy
import gzip
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_assembly_guide import CORE, build_mapping, load_mesh, read_json, verify_plate


class AssemblyGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read_json(ROOT / "design/catalog.json")
        cls.results = {}
        for model in "ABC":
            folder = ROOT / "site/downloads" / model
            assembly = read_json(folder / "assembly.json")
            manifest = read_json(folder / "plates/manifest.json")
            cls.results[model] = build_mapping(cls.catalog, assembly, manifest, ROOT / "site/downloads", folder / "plates")

    def test_all_occurrences_keep_original_geometry_pose_color_and_steps(self):
        for model, count in (("A", 91), ("B", 150), ("C", 228)):
            mapping, meshes = self.results[model]
            self.assertEqual(mapping["part_count"], count)
            self.assertEqual(sum(len(p["slots"]) for p in mapping["plates"]), count)
            original = read_json(ROOT / f"site/downloads/{model}/assembly.json")
            for old, new in zip(original["placements"], mapping["placements"]):
                for key in ("id", "part", "color", "position", "rotation", "step", "role"):
                    self.assertEqual(old[key], new[key])
            for part, mesh in meshes.items():
                master = ROOT / "site/downloads" / self.catalog["parts"][part]["stl"]
                decoded = gzip.decompress(base64.b64decode(mesh["payload"]))
                self.assertEqual(decoded, master.read_bytes())
                self.assertEqual(hashlib.sha256(decoded).hexdigest(), mapping["parts"][part]["sha256"])

    def test_b_first_base_is_second_black_file_slot_three(self):
        mapping, _ = self.results["B"]
        first = mapping["first_source"]
        self.assertEqual((first["plate"], first["slot"], first["suggested_placement"]),
                         ("B-black-02.3mf", 3, "B-001"))
        self.assertEqual(mapping["placements"][0]["part"], "BASE3-24x10-B-562406")
        self.assertEqual(mapping["placements"][0]["step"], 1)
        self.assertEqual(mapping["base_source_files"], [f"B-black-{n:02}.3mf" for n in range(1, 5)])

    def test_interchangeable_sources_and_destinations_are_complete_not_personal_identities(self):
        mapping, _ = self.results["B"]
        group = mapping["groups"]["BASE3-06x10-T-838259|black"]
        self.assertEqual(group["placements"], ["B-003", "B-007", "B-008", "B-012", "B-016", "B-017"])
        self.assertEqual(Counter(s["plate"] for s in group["sources"]), {"B-black-03.3mf": 4, "B-black-04.3mf": 2})
        self.assertEqual({s["suggested_placement"] for s in group["sources"]}, set(group["placements"]))
        self.assertFalse(mapping["slot_numbers_are_physical_markings"])
        for plate in mapping["plates"]:
            for slot in plate["slots"]:
                self.assertEqual(slot["candidate_placements"], mapping["groups"][slot["group"]]["placements"])

    def test_front_modules_and_keepers_precede_face_and_have_actual_rotation(self):
        mapping, _ = self.results["B"]
        for p in mapping["placements"]:
            if p["role"] == "front_module":
                self.assertEqual(p["step"], 6)
                self.assertEqual(p["rotation"], [90, 0, 0])
            elif p["role"] == "keeper":
                self.assertEqual(p["step"], 7)
            elif p["role"] in ("face", "crest"):
                self.assertGreaterEqual(p["step"], 8)
        self.assertEqual(mapping["motion"]["module_lift_mm"], 45)
        self.assertGreaterEqual(mapping["motion"]["module_front_mm"], 32)
        self.assertFalse(mapping["sliced"])
        self.assertFalse(mapping["physical_fit_tested"])

    def test_missing_or_wrong_color_print_occurrence_is_rejected(self):
        folder = ROOT / "site/downloads/B"
        assembly = read_json(folder / "assembly.json")
        for mutation in ("missing", "color"):
            manifest = read_json(folder / "plates/manifest.json")
            if mutation == "missing":
                manifest["plates"][0]["items"].pop()
            else:
                manifest["plates"][0]["color"] = "cyan"
            with self.assertRaisesRegex(ValueError, "quantities exactly"):
                build_mapping(self.catalog, assembly, manifest, ROOT / "site/downloads", folder / "plates")

    def test_changed_pose_or_step_is_rejected(self):
        folder = ROOT / "site/downloads/B"
        for key, replacement in (("position", [1, 0, 0]), ("step", 2)):
            assembly = read_json(folder / "assembly.json")
            assembly["placements"][0][key] = replacement
            with self.assertRaisesRegex(ValueError, "placements differ"):
                build_mapping(self.catalog, assembly, read_json(folder / "plates/manifest.json"),
                              ROOT / "site/downloads", folder / "plates")

    def test_real_3mf_transform_is_checked_not_just_manifest(self):
        folder = ROOT / "site/downloads/B/plates"
        plate = read_json(folder / "manifest.json")["plates"][1]
        fingerprints = {}
        for item in plate["items"]:
            spec = self.catalog["parts"][item["part"]]
            _, fingerprints[item["part"]] = load_mesh(ROOT / "site/downloads" / spec["stl"], spec)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / plate["file"]
            with zipfile.ZipFile(folder / plate["file"]) as source, zipfile.ZipFile(target, "w") as result:
                for name in source.namelist():
                    content = source.read(name)
                    if name == "3D/3dmodel.model":
                        node = ET.fromstring(content)
                        node.find(CORE + "build")[2].set("transform", "1 0 0 0 1 0 0 0 1 0 0 0")
                        content = ET.tostring(node)
                    result.writestr(name, content)
            with self.assertRaisesRegex(ValueError, "transform differs"):
                verify_plate(target, plate, fingerprints)


if __name__ == "__main__":
    unittest.main()
