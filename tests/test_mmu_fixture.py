import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_mmu_fixture import validate_result


class MmuFixtureTests(unittest.TestCase):
    def good(self):
        return {"passed": True, "cpu_count": 2, "remap_rounds": 24,
                "permission_faults": 2, "arm_code_updates": True, "code_updates": 48,
                "pages128_seconds": .01, "pages512_seconds": .02,
                "pages2048_seconds": .04, "total_seconds": .5}

    def test_accepts_complete_arm_results(self):
        self.assertEqual(validate_result(json.dumps(self.good())), self.good())

    def test_rejects_host_only_or_partial_verification(self):
        for key, value in (("arm_code_updates", False), ("code_updates", 0),
                           ("passed", 1), ("cpu_count", 1), ("permission_faults", 1),
                           ("pages128_seconds", -1), ("total_seconds", float("nan"))):
            with self.subTest(key=key):
                data = self.good(); data[key] = value
                with self.assertRaises(ValueError):
                    validate_result(json.dumps(data))
