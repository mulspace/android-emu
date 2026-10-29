from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prewarm_public_app import launch_component,displayed_lines,failure_lines,wait_main_displayed,AppStartupFailure,app_processes,verify_stopped_peer

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

    def test_padded_failure_tags_and_exact_process_scope(self):
        anr="10-29 I am_anr  : [0,2389,com.guotai.dazhihui,42,executing service]"
        crash="10-29 I am_crash: [0,2389,com.guotai.dazhihui:pushservice,42,Exception]"
        other=anr.replace("com.guotai.dazhihui","com.guotai.dazhihuiOther")
        self.assertEqual(failure_lines("\n".join([anr,crash,other]),"com.guotai.dazhihui"),{anr,crash})
        self.assertEqual(len(failure_lines("\n".join([anr,crash,other]))),3)

    def test_readiness_wait_uses_whole_deadline_not_twelve_polls(self):
        now=[0];reads=[0]
        shown="10-29 I am_activity_launch_time: [0,123,com.guotai.dazhihui/com.gtja.home.MainScreen,105000,105000]"
        def read():
            reads[0]+=1;now[0]+=1
            return shown if reads[0]==16 else ""
        def pause(seconds):now[0]+=seconds
        self.assertEqual(wait_main_displayed(read,"","com.guotai.dazhihui",240,lambda:now[0],pause),{shown})
        self.assertEqual(reads[0],16)
        now[0]=0;reads[0]=0
        with self.assertRaises(TimeoutError):wait_main_displayed(read,"","com.guotai.dazhihui",20,lambda:now[0],pause)
        self.assertLessEqual(now[0],20)

    def test_new_anr_stops_even_if_main_display_event_arrives(self):
        package="com.guotai.dazhihui"
        old="10-28 I am_anr  : [0,20,com.guotai.dazhihui,42,old]"
        new="10-29 I am_anr  : [0,30,com.guotai.dazhihui,42,new]"
        shown="10-29 I am_activity_launch_time: [0,123,com.guotai.dazhihui/com.gtja.home.MainScreen,105000,105000]"
        with self.assertRaises(AppStartupFailure) as caught:
            wait_main_displayed(lambda:old+"\n"+new+"\n"+shown,old,package,240,lambda:0,lambda _:None)
        self.assertEqual(caught.exception.events,{new})
        self.assertEqual(wait_main_displayed(lambda:old+"\n"+shown,old,package,240,lambda:0,lambda _:None),{shown})

class PeerIsolation(unittest.TestCase):
    header="USER PID PPID VSIZE RSS WCHAN PC NAME\n"
    base=header+"root 1 0 100 10 epoll 0 S /init\n"
    package="com.guotai.dazhihui"

    def test_exact_package_and_subprocess_not_similar_name(self):
        output=self.base+"u0_a61 20 1 100 10 epoll 0 S "+self.package+"\n"
        output+="u0_a61 21 1 100 10 epoll 0 S "+self.package+":pushservice\n"
        output+="u0_a61 22 1 100 10 epoll 0 S "+self.package+"Other\n"
        self.assertEqual(app_processes(output,self.package),{20,21})
        for bad in ("",self.header,"permission denied",self.base+"malformed\n"):
            with self.assertRaises(ValueError):app_processes(bad,self.package)
        with self.assertRaises(ValueError):app_processes(output,"other.app")

    def test_restore_after_initial_stop_is_corrected_once_and_verified_twice(self):
        restored=self.base+"u0_a61 20 1 100 10 epoll 0 S "+self.package+"\n"
        readings=iter([restored,self.base,self.base]);stops=[];pauses=[]
        result=verify_stopped_peer(lambda:next(readings),stops.append,self.package,pauses.append)
        self.assertEqual(stops,[self.package]);self.assertEqual(pauses,[1,1])
        self.assertEqual(result,{"observed_process_count":1,"restop_requested":True,"verified_absent_checks":2})

    def test_persistent_or_later_restore_fails_without_another_stop(self):
        restored=self.base+"u0_a61 20 1 100 10 epoll 0 S "+self.package+"\n"
        for values,expected in (([restored,restored],[self.package]),([self.base,self.base,restored],[])):
            with self.subTest(values=values):
                readings=iter(values);stops=[]
                with self.assertRaises(RuntimeError):
                    verify_stopped_peer(lambda:next(readings),stops.append,self.package,lambda _:None)
                self.assertEqual(stops,expected)

    def test_already_absent_peer_is_not_stopped_again(self):
        stops=[];reads=[]
        def read():reads.append(1);return self.base
        result=verify_stopped_peer(read,stops.append,self.package,lambda _:None)
        self.assertFalse(stops);self.assertEqual(len(reads),3)
        self.assertFalse(result['restop_requested'])

if __name__=='__main__':unittest.main()
