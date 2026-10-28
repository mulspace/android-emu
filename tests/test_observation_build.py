from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_observation_probe import retry_incomplete_checked

class CheckedBuild(unittest.TestCase):
    def test_rejects_source_drift_or_ambiguous_transformation(self):
        anchor="if (expected != null || attempt == 2) throw changed;"
        for source in ("", anchor + anchor):
            with self.assertRaises(ValueError): retry_incomplete_checked(source)
