from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prewarm_public_app import launch_component,displayed_lines

class Prewarm(unittest.TestCase):
    def test_launcher_requires_unique_exact_package(self):
        package='com.guotai.dazhihui'
        component=package+'/com.gtja.home.InitScreen'
        self.assertEqual(launch_component('priority=0\n'+component+'\n',package),component)
        for output in ('other.app/Entry',component+'\n'+component,'',component+'; command'):
            with self.assertRaises(ValueError):launch_component(output,package)
        with self.assertRaises(ValueError):launch_component(component,'other.app')

    def test_display_proof_requires_full_main_activity_and_launch_event(self):
        package='com.guotai.dazhihui'
        expected='10-29 05:00:00.000 I am_activity_launch_time: [0,123,com.guotai.dazhihui/com.gtja.home.MainScreen,60000,70000]'
        for bad in (expected.replace('MainScreen','MainScreenOther'),expected.replace('am_activity_launch_time','am_resume_activity'),expected.replace('com.guotai.dazhihui/','other.app/')):
            self.assertEqual(displayed_lines(bad,package),set())
        self.assertEqual(displayed_lines(expected,package),{expected})
        self.assertFalse(displayed_lines(expected,package)-{expected})

if __name__=='__main__':unittest.main()
