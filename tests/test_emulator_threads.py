from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sample_emulator_threads import delta, identity, thread_snapshot


def stat(start):
    return '8 (CPU (0) worker) ' + ' '.join(['S'] + ['0'] * 18 + [str(start)] + ['0'] * 8)


def row(start=5, run=10, wait=3, slices=2):
    return dict(start_ticks=start, run_ns=run, wait_ns=wait, slices=slices,
                allowed_cpus='12-15', name='CPU 0/TCG')


class ThreadSampleTests(unittest.TestCase):
    def test_stat_identity_handles_thread_name_parentheses(self):
        self.assertEqual(identity(stat(543)), 543)

    def test_new_exited_and_reused_threads_do_not_inflate_totals(self):
        before = {'8': row(), '9': row(), '10': row()}
        after = {'8': row(run=17, wait=5, slices=3), '9': row(start=6, run=90), '11': row(run=999)}
        values = delta(before, after)
        self.assertEqual(set(values), {('8', 5)})
        self.assertEqual((values[('8', 5)]['run_ns'], values[('8', 5)]['wait_ns'], values[('8', 5)]['slices']), (7, 2, 1))

    def test_backwards_counters_fail(self):
        with self.assertRaises(ValueError):
            delta({'8': row()}, {'8': row(run=9)})

    def test_snapshot_reads_only_thread_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            thread = root / '7/task/8'
            thread.mkdir(parents=True)
            (thread / 'stat').write_text(stat(5))
            (thread / 'schedstat').write_text('17 5 3\n')
            (thread / 'status').write_text('Name:\tCPU 0\nCpus_allowed_list:\t12-15\n')
            (thread / 'comm').write_text('CPU 0/TCG\n')
            (root / '7/task/9').mkdir()  # vanished before files were read
            self.assertEqual(thread_snapshot(7, root), {'8': row(run=17, wait=5, slices=3)})
            (thread / 'schedstat').write_text('-1 5 3\n')
            with self.assertRaises(ValueError):
                thread_snapshot(7, root)
