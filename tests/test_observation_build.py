from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_observation_probe import retry_incomplete_checked, hierarchy_retry_delay

class CheckedBuild(unittest.TestCase):
    def test_rejects_source_drift_or_ambiguous_transformation(self):
        anchor="if (expected != null || attempt == 2) throw changed;"
        for source in ("", anchor + anchor):
            with self.assertRaises(ValueError): retry_incomplete_checked(source)

    def test_pause_is_scoped_to_original_snapshot_request_only(self):
        pause = "SystemClock.sleep(25L); alive();"
        source = pause + "\n    private static JSONObject captureSnapshot(Args args) {\n" + pause + "\n" + pause + "\n}\n    private static void input() {" + pause + "}"
        self.assertEqual(hierarchy_retry_delay(source, 25), source)
        result = hierarchy_retry_delay(source, 1000)
        self.assertEqual(result.count("SystemClock.sleep(1000L)"), 2)
        self.assertTrue(result.startswith(pause))
        self.assertTrue(result.endswith(pause + "}"))
        for delay in (-1, 0, 2000):
            with self.assertRaises(ValueError): hierarchy_retry_delay(source, delay)
        with self.assertRaises(ValueError): hierarchy_retry_delay(source.replace(pause, "", 2), 1000)
