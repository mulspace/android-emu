#!/usr/bin/env python3
"""One isolated public App launch before UiAutomation; no account operations."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from probe_public_capture import owned_run

ACTIVITIES = {'com.tdx.AndroidNew': 'com.tdx.AndroidNew/com.tdx.Android.TdxActivity',
              'com.guotai.dazhihui': 'com.guotai.dazhihui/com.gtja.home.MainScreen'}


def launch_component(output, package):
    if package not in ACTIVITIES:
        raise ValueError('Unsupported public test App')
    matches = [line.strip() for line in output.splitlines()
               if re.fullmatch(re.escape(package) + r'/[A-Za-z0-9_.$]+', line.strip())]
    if len(matches) != 1:
        raise ValueError('Launcher Activity is not unique and verified')
    return matches[0]


def displayed_lines(output, package):
    component = ACTIVITIES[package]
    return {line for line in output.splitlines()
            if ' am_activity_launch_time:' in line and ',' + component + ',' in line}


class AppStartupFailure(RuntimeError):
    def __init__(self, events):
        super().__init__("Observed App ANR or crash during startup")
        self.events=events


def failure_lines(output, package=None):
    if package is not None and package not in ACTIVITIES:
        raise ValueError("Unsupported public test App")
    rows={line for line in output.splitlines() if re.search(r"\bam_(?:anr|crash)\s*:",line)}
    if package is not None:
        pattern=r"(?:\[|,)"+re.escape(package)+r"(?::[^,\]]+)?(?:,|\])"
        rows={line for line in rows if re.search(pattern,line)}
    return rows


def app_processes(output, package):
    """Exact process identity from the known Android ps format, not substrings."""
    if package not in ACTIVITIES:
        raise ValueError("Unsupported public test App")
    lines=[line.split() for line in output.splitlines() if line.strip()]
    if len(lines)<2 or "PID" not in lines[0] or lines[0][-1]!="NAME":
        raise ValueError("Unrecognized process inventory")
    pid_column=lines[0].index("PID")
    found=set()
    for row in lines[1:]:
        # Android 7 ps includes a state column absent from its header.
        if len(row)<len(lines[0]) or not row[pid_column].isdecimal():
            raise ValueError("Incomplete process inventory")
        if row[-1]==package or row[-1].startswith(package+":"):
            found.add(int(row[pid_column]))
    return found


def verify_stopped_peer(read, stop, package, pause=time.sleep):
    """At most one corrective stop; fail if Android restores the peer again."""
    before=app_processes(read(),package)
    if before:stop(package)
    for _ in range(2):
        pause(1)
        if app_processes(read(),package):
            raise RuntimeError("Other test App did not remain stopped")
    return {"observed_process_count":len(before),"restop_requested":bool(before),
            "verified_absent_checks":2}


def wait_main_displayed(read, baseline, package, deadline, clock=time.monotonic, pause=time.sleep):
    old_display=displayed_lines(baseline,package)
    old_failures=failure_lines(baseline,package)
    while clock()<deadline:
        output=read()
        failures=failure_lines(output,package)-old_failures
        if failures:raise AppStartupFailure(failures)
        if clock()>=deadline:break
        shown=displayed_lines(output,package)-old_display
        if shown:return shown
        remaining=deadline-clock()
        if remaining>0:pause(min(5,remaining))
    raise TimeoutError("Main display event was not observed before the startup deadline")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--adb', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--package', choices=tuple(ACTIVITIES), required=True)
    p.add_argument('--stop-other-test-app', action='store_true', help='Isolated AVD only: stop the other one of the two public test Apps before launch')
    args = p.parse_args()
    os.umask(0o077)
    owned_run(args.run_dir, 'emulator-5576')
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + 240
    events = []
    phase = 'resolve'
    def call(arguments, bound=25):
        owned_run(args.run_dir, 'emulator-5576')
        remaining = deadline-time.monotonic()
        if remaining <= 0: raise TimeoutError('Prewarm deadline')
        return subprocess.run([str(args.adb), '-s', 'emulator-5576', *arguments],
                              capture_output=True, check=True, timeout=min(bound, remaining)).stdout.decode()
    def event(name):
        value = {'phase': name, 'seconds': round(time.monotonic()-started, 3)}
        events.append(value); print(json.dumps(value), flush=True)
    passed = False
    stopped_peers=[]
    peer_checks={}
    def read_events():
        return call(['logcat','-b','events','-d','-s','am_activity_launch_time:I','am_anr:I','am_crash:I','*:S'])
    try:
        phase = 'require_boot_complete'
        if call(['shell', 'getprop', 'sys.boot_completed']).strip() != '1':
            raise ValueError('Guest has not completed boot')
        phase = 'resolve'
        component = launch_component(call(['shell', 'cmd', 'package', 'resolve-activity', '--brief',
            '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER', args.package]), args.package)
        if args.stop_other_test_app:
            phase='stop_other_test_app'
            for peer in ACTIVITIES:
                if peer!=args.package:
                    call(['shell','am','force-stop',peer])
                    stopped_peers.append(peer)
            event(phase)
        phase = 'stop_test_app'
        call(['shell', 'am', 'force-stop', args.package])
        phase = 'baseline'
        baseline = read_events()
        phase = 'launch_once'
        response = call(['shell', 'am', 'start', '-a', 'android.intent.action.MAIN',
                         '-c', 'android.intent.category.LAUNCHER', '-n', component])
        (args.output/'launch.txt').write_text(response)
        if 'Error' in response or 'Starting: Intent' not in response:
            raise ValueError('Launch not acknowledged')
        event(phase)
        phase = 'await_main_displayed'
        latest=wait_main_displayed(read_events,baseline,args.package,deadline)
        (args.output/'displayed.txt').write_text('\n'.join(sorted(latest))+'\n')
        event(phase)
        if args.stop_other_test_app:
            phase='verify_other_test_app_stopped'
            for peer in stopped_peers:
                peer_checks[peer]=verify_stopped_peer(
                    lambda:call(['shell','ps']),
                    lambda package:call(['shell','am','force-stop',package]),peer)
            failures=failure_lines(read_events(),args.package)-failure_lines(baseline,args.package)
            if failures:raise AppStartupFailure(failures)
            event(phase)
        passed=True
    except Exception as error:
        events.append({'phase': phase, 'error_type': type(error).__name__})
        if isinstance(error,AppStartupFailure):
            (args.output/'failure-events.txt').write_text('\n'.join(sorted(error.events))+'\n')
    result = {'passed': passed, 'package': args.package, 'events': events,
              'stopped_other_test_apps':stopped_peers, 'peer_stop_checks':peer_checks,
              'startup_limit_seconds':240,
              'elapsed_seconds': round(time.monotonic()-started,3),
              'account_input': False, 'production_cutover': False,
              'meaning': 'Activity displayed only; guarded capture still required'}
    (args.output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
