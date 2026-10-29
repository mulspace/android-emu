import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from transition_read_budget import call_with_transition_budget


@dataclass(frozen=True)
class Timing:
    snapshot_seconds: int = 30
    launch_seconds: int = 125
    input_seconds: int = 8


class TransitionBudget(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, operation='android.snapshot', phase='broker_quote_entry_1',
                       options=None, seconds=45, error=None, base=30):
        class Transport:
            timing = Timing(snapshot_seconds=base)
        transport = Transport()
        original = transport.timing
        calls = []
        payload = {'arguments': options if options is not None else {'include_image': False, 'include_xml': True}}
        class Session:
            timing = original
            async def call(self, op, body):
                calls.append((op, body, self.timing))
                if error is not None:
                    raise error
                return 'original response'
        session = Session()
        try:
            result = await call_with_transition_budget(session, operation, payload,
                                                      phase=phase, seconds=seconds)
        except BaseException as raised:
            result = raised
        self.assertIs(transport.timing, original)
        self.assertIs(session.timing, original)
        return result, calls, payload

    async def test_only_first_xml_entry_read_changes_its_budget(self):
        result, calls, payload = await self.exercise()
        self.assertEqual(result, 'original response')
        self.assertEqual(calls, [('android.snapshot', payload, Timing(snapshot_seconds=45))])

    async def test_default_and_later_reads_are_unchanged(self):
        for seconds, phase in ((None, 'broker_quote_entry_1'), (45, 'broker_quote_entry_2'),
                               (45, 'snapshot_1_quote'), (45, 'broker_known_result_1')):
            _, calls, _ = await self.exercise(seconds=seconds, phase=phase)
            self.assertEqual(calls[0][2], Timing())

    async def test_never_extends_images_bound_frames_or_input(self):
        for operation, options in (
            ('android.tap', {'x': 0.5, 'y': 0.5, 'frame_ref': 'frame'}),
            ('android.input_text', {'text': '600999'}),
            ('android.snapshot', {'include_image': True, 'include_xml': True}),
            ('android.snapshot', {'include_image': False, 'include_xml': True, 'expected_frame_ref': 'frame'}),
        ):
            _, calls, payload = await self.exercise(operation=operation, options=options)
            self.assertEqual(calls, [(operation, payload, Timing())])

    async def test_failure_timeout_and_cancellation_restore_without_retry(self):
        for error in (RuntimeError('failed'), TimeoutError('expired'), asyncio.CancelledError()):
            result, calls, _ = await self.exercise(error=error)
            self.assertIs(result, error)
            self.assertEqual(len(calls), 1)

    async def test_rejects_invalid_or_conflicting_budget_before_rpc(self):
        for seconds, base in ((True, 30), (0, 30), (46, 30), (45, 90)):
            result, calls, _ = await self.exercise(seconds=seconds, base=base)
            self.assertIsInstance(result, ValueError)
            self.assertEqual(calls, [])

    async def test_real_native_rpc_uses_session_budget_then_restores(self):
        from kengent.tools.resource_node.android import NativeSession
        seen = []
        actual_timeout = asyncio.timeout
        def timeout(seconds):
            seen.append(seconds)
            return actual_timeout(seconds)
        transport = SimpleNamespace(timing=Timing())
        session = NativeSession(transport, {'nonce': '0'*32}, ['com.guotai.dazhihui'])
        class Stream:
            def write(self, value):
                self.request = json.loads(value)
            async def drain(self): pass
            async def readline(self):
                return json.dumps({'id': self.request['id'], 'ok': True, 'result': {}}).encode()+b'\n'
        stream = Stream()
        session.process = SimpleNamespace(returncode=None, stdin=stream, stdout=stream)
        with patch('kengent.tools.resource_node.android.asyncio.timeout', side_effect=timeout):
            await call_with_transition_budget(session, 'android.snapshot',
                {'arguments': {'include_image': False, 'include_xml': True}},
                phase='broker_quote_entry_1', seconds=45)
            await session.call('android.snapshot', {'arguments': {}})
            await session.call('android.tap', {'arguments': {}})
        self.assertEqual(seen, [45, 30, 8])
        self.assertIs(session.timing, transport.timing)
