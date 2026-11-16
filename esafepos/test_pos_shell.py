import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from esafepos.www import pos


class PosShellRevisionTests(unittest.TestCase):
    def test_same_release_gets_new_revision_when_assets_change(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pos.frappe, "get_app_path", return_value=folder):
            assets = Path(folder)
            for name in ("pos.js", "pos.css", "sw.js", "manifest.json"):
                (assets / name).write_text("original", encoding="utf-8")
            original = pos._shell_revision("0.69.5")
            self.assertRegex(original, r"^0\.69\.5-[0-9a-f]{16}$")
            self.assertEqual(pos._shell_revision("0.69.5"), original)
            (assets / "pos.js").write_text("changed bundle", encoding="utf-8")
            self.assertNotEqual(pos._shell_revision("0.69.5"), original)

    def test_missing_build_falls_back_to_release(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pos.frappe, "get_app_path", return_value=folder):
            self.assertEqual(pos._shell_revision("0.69.5"), "0.69.5")
