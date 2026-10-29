#!/usr/bin/env python3
"""Opt-in volatile app CPU-set repair in the owned debug emulator only."""
import argparse
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import re
import subprocess
from probe_public_capture import owned_run

GROUPS=("foreground","top-app")
PACKAGES=("com.tdx.AndroidNew","com.guotai.dazhihui")

def allocation_plan(receipt,online,parent,current):
    cpus=receipt.get("guest_vcpus")
    if receipt.get("serial")!="emulator-5576" or receipt.get("experimental_arm_smp") is not True or type(cpus) is not int or cpus not in (2,4):
        raise ValueError("An owned ARM SMP diagnostic is required")
    expected="0-"+str(cpus-1)
    if online!=expected or parent!=expected or set(current)!=set(GROUPS):
        raise ValueError("Guest online/root CPU allocation does not match the run")
    if any(value not in ("0",expected) for value in current.values()):
        raise ValueError("Unexpected app CPU allocation; refuse to overwrite")
    return {group:expected for group in GROUPS if current[group]!=expected}


def apply_allocation(call,changes,before,record):
    """Stop only both test Apps, apply validated constants, then drop ADB root."""
    if not changes:return
    if set(changes)-set(GROUPS) or set(before)!=set(GROUPS) or any(v not in ("0-1","0-3") for v in changes.values()) or any(v not in ("0","0-1","0-3") for v in before.values()):
        raise ValueError("Unsupported CPU-set mutation")
    if not re.match(r"uid=2000\(shell\)",call(["shell","id"]).strip()):
        raise ValueError("Expected ordinary ADB shell before experiment")
    for package in PACKAGES:call(["shell","am","force-stop",package])
    # Set before requesting it: even an interrupted reply requires cleanup.
    record["adb_root_requested"]=True
    changed=[]
    try:
        call(["root"])
        call(["wait-for-device"])
        if not re.match(r"uid=0\(root\)",call(["shell","id"]).strip()):
            raise ValueError("Isolated userdebug ADB did not enter root")
        for group,value in changes.items():
            changed.append(group)
            path="/dev/cpuset/"+group+"/cpus"
            call(["shell","sh","-c","'printf "+value+" > "+path+"'"])
            if call(["shell","cat",path]).strip()!=value:
                raise ValueError("Guest CPU-set readback mismatch")
        record["applied"]=dict(changes)
    except BaseException:
        record["rollback_confirmed"]=False
        try:
            for group in reversed(changed):
                path="/dev/cpuset/"+group+"/cpus"
                call(["shell","sh","-c","'printf "+before[group]+" > "+path+"'"])
                if call(["shell","cat",path]).strip()!=before[group]:
                    raise ValueError("Guest CPU-set rollback mismatch")
            record["rollback_confirmed"]=True
        finally:record.pop("applied",None)
        raise
    finally:
        call(["unroot"])
        call(["wait-for-device"])
        record["ordinary_shell_restored"]=bool(re.match(r"uid=2000\(shell\)",call(["shell","id"]).strip()))
        if not record["ordinary_shell_restored"]:raise ValueError("Ordinary ADB shell restoration was not confirmed")


def require_shell_restored(record,run_dir):
    if not record.get("adb_root_requested") or record.get("ordinary_shell_restored"):
        return
    record["passed"]=False
    try:
        owned_run(run_dir,"emulator-5576")
        (run_dir/"stop.request").write_text("CPU-set diagnostic could not confirm ordinary ADB shell\n")
        record["owned_guest_stop_requested"]=True
    except (OSError,ValueError):
        # Never act on a different process if the owned guest disappeared.
        record["owned_guest_stop_unconfirmed"]=True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--adb",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--apply",action="store_true",help="Stop only the test Apps, temporarily root this userdebug ADB, set two app CPU sets, then unroot")
    args=parser.parse_args()
    os.umask(0o077)
    owned_run(args.run_dir,"emulator-5576")
    if args.output.exists():raise ValueError("Do not overwrite an earlier receipt")
    record={"started_at":datetime.now(UTC).isoformat(),"production_cutover":False,
            "physical_device_operated":False,"account_input":False,"persistent_image_change":False,"passed":False}
    def call(argv):
        owned_run(args.run_dir,"emulator-5576")
        result=subprocess.run([str(args.adb),"-s","emulator-5576",*argv],capture_output=True,text=True,timeout=12)
        if result.returncode:raise RuntimeError("Scoped guest command failed")
        return result.stdout
    try:
        receipt=json.loads((args.run_dir/"started.json").read_text())
        if call(["shell","getprop","sys.boot_completed"]).strip()!="1":raise ValueError("Guest not booted")
        if call(["shell","getprop","ro.product.cpu.abi"]).strip()!="armeabi-v7a":raise ValueError("Unexpected diagnostic ABI")
        if call(["shell","getprop","ro.debuggable"]).strip()!="1":raise ValueError("Expected the existing userdebug image")
        online=call(["shell","cat","/sys/devices/system/cpu/online"]).strip()
        parent=call(["shell","cat","/dev/cpuset/cpus"]).strip()
        current={g:call(["shell","cat","/dev/cpuset/"+g+"/cpus"]).strip() for g in GROUPS}
        changes=allocation_plan(receipt,online,parent,current)
        record.update(online=online,before=current,proposed=changes)
        if args.apply:apply_allocation(call,changes,current,record)
        record["after"]={g:call(["shell","cat","/dev/cpuset/"+g+"/cpus"]).strip() for g in GROUPS}
        record["passed"]=not args.apply or all(record["after"][g]==online for g in GROUPS)
    except BaseException as error:
        record["error_type"]=type(error).__name__
    finally:
        require_shell_restored(record,args.run_dir)
        record["ended_at"]=datetime.now(UTC).isoformat()
        args.output.write_text(json.dumps(record,indent=2)+"\n")
        print(json.dumps(record),flush=True)
    raise SystemExit(0 if record["passed"] else 1)

if __name__=="__main__":main()
