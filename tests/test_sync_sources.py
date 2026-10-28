import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_sources import validate_project


class SourceContractTests(unittest.TestCase):
    def test_rejects_mutable_revisions_untrusted_upstreams_and_escaping_paths(self):
        base = {"path": "external/qemu", "revision": "1" * 40, "url": "https://android.googlesource.com/platform/external/qemu"}
        validate_project(base)
        for key, value in (("path", "../escape"), ("path", "/tmp/escape"), ("revision", "main"), ("url", "https://example.com/source")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_project({**base, key: value})


if __name__ == "__main__":
    unittest.main()
