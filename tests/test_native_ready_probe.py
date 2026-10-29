import asyncio as real_asyncio
import hashlib
import inspect
from pathlib import Path
import sys
import textwrap
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from native_ready_probe import ready_session_type

# Scale only the fake fixture clock: a ten-second policy is ten milliseconds.
# Production source is never patched or imported by these tests.
asyncio = types.SimpleNamespace(timeout=lambda seconds: real_asyncio.timeout(seconds / 1000))


class Fake:
    def __init__(self, delay=0.02, nonce='owned'):
        self.delay = delay
        self.nonce = nonce
        self.starts = self.reads = self.configures = 0
        self.ready = self.failed = False
        self.lifecycle = real_asyncio.Lock()

    def ttl(self, session):
        if session <= 0:
            raise ValueError('Lease expired')
        return session

    async def _read(self):
        self.reads += 1
        await real_asyncio.sleep(self.delay)
        return self.nonce

    async def start(self, session):
        async with self.lifecycle:
            if self.ready:
                return
            self.starts += 1
            try:
                async with asyncio.timeout(10):
                    ready = await self._read()
                if ready != 'owned':
                    raise ValueError('Wrong native owner')
                self.ttl(session)
                self.configures += 1
                self.ready = True
            except Exception:
                self.failed = True
                raise


def candidate():
    digest = hashlib.sha256(textwrap.dedent(inspect.getsource(Fake.start)).encode()).hexdigest()
    return ready_session_type(Fake, 30, expected_sha256=digest)


class ReadyProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_ready_only_passes_explicit_diagnostic_once(self):
        old = ready_session_type(Fake)()
        with self.assertRaises(TimeoutError):
            await old.start(280000)
        new = candidate()()
        await new.start(280000)
        await new.start(280000)
        self.assertTrue(new.ready)
        self.assertEqual((new.starts, new.reads, new.configures), (1, 1, 1))
        self.assertTrue(old.failed)
        self.assertEqual(old.configures, 0)

    async def test_no_ready_before_new_bound_fails_without_retry(self):
        new = candidate()(delay=0.06)
        with self.assertRaises(TimeoutError):
            await new.start(280000)
        self.assertTrue(new.failed)
        self.assertEqual((new.starts, new.reads, new.configures), (1, 1, 0))

    async def test_remaining_lease_is_stricter_than_diagnostic_bound(self):
        new = candidate()()
        with self.assertRaises(TimeoutError):
            await new.start(5000)
        self.assertTrue(new.failed)
        self.assertEqual(new.configures, 0)

    async def test_wrong_owner_and_expired_lease_do_not_configure(self):
        for nonce, lease in [('wrong', 280000), ('owned', 0)]:
            new = candidate()(delay=0.001, nonce=nonce)
            with self.assertRaises(ValueError):
                await new.start(lease)
            self.assertTrue(new.failed)
            self.assertEqual(new.configures, 0)

    async def test_cancellation_does_not_replay(self):
        new = candidate()(delay=0.2)
        task = real_asyncio.create_task(new.start(280000))
        await real_asyncio.sleep(0.002)
        task.cancel()
        with self.assertRaises(real_asyncio.CancelledError):
            await task
        self.assertEqual((new.starts, new.reads, new.configures), (1, 1, 0))

    def test_default_and_source_identity_guard(self):
        self.assertIs(ready_session_type(Fake, 10), Fake)
        for value in (True, 0, 60, '30'):
            with self.assertRaises(ValueError):
                ready_session_type(Fake, value)
        with self.assertRaisesRegex(ValueError, 'source changed'):
            ready_session_type(Fake, 30)
        self.assertTrue(candidate().ready_probe_info['bounded_by_original_lease'])
