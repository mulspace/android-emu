"""Opt-in readiness-only diagnostic; no production source or input-policy edit."""
import hashlib
import inspect
import textwrap

APPROVED_START_SHA256 = '2cc6ea9da6596a45a797038b2b04379cfa56cc00b4da471d27b561f346b5aeb6'


def ready_session_type(base, seconds=10, *, expected_sha256=APPROVED_START_SHA256):
    if type(seconds) is not int or seconds not in (10, 30):
        raise ValueError('Native readiness diagnostic supports only 10 or 30 seconds')
    if seconds == 10:
        return base
    source = textwrap.dedent(inspect.getsource(base.start))
    digest = hashlib.sha256(source.encode()).hexdigest()
    if digest != expected_sha256:
        raise ValueError('Native startup source changed; review before applying diagnostic')
    anchor = 'async with asyncio.timeout(10):'
    if source.count(anchor) != 1:
        raise ValueError('Native readiness anchor is not unique')
    candidate = source.replace(anchor, 'async with asyncio.timeout(min(30.0, self.ttl(session) / 1000.0)):')
    namespace = dict(base.start.__globals__)
    exec(compile(candidate, '<isolated-native-ready-probe>', 'exec'), namespace)
    return type('BoundedReadySession', (base,), {
        'start': namespace['start'],
        'ready_probe_info': {'original_start_sha256': digest,
            'candidate_start_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
            'native_ready_seconds': 30, 'bounded_by_original_lease': True,
            'production_source_changed': False},
    })
