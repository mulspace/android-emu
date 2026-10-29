"""Audit private experimental quote receipts offline, never production acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from quote_read_probe import options, validate_receipt, PACKAGE, SYMBOL, NAME


def audit(directory):
    from kengent.tools.resource_node.android import _snapshot_hierarchy, _snapshot_image
    receipt = json.loads((directory / 'receipt.json').read_text())
    if (receipt.get('read_only_quote_capture') is not True or receipt.get('checked_capture') is not False
            or receipt.get('input_denial_verified') is not True or receipt.get('cleanup_confirmed') is not True
            or receipt.get('passed') is not True or receipt.get('package') != PACKAGE):
        raise ValueError('Original read-only quote probe is incomplete or failed')
    frames = []
    events = [event for event in receipt['events'] if re.fullmatch(r'snapshot_[1-6](?:_quote)?', event['phase'])]
    if len(events) != 3 or any(event.get('ok') is not True for event in events):
        raise ValueError('Expected three completed experimental captures')
    for event in events:
        name = event['phase']
        requested = json.loads((directory / (name + '.request.json')).read_text())
        raw = json.loads((directory / (name + '.wire.json')).read_text())
        if requested != options():
            raise ValueError('Experimental request changed')
        validate_receipt(raw)
        result = dict(raw)
        _snapshot_hierarchy(result, requested)
        values = list(ET.fromstring(result['hierarchy_xml']).iter('node'))
        for suffix, text in [('stock_code', SYMBOL), ('stock_name', NAME), ('minutes', '分时')]:
            matches = [node for node in values if node.get('resource-id') == PACKAGE + ':id/' + suffix]
            if len(matches) != 1 or matches[0].get('text') != text:
                raise ValueError('Retained quote identity differs')
            if suffix == 'minutes' and matches[0].get('selected') != 'true':
                raise ValueError('Retained period is not selected')
        image, media_type = _snapshot_image(result.pop('image_base64'), result, 'jpeg')
        if image != (directory / (name + '.jpg')).read_bytes():
            raise ValueError('Preview does not match retained wire pixels')
        frames.append({'phase': name, 'frame_ref': result['frame_ref'], 'image_sha256': hashlib.sha256(image).hexdigest(),
                       'media_type': media_type, 'rpc_seconds': event['seconds']})
    if len({item['frame_ref'] for item in frames}) != 3:
        raise ValueError('Fresh image references were reused')
    report = {'offline_only': True, 'device_access': False, 'network_access': False,
              'experimental_contract_passed': True, 'production_stock_acceptance': False,
              'account_collection_verified': False, 'input_denial_verified': True,
              'xml_values_atomic': False, 'visual_image_identity_review_required': True,
              'frames': frames}
    (directory / 'quote-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    audit(parser.parse_args().directory)
