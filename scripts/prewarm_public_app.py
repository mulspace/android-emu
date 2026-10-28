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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--adb', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--package', choices=tuple(ACTIVITIES), required=True)
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
    try:
        component = launch_component(call(['shell', 'cmd', 'package', 'resolve-activity', '--brief',
            '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER', args.package]), args.package)
        phase = 'stop_test_app'
        call(['shell', 'am', 'force-stop', args.package])
        phase = 'baseline'
        baseline = displayed_lines(call(['logcat', '-b', 'events', '-d', '-t', '250']), args.package)
        phase = 'launch_once'
        response = call(['shell', 'am', 'start', '-a', 'android.intent.action.MAIN',
                         '-c', 'android.intent.category.LAUNCHER', '-n', component])
        (args.output/'launch.txt').write_text(response)
        if 'Error' in response or 'Starting: Intent' not in response:
            raise ValueError('Launch not acknowledged')
        event(phase)
        phase = 'await_main_displayed'
        for attempt in range(12):
            log = call(['logcat', '-b', 'events', '-d', '-t', '250'])
            latest = displayed_lines(log, args.package)-baseline
            if latest:
                (args.output/'displayed.txt').write_text('\n'.join(sorted(latest))+'\n')
                event(phase); passed=True; break
            if time.monotonic()+5 >= deadline: break
            time.sleep(5)
    except Exception as error:
        events.append({'phase': phase, 'error_type': type(error).__name__})
    result = {'passed': passed, 'package': args.package, 'events': events,
              'elapsed_seconds': round(time.monotonic()-started,3),
              'account_input': False, 'production_cutover': False,
              'meaning': 'Activity displayed only; guarded capture still required'}
    (args.output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
