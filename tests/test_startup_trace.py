import asyncio
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from trace_native_start import traced_session_type
from build_observation_probe import startup_diagnostics

class Transport:
    def __init__(self, fail=False): self.fail=fail;self.calls=0
    async def start(self, nonce):
        self.calls+=1
        if self.fail: raise TimeoutError("private nonce must not be logged")
        return nonce

class Base:
    def __init__(self,transport,fail_read=False):
        self.transport=transport;self.ready=False;self.sequence=0;self.fail_read=fail_read
    async def _read(self,*args,**kwargs):
        if self.fail_read:raise TimeoutError("private content must not be logged")
        return {"private":"not logged"}
    async def start(self,session):
        await self.transport.start("private nonce")
        await self._read()
        self.sequence=1
        await self._read()
        self.ready=True
        return session

class StartupTrace(unittest.IsolatedAsyncioTestCase):
    async def test_success_records_phases_without_payload_and_restores_transport(self):
        events=[];transport=Transport();original=transport.start
        traced=traced_session_type(Base,events.append)(transport)
        result=await traced.start("private request")
        self.assertEqual(result,"private request")
        self.assertEqual(transport.start,original)
        self.assertEqual([e["phase"] for e in events],["native_transport_start","native_ready_wait","native_configure_wait"])
        self.assertTrue(all(e["ok"] for e in events));self.assertEqual(transport.calls,1)
        await traced._read();self.assertEqual(len(events),3)
        self.assertNotIn("private",str(events))

    async def test_failures_propagate_once_and_restore_transport(self):
        for fail_transport in (True,False):
            events=[];transport=Transport(fail_transport);original=transport.start
            traced=traced_session_type(Base,events.append)(transport,not fail_transport)
            with self.assertRaises(TimeoutError):await traced.start("private request")
            self.assertEqual(transport.start,original);self.assertEqual(transport.calls,1)
            self.assertFalse(events[-1]["ok"]);self.assertNotIn("private",str(events))

    async def test_cancellation_is_not_retried(self):
        class Cancelled(Transport):
            async def start(self,nonce):self.calls+=1;raise asyncio.CancelledError()
        events=[];transport=Cancelled();original=transport.start
        traced=traced_session_type(Base,events.append)(transport)
        with self.assertRaises(asyncio.CancelledError):await traced.start(None)
        self.assertEqual(transport.calls,1);self.assertEqual(transport.start,original)
        self.assertFalse(events[-1]["ok"])

class StartupSource(unittest.TestCase):
    def test_preserves_implementation_and_refuses_drift(self):
        source='    private static void serve(PrintStream wire) {\n        String phase = "service_configurator";\n'
        source+=''.join('            phase = "'+p+'";\n' for p in ("service_automation","service","ready"))
        source+='        original_deadline();\n}\n    public static void main(String[] args) {}'
        result=startup_diagnostics(source)
        self.assertEqual(result.count('Log.i("EmuStartup"'),4)
        self.assertIn('original_deadline();',result)
        for changed in ("",source.replace('phase = "ready"','phase = "other"'),source.replace('phase = "service";', 'phase = "service";\n            phase = "service";')):
            with self.assertRaises(ValueError):startup_diagnostics(changed)
