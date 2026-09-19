import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from personalization import GENERIC_LINES, load_private, private_output, strict_object, validate_lines, validate_public


class PersonalizationTests(unittest.TestCase):
    def setUp(self):
        self.parameters = json.loads((ROOT / "design/parameters.json").read_text())
        self.policy = json.loads((ROOT / "design/publication-policy.json").read_text())

    def test_public_defaults_are_unambiguous_placeholders(self):
        self.assertEqual(self.policy["mode"], "generic")
        self.assertFalse(self.policy["public_text_approved"])
        self.assertEqual(self.parameters["message"]["lines"], GENERIC_LINES)
        validate_public(self.parameters, self.policy)

    def test_public_custom_text_needs_explicit_approval(self):
        self.parameters["message"]["lines"] = ["CUSTOM DISPLAY LABEL", "CUSTOM ACCOUNT LABEL"]
        with self.assertRaises(ValueError):
            validate_public(self.parameters, self.policy)
        self.policy["mode"] = "public_personalization"
        with self.assertRaises(ValueError):
            validate_public(self.parameters, self.policy)
        self.policy["public_text_approved"] = True
        validate_public(self.parameters, self.policy)

    def test_unknown_mode_glyph_long_or_extra_lines_fail_without_truncation(self):
        for lines in (["ONE"], ["ONE", "TWO", "THREE"], ["X" * 121, "LABEL"],
                      [" LABEL", "LABEL"], ["LABEL\nNEXT", "LABEL"], ["未対応", "LABEL"],
                      ["<script>", "LABEL"], [42, "LABEL"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                validate_lines(lines)
        self.policy["mode"] = "private"
        with self.assertRaises(ValueError):
            validate_public(self.parameters, self.policy)

    def test_private_schema_and_output_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            data = {"schema_version": 1, "visibility": "private", "model": "B", "lines": GENERIC_LINES}
            path.write_text(json.dumps(data))
            self.assertEqual(load_private(path), data)
            path.write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaises(ValueError):
                load_private(path)
            path.write_text(json.dumps({**data, "font": "/unapproved/input"}))
            with self.assertRaises(ValueError):
                load_private(path)
            path.write_text(json.dumps({**data, "schema_version": True}))
            with self.assertRaises(ValueError):
                load_private(path)
        with self.assertRaises(ValueError):
            private_output(ROOT / "site/downloads")
        with self.assertRaises(ValueError):
            load_private(ROOT / "design/personalization.private.example.json")
        ignored = subprocess.run(["git", "check-ignore", ".private/personalization.json",
                                  ".private/generated/B/plate.FCStd"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ignored.returncode, 0)
        self.assertEqual(len(ignored.stdout.splitlines()), 2)

    def test_guidance_has_both_routes_and_actual_commands(self):
        text = (ROOT / "docs/customize.ja.md").read_text()
        for phrase in ("公開repoのforkは公開", "Assignees", "Optional prompt", "@copilot",
                       "private repo", "scripts/personalize_plate.py", "public_text_approved",
                       "BLOCKED", "GitHub Actions", "勝手にPRしません", "secret"):
            self.assertIn(phrase, text)
        form = (ROOT / ".github/ISSUE_TEMPLATE/personalize.yml").read_text()
        self.assertIn("github.com/YOUR-USERNAME", form)
        self.assertIn("非公開", form)


if __name__ == "__main__":
    unittest.main()
