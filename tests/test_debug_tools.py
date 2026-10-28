import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_archives import safe_extract
from owned_process import run, stop_group
from build_debug import configuration
from sync_gitiles_tree import git_blob


class ArchiveTests(unittest.TestCase):
    def archive(self, path, entries):
        with tarfile.open(path, "w:gz") as tf:
            for name, target in entries:
                item = tarfile.TarInfo(name)
                if target is None:
                    item.size = 2
                    tf.addfile(item, io.BytesIO(b"ok"))
                else:
                    item.type = tarfile.SYMTYPE
                    item.linkname = target
                    tf.addfile(item)

    def test_rejects_traversal_and_external_symlinks(self):
        for entry in (("../escape", None), ("/absolute", None), ("link", "/etc/passwd"), ("link", "../../escape")):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.archive(root / "test.tgz", [entry])
                with self.assertRaises((ValueError, tarfile.FilterError)):
                    safe_extract(root / "test.tgz", root / "dest")
                self.assertFalse((root / "escape").exists())

    def test_allows_aosp_cross_project_link_without_writing_through_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "aosp/device/generic/.temporary"
            final = root / "aosp/device/generic/vulkan-cereal"
            dest.mkdir(parents=True)
            self.archive(root / "test.tgz", [("local", None), ("testenvs/mock", "../../../../external/qemu/guest")])
            safe_extract(root / "test.tgz", dest, final_destination=final, allowed_root=root / "aosp")
            self.assertEqual((dest / "local").read_text(), "ok")
            self.assertTrue((dest / "testenvs/mock").is_symlink())
            self.assertFalse((root / "aosp/external/qemu/guest").exists())

    def test_rejects_archive_that_writes_under_deferred_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.archive(root / "test.tgz", [("link", "../other"), ("link/file", None)])
            with self.assertRaises(ValueError):
                safe_extract(root / "test.tgz", root / "dest", allowed_root=root)
            self.assertFalse((root / "other/file").exists())


class ProcessTests(unittest.TestCase):
    def test_timeout_terminates_the_owned_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pid"
            command = [sys.executable, "-c", "import os,time,pathlib; pathlib.Path(__import__('sys').argv[1]).write_text(str(os.getpid())); time.sleep(60)", str(pidfile)]
            with self.assertRaises(subprocess.TimeoutExpired):
                run(command, timeout=1)
            pid = int(pidfile.read_text())
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_stop_escalates_for_only_the_owned_group(self):
        process = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(60)"], stdout=subprocess.PIPE, start_new_session=True, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "ready")
            stop_group(process, grace=.2)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            with self.assertRaises(ProcessLookupError): os.killpg(process.pid, 0)
        finally:
            if process.poll() is None: stop_group(process, grace=.2)
            process.stdout.close()


class BuildTests(unittest.TestCase):
    def test_blob_digest_matches_git_object_format(self):
        self.assertEqual(git_blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(git_blob(b"test\n"), "9daeafb9864cf43055ae93beb0afd6c7d144bfa4")

    def test_arm32_symbols_and_no_upload_are_explicit(self):
        args = configuration(Path('/source'), Path('/build'), Path('/cmake'), Path('/ninja'))
        for flag in ("-DCMAKE_BUILD_TYPE=Debug", "-DOPTION_MINBUILD=OFF", "-DOPTION_CRASHUPLOAD=NONE", "-DOPTION_ASAN_IN_DEBUG=OFF", "-DWEBRTC=OFF"):
            self.assertIn(flag, args)


if __name__ == "__main__": unittest.main()
