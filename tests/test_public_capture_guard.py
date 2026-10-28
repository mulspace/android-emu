import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from probe_public_capture import owned_run, validate_checked_pair
from validate_capture_receipts import retained_options


class OwnedCaptureTests(unittest.TestCase):
    def test_direct_mode_requires_exact_engine_and_original_process_identity(self):
        for mode in ('valid', 'wrong_binary', 'reused_pid', 'missing_identity', 'wrong_group', 'unknown_mode'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); run = root/'run'; proc = root/'proc'; run.mkdir(); (proc/'100').mkdir(parents=True)
                receipt = {'serial':'emulator-5576','owned_pgid':100,'owned_start_ticks':'500',
                           'debugger':'unknown' if mode=='unknown_mode' else 'none',
                           'command':['/candidate/emulator','-avd','android-emu-debug-fixture','-port','5576']}
                if mode=='missing_identity': receipt.pop('owned_start_ticks')
                (run/'started.json').write_text(json.dumps(receipt))
                binary=b'/candidate/qemu/linux-x86_64/qemu-system-armel-headless' if mode!='wrong_binary' else b'/usr/bin/python3'
                (proc/'100/cmdline').write_bytes(b'\0'.join([binary,b'-avd',b'android-emu-debug-fixture',b'-port',b'5576']))
                stat=['S','1','101' if mode=='wrong_group' else '100']+['0']*16+['501' if mode=='reused_pid' else '500']
                (proc/'100/stat').write_text('100 (emulator) '+' '.join(stat))
                if mode=='valid': owned_run(run,'emulator-5576',proc)
                else:
                    with self.assertRaises(ValueError): owned_run(run,'emulator-5576',proc)

    def test_only_live_owned_emulator_process_is_accepted(self):
        for mode in ('valid', 'physical', 'wrong_serial', 'finished', 'wrong_port', 'wrong_avd', 'missing_process', 'invalid_pid'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run, proc = root / 'run', root / 'proc'
                run.mkdir()
                (proc / '100').mkdir(parents=True)
                serial = 'physical-device' if mode == 'physical' else 'emulator-5576'
                receipt = {'serial': 'emulator-5578' if mode == 'wrong_serial' else serial,
                           'owned_pgid': True if mode == 'invalid_pid' else 100}
                (run / 'started.json').write_text(json.dumps(receipt))
                if mode == 'finished':
                    (run / 'ended.json').write_text('{}')
                port = b'5578' if mode == 'wrong_port' else b'5576'
                avd = b'production' if mode == 'wrong_avd' else b'android-emu-debug-fixture'
                if mode != 'missing_process':
                    (proc / '100/cmdline').write_bytes(b'\0'.join([b'gdb', b'--args', b'emulator', b'-port', port, b'-avd', avd]))
                if mode == 'valid':
                    owned_run(run, serial, proc)
                else:
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        owned_run(run, serial, proc)


class CheckedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.observed = {'frame_ref': 'frame-1', 'foreground_package': 'example.app',
                         'width': 720, 'height': 1280, 'rotation': 0,
                         'hierarchy_xml': '<hierarchy><node text="quote"/></hierarchy>'}
        self.captured = dict(self.observed, frame_ref='frame-2', based_on_frame_ref='frame-1')

    def test_image_is_bound_to_exact_observation(self):
        validate_checked_pair(self.observed, self.captured)

    def test_changed_or_missing_evidence_is_rejected(self):
        for key, changed in [('based_on_frame_ref', 'frame-old'),
                             ('foreground_package', 'android'), ('width', 1080),
                             ('height', 1920), ('rotation', 1),
                             ('hierarchy_xml', '<hierarchy/>')]:
            for missing in (True, False):
                with self.subTest(key=key, missing=missing):
                    candidate = dict(self.captured)
                    if missing:
                        candidate.pop(key)
                    else:
                        candidate[key] = changed
                    with self.assertRaises(ValueError):
                        validate_checked_pair(self.observed, candidate)

    def test_missing_observation_reference_is_rejected(self):
        for reference in (None, '', 42):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                validate_checked_pair(dict(self.observed, frame_ref=reference), self.captured)

    def test_replay_uses_original_request_and_checks_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observe_options = {'include_image': False, 'include_xml': True}
            (root / 'snapshot_1_observe.request.json').write_text(json.dumps(observe_options))
            self.assertEqual(retained_options(root, 'snapshot_1_observe', self.observed), observe_options)
            (root / 'snapshot_1_observe.wire.json').write_text(json.dumps(self.observed))
            options = {'include_image': True, 'include_xml': True, 'image_format': 'jpeg',
                       'expected_frame_ref': 'frame-1'}
            (root / 'snapshot_1_checked.request.json').write_text(json.dumps(options))
            self.assertEqual(retained_options(root, 'snapshot_1_checked', self.captured), options)
            options['expected_frame_ref'] = 'old-frame'
            (root / 'snapshot_1_checked.request.json').write_text(json.dumps(options))
            with self.assertRaises(ValueError):
                retained_options(root, 'snapshot_1_checked', self.captured)

    def test_legacy_receipt_supported_but_checked_requests_cannot_be_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(retained_options(root, 'snapshot_1', {}),
                             {'include_image': True, 'include_xml': True, 'image_format': 'jpeg'})
            for suffix in ('observe', 'checked'):
                with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                    retained_options(root, 'snapshot_1_' + suffix, {})


if __name__ == '__main__':
    unittest.main()
