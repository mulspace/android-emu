import json
from pathlib import Path
import socket
import sys
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from read_jit_stats import parse_stats, query
from run_debug import guest_command

TEXT = """Translation buffer state:
gen code size       12000/33554432
TB count            27
TB flush count      9
TB invalidate count 42
TLB flush count     510
"""


class JitTests(unittest.TestCase):
    def test_cache_options_stay_after_one_qemu_boundary(self):
        args = (Path('/emulator'), 'android-emu-debug-test', 5576, 'host',
                [Path('/isolated/userdata-qemu.img'), Path('/isolated/cache.img')])
        for smp in (False, True):
            command = guest_command(*args, experimental_arm_smp=smp, tcg_cache_mb=256,
                                    jit_monitor=Path('/private/jit.sock'))
            self.assertEqual(command.count('-qemu'), 1)
            self.assertLess(command.index('-qemu'), command.index('-tb-size'))
            self.assertEqual(command[-4:], ['-tb-size', '256', '-qmp',
                                           'unix:/private/jit.sock,server,nowait'])
            self.assertNotIn('-no-jni', command)
        for value in (True, 0, -1, 1024, '128'):
            with self.assertRaises(ValueError):
                guest_command(*args, tcg_cache_mb=value)
        for path in (Path('relative.sock'), Path('/bad,path'), Path('/' + 'a'*101)):
            with self.assertRaises(ValueError):
                guest_command(*args, jit_monitor=path)

    def test_stats_require_complete_unambiguous_values(self):
        self.assertEqual(parse_stats(TEXT)['tb_flushes'], 9)
        for bad in (TEXT.replace('12000/', '999999999/'), TEXT + 'TB count 1\n',
                    TEXT.replace('TB flush count', 'unknown'), ''):
            with self.assertRaises(ValueError):
                parse_stats(bad)

    def test_qmp_sends_only_fixed_read_command(self):
        client, server = socket.socketpair()
        requests = []
        errors = []
        def respond():
            try:
                with server, server.makefile('rb') as reader:
                    server.sendall(b'{"QMP": {}}\r\n')
                    for result in ({}, TEXT):
                        request = json.loads(reader.readline())
                        requests.append(request)
                        server.sendall(b'{"event":"STOP"}\r\n' +
                                       json.dumps({'id': request['id'], 'return': result}).encode() + b'\r\n')
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        with client:
            raw, metrics = query(client)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(raw, TEXT)
        self.assertEqual(metrics['capacity_bytes'], 33554432)
        self.assertEqual(requests, [{'execute':'qmp_capabilities','id':'capabilities'},
            {'execute':'human-monitor-command','id':'jit','arguments':{'command-line':'info jit'}}])

    def test_qmp_rejects_missing_greeting(self):
        client, server = socket.socketpair()
        with client, server:
            server.sendall(b'{"return":{}}\n')
            with self.assertRaises(ValueError):
                query(client)
