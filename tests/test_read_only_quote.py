from pathlib import Path
import copy
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from quote_read_probe import options, validate_receipt, verify_input_denial


class Receipt(unittest.TestCase):
    def test_read_only_proof_is_required_and_never_a_strict_frame(self):
        valid = {'foreground_package': 'com.guotai.dazhihui', 'width': 720, 'height': 1560,
                 'rotation': 0, 'read_only_quote_proof': {'schema': 1, 'contract': 'junhong-time-v1',
                 'symbol': '600999', 'name': '招商证券', 'period': '分时',
                 'input_authority': False, 'xml_values_atomic': False}}
        validate_receipt(valid)
        bad = [dict(valid, based_on_frame_ref='older'), dict(valid, rotation=1),
               dict(valid, foreground_package='other'), dict(valid, read_only_quote_proof=None)]
        for key, value in [('schema', True), ('symbol', '600150'), ('period', '日K'),
                           ('input_authority', True), ('xml_values_atomic', True)]:
            item = copy.deepcopy(valid)
            item['read_only_quote_proof'][key] = value
            bad.append(item)
        for item in bad:
            with self.assertRaises(ValueError):
                validate_receipt(item)
        self.assertNotIn('expected_frame_ref', options())
        self.assertNotIn('frame_ref', options())


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required')
class QuotePolicy(unittest.TestCase):
    def test_dynamic_quotes_preserve_identity_layout_sensitivity_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['javac', '-encoding', 'UTF-8', '-d', tmp,
                            str(ROOT / 'experimental/native/ReadOnlyQuote.java'),
                            str(ROOT / 'tests/guest/ReadOnlyQuoteProbe.java')], check=True, timeout=30)
            subprocess.run(['java', '-cp', tmp, 'ReadOnlyQuoteProbe'], check=True, timeout=15)


class InputAuthority(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_coordinates_never_hide_a_missing_identity_rejection(self):
        class Refusal(Exception):
            def __init__(self, phase):
                self.native_diagnostic = {'phase': phase, 'exception_type': 'IllegalStateException'}
        calls = []
        async def denied(operation, payload):
            calls.append((operation, payload))
            raise Refusal('observation_identity')
        self.assertTrue(await verify_input_denial(denied, 'fresh-read-only-frame'))
        self.assertEqual(calls, [('android.tap', {'arguments': {
            'frame_ref': 'fresh-read-only-frame', 'x': -1.0, 'y': -1.0}})])
        async def too_late(*args):
            raise Refusal('input_coordinates')
        async def accepted(*args):
            return {'applied': True}
        async def timed_out(*args):
            raise TimeoutError()
        for call in (too_late, accepted, timed_out):
            with self.assertRaises(ValueError):
                await verify_input_denial(call, 'frame')


class QuoteJourney(unittest.IsolatedAsyncioTestCase):
    async def test_quote_route_requires_proof_and_keeps_it_separate_from_strict_mode(self):
        from probe_public_journey import Journey, JUNHONG, TDX
        import xml.etree.ElementTree as ET
        for missing in (False, True):
            reads = []
            root = ET.Element('hierarchy')
            for text in ('600999', '招商证券', '分时'):
                ET.SubElement(root, 'node', {'package': JUNHONG, 'text': text})
            async def capture(phase, requested):
                reads.append((phase, requested))
                result = {'foreground_package': JUNHONG, 'width': 720, 'height': 1560, 'rotation': 0,
                          'hierarchy_xml': ET.tostring(root, encoding='unicode'),
                          'frame_ref': 'read-only-image', 'sensitive_inputs': []}
                if requested.get('read_only_quote') and not missing:
                    result['read_only_quote_proof'] = {'schema': 1, 'contract': 'junhong-time-v1',
                        'symbol': '600999', 'name': '招商证券', 'period': '分时',
                        'input_authority': False, 'xml_values_atomic': False}
                return result
            async def action(*args):
                self.fail('Already-open public quote needs no navigation input')
            journey = Journey(JUNHONG, capture, action, junhong_page='quote', read_only_quote=True)
            if missing:
                with self.assertRaises(ValueError):
                    await journey.navigate()
                self.assertEqual(len(reads), 2)
            else:
                result = await journey.navigate()
                self.assertEqual(result['frame_ref'], 'read-only-image')
                self.assertEqual(len(reads), 4)
                self.assertEqual([value for _, value in reads[1:]], [options()] * 3)
            with self.assertRaises(ValueError):
                Journey(TDX, capture, action, read_only_quote=True)
            with self.assertRaises(ValueError):
                Journey(JUNHONG, capture, action, read_only_quote=True)
