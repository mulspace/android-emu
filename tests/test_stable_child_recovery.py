from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "scripts"))
from build_observation_probe import recover_stable_child

class StableChildRecoveryTests(unittest.TestCase):
    def test_source_transform_requires_exact_shape(self):
        source=(ROOT/"experimental/native/AndroidHierarchy.java").read_text()
        candidate=recover_stable_child(source)
        self.assertEqual(candidate.count("StableChildRecovery.recover("),1)
        self.assertIn('getMethod("getChildId",int.class)',candidate)
        for bad in ("", source+source, candidate):
            with self.assertRaises(ValueError): recover_stable_child(bad)

    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"),"JDK required")
    def test_identity_changes_and_missing_nodes_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(["javac","-d",folder,
                str(ROOT/"experimental/native/StableChildRecovery.java"),
                str(ROOT/"tests/guest/StableChildRecoveryProbe.java")],check=True,timeout=30)
            result=subprocess.run(["java","-cp",folder,"StableChildRecoveryProbe"],check=True,timeout=15,capture_output=True,text=True)
            self.assertIn("11 stable-child recovery scenarios passed",result.stdout)
