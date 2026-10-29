"""One explicit public quote-entry read budget; input and image bounds stay fixed."""
from dataclasses import replace


async def call_with_transition_budget(session, operation, payload, *, phase, seconds=None):
    if seconds is not None and (type(seconds) is not int or seconds not in (45, 90)):
        raise ValueError('Unsupported quote-entry diagnostic budget')
    selected = (seconds is not None and operation == 'android.snapshot'
                and phase == 'broker_quote_entry_1'
                and payload == {'arguments': {'include_image': False, 'include_xml': True}})
    original = session.timing
    if selected:
        if original.snapshot_seconds != 30:
            raise ValueError('Quote-entry comparison requires the normal 30-second read budget')
        session.timing = replace(original, snapshot_seconds=seconds)
    try:
        return await session.call(operation, payload)
    finally:
        if selected:
            session.timing = original
