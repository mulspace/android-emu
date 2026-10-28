import io
import hashlib
import os
from pathlib import Path
import signal
import struct
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
from apply_patches import source_state, reviewed_patches
from sync_gitiles_tree import git_blob
from run_debug import isolated_avd_paths, guest_command, check_local_overlay


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


class PatchTests(unittest.TestCase):
    def test_rejects_changed_and_partially_applied_source(self):
        digest = lambda data: hashlib.sha256(data).hexdigest()
        manifest = {"files": {name: {"before_sha256": digest(b"old"),
                     "after_sha256": digest(b"new")} for name in ("one.c", "two.c")}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in manifest["files"]: (root / name).write_bytes(b"old")
            self.assertEqual(source_state(root, manifest), "unpatched")
            (root / "one.c").write_bytes(b"new")
            with self.assertRaisesRegex(ValueError, "Mixed"):
                source_state(root, manifest)
            (root / "two.c").write_bytes(b"new")
            self.assertEqual(source_state(root, manifest), "patched")
            (root / "one.c").write_bytes(b"unrelated work")
            with self.assertRaisesRegex(ValueError, "differs"):
                source_state(root, manifest)
            self.assertEqual((root / "one.c").read_bytes(), b"unrelated work")


    def test_upgrade_preserves_an_applied_patch_and_rejects_tampering(self):
        digest = lambda data: hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            patches = root / "patches"
            source.mkdir()
            patches.mkdir()
            manifest = {"files": {}, "patches": []}
            for number in (1, 2):
                name = str(number) + ".c"
                patch = str(number) + ".patch"
                (source / name).write_bytes(b"new" if number == 1 else b"old")
                (patches / patch).write_bytes(b"reviewed diff" + bytes([number]))
                manifest["files"][name] = {"before_sha256": digest(b"old"), "after_sha256": digest(b"new")}
                manifest["patches"].append({"path": patch, "sha256": digest((patches / patch).read_bytes()), "files": [name]})
            self.assertEqual([state for _, state in reviewed_patches(source, manifest, patches)],
                             ["patched", "unpatched"])
            (patches / "2.patch").write_bytes(b"unreviewed change")
            with self.assertRaisesRegex(ValueError, "checksum"):
                reviewed_patches(source, manifest, patches)
            self.assertEqual((source / "1.c").read_bytes(), b"new")
            self.assertEqual((source / "2.c").read_bytes(), b"old")


class BuildTests(unittest.TestCase):
    def test_optimized_build_keeps_symbols_and_rejects_release(self):
        paths = [Path(p) for p in ('/source', '/build', '/cmake', '/ninja')]
        self.assertIn('-DCMAKE_BUILD_TYPE=RelWithDebInfo', configuration(*paths, 'RelWithDebInfo'))
        with self.assertRaises(ValueError):
            configuration(*paths, 'Release')

    def test_blob_digest_matches_git_object_format(self):
        self.assertEqual(git_blob(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(git_blob(b"test\n"), "9daeafb9864cf43055ae93beb0afd6c7d144bfa4")

    def test_arm32_symbols_and_no_upload_are_explicit(self):
        args = configuration(Path('/source'), Path('/build'), Path('/cmake'), Path('/ninja'))
        self.assertIn("-H/source", args)
        self.assertIn("-B/build", args)
        self.assertNotIn("-S", args)
        for flag in ("-DCMAKE_BUILD_TYPE=Debug", "-DOPTION_MINBUILD=OFF", "-DOPTION_CRASHUPLOAD=NONE", "-DOPTION_ASAN_IN_DEBUG=OFF", "-DWEBRTC=OFF"):
            self.assertIn(flag, args)




class IsolatedGuestTests(unittest.TestCase):
    def test_four_core_experiment_keeps_wrapper_and_engine_in_agreement(self):
        disks = [Path('/isolated/userdata-qemu.img'), Path('/isolated/cache.img')]
        args = (Path('/emulator'), 'android-emu-debug-test', 5576, 'host', disks)
        command = guest_command(*args, experimental_arm_smp=True, arm_vcpus=4)
        self.assertEqual(command[command.index('-cores') + 1], '4')
        self.assertEqual(command[command.index('-smp') + 1], '4')
        self.assertNotIn('-no-jni', command)
        for value in (True, 1, 3, 8, '4'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                guest_command(*args, experimental_arm_smp=True, arm_vcpus=value)
        with self.assertRaises(ValueError):
            guest_command(*args, arm_vcpus=4)

    def test_qcow_backing_cannot_escape_the_cloned_avd(self):
        with tempfile.TemporaryDirectory() as tmp:
            disk = Path(tmp) / 'userdata-qemu.img'
            disk.write_bytes(b'base')
            overlay = disk.with_name(disk.name + '.qcow2')
            def write_header(backing, features=0):
                header = bytearray(104)
                struct.pack_into('>IIQI', header, 0, 0x514649fb, 3, 104, len(backing))
                struct.pack_into('>Q', header, 72, features)
                overlay.write_bytes(header + backing)
            write_header(disk.name.encode())
            check_local_overlay(disk)
            for backing in (b'../another-guest.img', b'/outside/userdata-qemu.img', b'file:/outside'):
                write_header(backing)
                with self.assertRaisesRegex(ValueError, 'own local base'):
                    check_local_overlay(disk)
            write_header(disk.name.encode(), features=4)
            with self.assertRaisesRegex(ValueError, 'features'):
                check_local_overlay(disk)
            self.assertEqual(disk.read_bytes(), b'base')

    def test_existing_layers_require_matching_image_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            name = 'android-emu-debug-test'
            avd = home / (name + '.avd')
            avd.mkdir()
            (home / (name + '.ini')).write_text('path=' + str(avd) + '\n')
            for disk in ['userdata-qemu.img', 'cache.img']:
                (avd / disk).write_bytes(b'base')
            backing = b'userdata-qemu.img'
            header = bytearray(104)
            struct.pack_into('>IIQI', header, 0, 0x514649fb, 3, 104, len(backing))
            overlay = avd / 'userdata-qemu.img.qcow2'
            overlay.write_bytes(header + backing)
            original = overlay.read_bytes()
            with self.assertRaisesRegex(ValueError, 'image-version marker'):
                isolated_avd_paths(home, name)
            image = home / 'system'
            image.mkdir()
            (image / 'build.prop').write_text('ro.build.version.incremental=123\n')
            (avd / 'config.ini').write_text('image.sysdir.1=' + str(image) + '\n')
            (avd / 'version_num.cache').write_text('122\n')
            with self.assertRaisesRegex(ValueError, 'Image-version mismatch'):
                isolated_avd_paths(home, name)
            (avd / 'version_num.cache').write_text('123\n')
            self.assertEqual(len(isolated_avd_paths(home, name)), 2)
            self.assertEqual(overlay.read_bytes(), original)

    def test_rejects_registration_and_disk_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            name = "android-emu-debug-test"
            avd = home / (name + ".avd")
            avd.mkdir()
            ini = home / (name + ".ini")
            ini.write_text("path=/outside/avd\n")
            with self.assertRaisesRegex(ValueError, "registration"):
                isolated_avd_paths(home, name)
            ini.write_text("path=" + str(avd) + "\n")
            external = home / "another-guest-disk"
            external.write_bytes(b"preserve")
            (avd / "userdata-qemu.img").symlink_to(external)
            (avd / "cache.img").write_bytes(b"cache")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                isolated_avd_paths(home, name)
            (avd / "userdata-qemu.img").unlink()
            os.link(external, avd / "userdata-qemu.img")
            with self.assertRaisesRegex(ValueError, "hardlinked"):
                isolated_avd_paths(home, name)
            self.assertEqual(external.read_bytes(), b"preserve")
            (avd / "userdata-qemu.img").unlink()
            (avd / "userdata-qemu.img").write_bytes(b"own")
            disks = isolated_avd_paths(home, name)
            command = guest_command(Path('/emulator'), name, 5576, 'host', disks)
            self.assertEqual(command[command.index('-data') + 1], str(disks[0]))
            self.assertNotIn('-qemu', command)
            self.assertNotIn('-no-jni', command)
            experiment = guest_command(Path('/emulator'), name, 5576, 'host', disks,
                                       experimental_arm_smp=True)
            self.assertEqual(experiment[-7:], ['-qemu', '-cpu', 'cortex-a15', '-smp',
                                              '2', '-accel', 'tcg,thread=multi'])
            performance = guest_command(Path('/emulator'), name, 5576, 'host', disks,
                                        experimental_arm_smp=True, disable_jni_checks=True)
            self.assertLess(performance.index('-no-jni'), performance.index('-qemu'))
            self.assertEqual(performance[-7:], experiment[-7:])

if __name__ == "__main__": unittest.main()
