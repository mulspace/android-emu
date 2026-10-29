from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from window_quiet_probe import instrument_window_quiet
from probe_public_journey import Journey, TDX, JUNHONG


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required')
class Policy(unittest.TestCase):
    def test_settle_deadlines_and_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['javac', '-d', tmp, str(ROOT/'experimental/native/WindowQuiet.java'),
                str(ROOT/'tests/guest/WindowQuietProbe.java')], check=True, timeout=30)
            subprocess.run(['java','-cp',tmp,'WindowQuietProbe'],check=True,timeout=15)

    def test_transform_preserves_capture_and_refuses_drift(self):
        anchor='        JSONObject result = captureSnapshot(args, true);'
        changed=instrument_window_quiet(anchor)
        self.assertIn(anchor,changed)
        self.assertIn('frame=null; frameAt=0; frameObservation=null;',changed)
        self.assertIn('packages.contains("com.tdx.AndroidNew")',changed)
        for source in ('',anchor+anchor):
            with self.assertRaises(ValueError):instrument_window_quiet(source)


class Route(unittest.IsolatedAsyncioTestCase):
    async def test_only_first_chart_observation_requests_settle(self):
        calls=[]
        async def capture(phase,options):
            calls.append((phase,options))
            return {'foreground_package':TDX,'width':720,'height':1560,'rotation':0,
                'hierarchy_xml':'<hierarchy/>','sensitive_inputs':[]}
        async def unused(*args):pass
        async def no_pause(seconds):pass
        for enabled in (False,True):
            calls.clear()
            j=Journey(TDX,capture,unused,pause=no_pause,settle_windows=enabled)
            with self.assertRaises(TimeoutError):await j.wait('chart_ready',lambda ns:None)
            self.assertEqual(len(calls),8)
            self.assertEqual(calls[0][1].get('wait_window_quiet'), 'tdx-chart-v1' if enabled else None)
            self.assertTrue(all('wait_window_quiet' not in o for _,o in calls[1:]))
            calls.clear()
            await j.wait('market_ready',lambda ns:{'ok':True})
            self.assertNotIn('wait_window_quiet',calls[0][1])
        with self.assertRaises(ValueError):Journey(JUNHONG,capture,unused,settle_windows=True)
