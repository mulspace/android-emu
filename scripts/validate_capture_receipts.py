"""Offline replay only: no ADB, credentials, platform API or artifact upload."""
import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from kengent.contracts.execution import ExecutionContext, IOBindings
from kengent.tools.resource_node import android


async def main(directory):
    receipt = json.loads((directory / 'receipt.json').read_text())
    events = {e['phase']: e for e in receipt['events'] if e['phase'].startswith('snapshot_') and e['ok']}
    outcomes = []
    context = ExecutionContext(scope='tenant', tenant_id='offline-fixture', workgroup_id='offline',
        principal_id='offline-validator', trace_id='offline',
        io=IOBindings(root_reply_ref='log:offline', output_ref='log:offline'))
    original_time = android.time
    try:
        for name, event in events.items():
            value = json.loads((directory / f'{name}.wire.json').read_text())
            clock = [100.0]
            android.time = SimpleNamespace(monotonic=lambda: clock[0])
            class RetainedOnly:
                def __init__(self, *args): pass
                async def start(self, session): pass
                async def renew(self, session): pass
                async def call(self, operation, payload):
                    assert operation == 'android.snapshot'
                    clock[0] += event['seconds']
                    return value
            async def private_fixture_sink(ctx, key, data, media_type):
                assert ctx.tenant_id == 'offline-fixture'
                return {'artifact_id': 'offline-fixture-artifact', 'sha256': hashlib.sha256(data).hexdigest(), 'media_type': media_type}
            backend = android.AndroidBackend(transport=object(), packages=[receipt['package']],
                artifact_sink=private_fixture_sink, session_factory=RetainedOnly)
            session = {'nonce': '0'*32, 'expires_at': (datetime.now(UTC)+timedelta(seconds=60)).isoformat(),
                       'context': context.to_header()}
            try:
                result = await backend.execute(session, 'android.snapshot',
                    {'include_image': True, 'include_xml': True, 'image_format': 'jpeg'})
                outcomes.append({'snapshot': name, 'accepted': True, 'capture_delay_ms': result.get('capture_delay_ms'),
                                 'has_image': 'image' in result, 'has_hierarchy': bool(result.get('hierarchy_xml'))})
            except Exception as error:
                outcomes.append({'snapshot': name, 'accepted': False, 'type': type(error).__name__,
                                 'problem': error.problem() if hasattr(error,'problem') else None})
    finally:
        android.time = original_time
    output = {'offline_only': True, 'device_access': False, 'network_access': False, 'results': outcomes}
    (directory/'backend-validation.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output),flush=True)
    return bool(outcomes) and all(o['accepted'] for o in outcomes)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    raise SystemExit(0 if asyncio.run(main(args.directory)) else 1)
