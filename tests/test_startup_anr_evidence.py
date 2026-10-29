from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from startup_anr_evidence import parse_event,match_main_trace,collect

LINE='10-29 16:20:00.000 961 990 I am_anr  : [0,1234,com.guotai.dazhihui,0,executing service widget]'
EVENT=parse_event(LINE,2026)
TRACE='''----- pid 1234 at 2026-10-29 16:20:01 -----
Cmd line: com.guotai.dazhihui
"renamed-worker" prio=5 tid=2 Runnable
  | group="main" sysTid=1235
  at unrelated.Worker.run(File.java:1)
"main" prio=5 tid=1 Native
  | group="main" sysTid=1234
  | state=D schedstat=( 5000000000 12000000000 21 )
  at android.app.ActivityManagerProxy.registerReceiver(File.java:2)
  at com.gtja.home.MainScreen.onCreate(File.java:3)
----- end 1234 -----
'''

class Evidence(unittest.TestCase):
    def test_exact_event_main_tid_and_scheduling(self):
        result=match_main_trace(TRACE,EVENT)
        self.assertTrue(result['matched'])
        value=result['matches'][0]
        self.assertEqual(value['main_tid'],1234)
        self.assertEqual(value['cpu_seconds'],5)
        self.assertEqual(value['runnable_wait_seconds'],12)
        self.assertEqual(value['java_methods'],['android.app.ActivityManagerProxy.registerReceiver','com.gtja.home.MainScreen.onCreate'])

    def test_unrelated_or_stale_or_partial_evidence_is_not_reused(self):
        for text in [TRACE.replace('16:20:01','15:20:01'),TRACE.replace('16:20:01','16:25:01'),
                     TRACE.replace('Cmd line: com.guotai.dazhihui','Cmd line: com.guotai.dazhihui:pushservice'),
                     TRACE.replace('sysTid=1234','sysTid=4321'),TRACE.replace('----- end 1234 -----',''),TRACE+TRACE]:
            with self.subTest(text=text):
                self.assertFalse(match_main_trace(text,EVENT)['matched'])
                self.assertEqual(match_main_trace(text,EVENT)['matches'],[])
        self.assertFalse(match_main_trace('',EVENT)['matched'])

    def test_repeated_worker_name_does_not_replace_main(self):
        text=TRACE.replace('"renamed-worker"','"main"')
        value=match_main_trace(text,EVENT)['matches'][0]
        self.assertNotIn('unrelated.Worker.run',value['java_methods'])
        text=TRACE.replace('"main" prio=5 tid=1','"ui-renamed" prio=5 tid=1')
        self.assertTrue(match_main_trace(text,EVENT)['matched'])

    def test_other_apps_and_crash_events_do_not_supply_account_app_identity(self):
        for line in [LINE.replace('am_anr','am_crash'),LINE.replace('com.guotai.dazhihui','other.app'),
                     LINE.replace('com.guotai.dazhihui','com.guotai.dazhihui:pushservice')]:
            with self.assertRaises(ValueError):parse_event(line,2026)

    def test_collector_preserves_missing_permissions_without_root_or_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def call(args):
                calls.append(args)
                if args==['shell','cat','/data/anr/traces.txt']:raise PermissionError()
                return 'retained public metadata'
            result=collect(call,Path(temp),[LINE],2026)
            self.assertEqual(result['analysis'],[])
            self.assertFalse(result['reads']['anr-traces']['ok'])
            self.assertFalse(result['root_requested'])
            self.assertEqual(len(calls),3)
            self.assertTrue((Path(temp)/'anr-evidence.json').is_file())
            self.assertFalse((Path(temp)/'anr-traces.txt').exists())

    def test_collector_retains_original_trace_and_matching_result(self):
        with tempfile.TemporaryDirectory() as temp:
            def call(args):return TRACE if args==['shell','cat','/data/anr/traces.txt'] else ''
            result=collect(call,Path(temp),[LINE],2026)
            self.assertTrue(result['analysis'][0]['matched'])
            self.assertEqual((Path(temp)/'anr-traces.txt').read_text(),TRACE)
