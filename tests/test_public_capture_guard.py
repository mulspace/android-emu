import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from probe_public_capture import owned_run


class OwnedCaptureTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
