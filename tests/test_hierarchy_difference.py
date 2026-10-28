from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK required")
class Difference(unittest.TestCase):
    def test_numeric_diagnostics_never_return_ui_values_or_accept_changed_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["javac", "-d", tmp,
                str(ROOT / "experimental/native/HierarchyDifference.java"),
                str(ROOT / "tests/guest/HierarchyDifferenceProbe.java")], check=True, timeout=30)
            subprocess.run(["java", "-cp", tmp, "HierarchyDifferenceProbe"], check=True, timeout=15)
