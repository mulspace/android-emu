"""Bounded subprocess groups; never clean up unrelated processes by name."""
import os
import signal
import subprocess
import time


def stop_group(process, grace=10):
    """The process must have been created with start_new_session=True."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            process.wait()
            return
        time.sleep(0.1)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)


def run(command, *, timeout, cwd=None, env=None, log=None):
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT if log is not None else None,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        stop_group(process)
        raise
    stop_group(process)
    return code
