#!/usr/bin/env python3
"""Read bounded per-thread CPU usage of an owned direct emulator diagnostic."""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import time

from probe_public_capture import owned_run


def identity(stat):
    # comm can contain spaces and parentheses; fields following it are fixed.
    fields = stat.rsplit(') ', 1)[1].split()
    return int(fields[19])


def thread_snapshot(pid, proc_root=Path('/proc')):
    result = {}
    for thread in (proc_root / str(pid) / 'task').iterdir():
        if not thread.name.isdecimal():
            continue
        try:
            start = identity((thread / 'stat').read_text())
            values = (thread / 'schedstat').read_text().split()
            if len(values) != 3 or any(not value.isdecimal() for value in values):
                raise ValueError('Invalid scheduler counters')
            status = dict(line.split(':', 1) for line in (thread / 'status').read_text().splitlines() if ':' in line)
            name = (thread / 'comm').read_text().strip()
            if identity((thread / 'stat').read_text()) != start:
                continue
            result[thread.name] = {'start_ticks': start, 'name': name,
                'allowed_cpus': status['Cpus_allowed_list'].strip(),
                'run_ns': int(values[0]), 'wait_ns': int(values[1]),
                'slices': int(values[2])}
        except (FileNotFoundError, ProcessLookupError):
            # Exited threads have no final sample; never invent their CPU time.
            continue
    return result


def delta(before, after):
    result = {}
    for tid, current in after.items():
        previous = before.get(tid)
        if not previous or current['start_ticks'] != previous['start_ticks']:
            continue
        counters = {key: current[key] - previous[key] for key in ('run_ns', 'wait_ns', 'slices')}
        if any(value < 0 for value in counters.values()):
            raise ValueError('Scheduler counters went backwards')
        result[(tid, current['start_ticks'])] = {**current, **counters}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error('Sampling must be bounded to 1..60 seconds')
    os.umask(0o077)
    owned_run(args.run_dir, 'emulator-5576')
    run = json.loads((args.run_dir / 'started.json').read_text())
    if run.get('debugger') != 'none':
        parser.error('Direct emulator required; do not sample its debugger instead')
    with args.output.open('x') as output:
        pid = run['owned_pgid']
        previous = thread_snapshot(pid)
        started_at = datetime.now(UTC).isoformat()
        started = time.monotonic()
        tick = started
        totals = {}
        samples = 0
        while time.monotonic() - started < args.seconds:
            time.sleep(max(0, min(1, args.seconds - (time.monotonic() - started))))
            owned_run(args.run_dir, 'emulator-5576')
            current = thread_snapshot(pid)
            now = time.monotonic()
            for key, value in delta(previous, current).items():
                total = totals.setdefault(key, {**value, 'run_ns': 0, 'wait_ns': 0,
                    'slices': 0, 'observed_seconds': 0, 'allowed_cpu_sets': []})
                for counter in ('run_ns', 'wait_ns', 'slices'):
                    total[counter] += value[counter]
                total['observed_seconds'] += now - tick
                if value['allowed_cpus'] not in total['allowed_cpu_sets']:
                    total['allowed_cpu_sets'].append(value['allowed_cpus'])
            previous, tick = current, now
            samples += 1
        rows = []
        for (tid, _), total in totals.items():
            rows.append({**total, 'tid': int(tid),
                'cpu_percent': round(total['run_ns'] / 1e7 / total['observed_seconds'], 2),
                'run_seconds': round(total['run_ns'] / 1e9, 3),
                'runnable_wait_seconds': round(total['wait_ns'] / 1e9, 3)})
        rows.sort(key=lambda row: row['run_ns'], reverse=True)
        receipt = {'pid': pid, 'serial': 'emulator-5576', 'started_at': started_at,
            'ended_at': datetime.now(UTC).isoformat(), 'elapsed_seconds': round(tick - started, 3), 'samples': samples,
            'schedstats_enabled': Path('/proc/sys/kernel/sched_schedstats').read_text().strip() == '1',
            'threads': rows, 'account_input': False, 'device_commands': False,
            'limitation': 'Intervals missing either endpoint are excluded; zero wait with schedstats disabled is not proof of no contention.'}
        output.write(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'elapsed_seconds': receipt['elapsed_seconds'], 'samples': samples,
            'schedstats_enabled': receipt['schedstats_enabled'], 'threads': rows[:8]}))


if __name__ == '__main__':
    main()
