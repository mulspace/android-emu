import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from configure_guest_smp import allocation_plan,apply_allocation,require_shell_restored
from unittest.mock import patch
import tempfile

class GuestSmp(unittest.TestCase):
    def test_requires_owned_matching_cpu_layout(self):
        record={"serial":"emulator-5576","experimental_arm_smp":True,"guest_vcpus":2}
        current={"foreground":"0","top-app":"0"}
        self.assertEqual(allocation_plan(record,"0-1","0-1",current),{g:"0-1" for g in current})
        self.assertEqual(allocation_plan(record,"0-1","0-1",{g:"0-1" for g in current}),{})
        for bad in ({**record,"serial":"8KE5T19614003830"},{**record,"guest_vcpus":1},{**record,"experimental_arm_smp":False}):
            with self.assertRaises(ValueError):allocation_plan(bad,"0-1","0-1",current)
        for online,parent,state in [("0","0-1",current),("0-1","0",current),("0-1","0-1",{"foreground":"1","top-app":"0"})]:
            with self.assertRaises(ValueError):allocation_plan(record,online,parent,state)

    def test_drop_debug_privilege_on_success_and_rollback(self):
        for fail in (False,True):
            with self.subTest(fail=fail):
                calls=[];state={"root":False,"foreground":"0","top-app":"0"};record={}
                def call(args):
                    calls.append(args)
                    if args==["root"]:state["root"]=True
                    elif args==["unroot"]:state["root"]=False
                    elif args==["shell","id"]:return "uid=0(root)" if state["root"] else "uid=2000(shell)"
                    elif args[:3]==["shell","sh","-c"]:
                        body=args[3].strip("'");value=body.split()[1];group=body.split("/cpuset/")[1].split("/")[0]
                        if fail and group=="top-app" and value=="0-1":raise RuntimeError()
                        state[group]=value
                    elif args[:2]==["shell","cat"]:return state[args[2].split("/cpuset/")[1].split("/")[0]]
                    return ""
                if fail:
                    with self.assertRaises(RuntimeError):apply_allocation(call,{"foreground":"0-1","top-app":"0-1"},{"foreground":"0","top-app":"0"},record)
                    self.assertTrue(record["rollback_confirmed"])
                    self.assertEqual(state["foreground"],"0")
                else:
                    apply_allocation(call,{"foreground":"0-1","top-app":"0-1"},{"foreground":"0","top-app":"0"},record)
                    self.assertEqual(state["foreground"],"0-1")
                self.assertTrue(record["ordinary_shell_restored"])
                self.assertFalse(state["root"])
                self.assertEqual(calls[1:3],[["shell","am","force-stop","com.tdx.AndroidNew"],["shell","am","force-stop","com.guotai.dazhihui"]])

    def test_invalid_plan_never_touches_device(self):
        calls=[]
        with self.assertRaises(ValueError):apply_allocation(lambda args:calls.append(args),{"background":"0-1"},{"foreground":"0","top-app":"0"},{})
        self.assertEqual(calls,[])

    def test_unconfirmed_privilege_stops_only_the_owned_guest(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            with patch("configure_guest_smp.owned_run") as owned:
                for record in ({},{"adb_root_requested":True,"ordinary_shell_restored":True}):
                    require_shell_restored(record,run)
                    owned.assert_not_called();self.assertFalse((run/"stop.request").exists())
                record={"adb_root_requested":True,"passed":True}
                require_shell_restored(record,run)
                owned.assert_called_once_with(run,"emulator-5576")
                self.assertFalse(record["passed"]);self.assertTrue(record["owned_guest_stop_requested"])
                self.assertTrue((run/"stop.request").exists())
            (run/"stop.request").unlink()
            with patch("configure_guest_smp.owned_run",side_effect=ValueError()):
                record={"adb_root_requested":True}
                require_shell_restored(record,run)
                self.assertTrue(record["owned_guest_stop_unconfirmed"])
                self.assertFalse((run/"stop.request").exists())
