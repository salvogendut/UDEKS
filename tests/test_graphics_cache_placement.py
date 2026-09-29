# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_cache_placement import audit, listing_functions, measured_reserve, object_sizes, validate_contracts

EVIDENCE = ROOT / 'bench/artifacts/2026-09-28-graphics-cache-placement'


def inputs():
    def read(name, binary=False):
        data = (EVIDENCE / 'inputs' / name).read_bytes()
        return data if binary else data.decode()
    return [
        read('build/8502/udeks-8502.map'), read('build/8502/udeks-scheduler-overlay.map'),
        read('build/8502/task-context-binding.map'), read('build/boot/scheduler-overlay.prg', True),
        read('build/8502/udeks-scheduler-overlay-page.bin', True),
        read('build/8502/udeks-scheduler-overlay-tail.bin', True),
        read('build/8502/task-context-binding.bin', True), read('build/8502/task-switch-tail.bin', True),
        read('build/8502/task-yield-handler.bin', True), read('build/8502/task-context-vectors.bin', True),
        listing_functions((EVIDENCE / 'raster.lst').read_text()),
        measured_reserve((EVIDENCE / 'transport.lst').read_text(), 'raster_scratch_placement_reserve'),
        [(EVIDENCE / f'{name}.segments.txt').read_text() for name in ('cache', 'rows', 'transfer')],
    ]


class GraphicsCachePlacementTests(unittest.TestCase):
    def test_memory_contract_drift_requires_inventory_review(self):
        header = (EVIDENCE / 'inputs/include/udeks/memory.h').read_text()
        task = (EVIDENCE / 'inputs/include/udeks/task.h').read_text()
        cfg = (EVIDENCE / 'inputs/cfg/8502-bootstrap.cfg').read_text()
        validate_contracts(header, task, [(cfg, 'MODULE', 0xE300, 0x0344)])
        with self.assertRaisesRegex(ValueError, 'C_STACK_BOTTOM'):
            validate_contracts(header.replace('0xE700u', '0xE800u'), task, [])
        with self.assertRaisesRegex(ValueError, 'TASK_STACK_TOP'):
            validate_contracts(header, task.replace('0xF7F0u', '0xF6F0u'), [])
        with self.assertRaisesRegex(ValueError, 'linker reservation'):
            validate_contracts(header, task, [(cfg.replace('$0344', '$0345'), 'MODULE', 0xE300, 0x0344)])

    def test_exact_archived_audit(self):
        result = audit(*inputs())
        report = json.loads((EVIDENCE / 'report.json').read_text())
        self.assertEqual(result, {name: report[name] for name in result})
        self.assertEqual(result['candidate'], dict(code=1005, bss=18, total=1023,
                         qualified_reserve=49, additional_bytes_before_bindings=974))
        self.assertEqual(result['raster_code_before_replacements'], 2023)

    def test_all_post_shadow_bytes_have_an_owner(self):
        region = audit(*inputs())['post_shadow']
        self.assertEqual(region['primary_map_gap'], 3552)
        self.assertEqual(region['scheduler_code_state'], 1875)
        self.assertEqual(region['scheduler_packaging_padding'], 141)
        self.assertEqual(region['lifecycle_handler'], 1163)
        self.assertEqual(region['handler_reserved_slack'], 50)
        self.assertEqual(region['context_code_state'], 323)
        self.assertEqual(region['unowned_bytes'], 0)
        self.assertEqual(sum(region[name] for name in ('scheduler_code_state',
            'scheduler_packaging_padding', 'lifecycle_handler', 'handler_reserved_slack',
            'context_code_state')), region['primary_map_gap'])

    def test_guard_stack_and_app_slot_are_not_reclaim(self):
        result = audit(*inputs())
        self.assertTrue(all(not item['available_to_cache'] for item in result['other_regions']))
        module = next(item for item in result['other_regions'] if item['name'] == 'module linker area')
        self.assertEqual(module['linked_slack'], 0)
        # The header's $E645 exclusive limit is one byte beyond the linker's
        # $E644 limit. That byte is owned, not permission to expand MODULE.
        extra = next(item for item in result['other_regions'] if item['name'] == 'module contract extra byte')
        self.assertEqual((extra['base'], extra['end']), (0xE644, 0xE644))

    def test_payload_corruption_cannot_pass(self):
        args = inputs()
        data = bytearray(args[3]); data[100] ^= 1; args[3] = bytes(data)
        with self.assertRaisesRegex(ValueError, 'payload does not match'):
            audit(*args)

    def test_handler_cannot_be_measured_against_a_stale_payload(self):
        args = inputs(); args[8] = args[8][:-1]
        with self.assertRaisesRegex(ValueError, 'payload does not match'):
            audit(*args)

    def test_context_state_is_counted_even_though_not_emitted(self):
        args = inputs(); args[2] = args[2].replace('00CEFF', '00CEFE')
        with self.assertRaisesRegex(ValueError, 'context'):
            audit(*args)

    def test_shadow_drift_fails_closed(self):
        args = inputs(); args[0] = args[0].replace('00C11F', '00C120')
        with self.assertRaisesRegex(ValueError, 'shadow moved'):
            audit(*args)

    def test_live_low_state_overrun_fails(self):
        args = inputs(); args[0] = args[0].replace('0011FC', '001200')
        with self.assertRaisesRegex(ValueError, 'LOWBSS'):
            audit(*args)

    def test_missing_primary_region_fails(self):
        args = inputs(); args[0] = args[0].replace('LOWBSS                000C00', 'OTHER                 000C00')
        with self.assertRaisesRegex(ValueError, 'missing required'):
            audit(*args)

    def test_listing_drift_fails(self):
        args = inputs(); args[10]['_udeks_vic_bitmap_fill']['size'] += 1
        with self.assertRaisesRegex(ValueError, 'listing and resident map'):
            audit(*args)

    def test_reserve_drift_fails(self):
        args = inputs(); args[11] = 50
        with self.assertRaisesRegex(ValueError, 'reserve changed'):
            audit(*args)

    def test_arbitrary_shared_padding_cannot_create_a_false_cache_budget(self):
        with self.assertRaisesRegex(ValueError, 'shared raster padding'):
            audit(*inputs(), primitives={'pixel': {'CODE': 190}, 'span': {'CODE': 102}},
                  primitive_reserve=173, shared_reserve=123)

    def test_candidate_additional_allocation_is_rejected(self):
        args = inputs(); args[12][0] += '\nName: "EXTRA"\nFlags: 0\nSize: 1\n'
        with self.assertRaisesRegex(ValueError, 'non-CODE/BSS'):
            audit(*args)

    def test_real_function_sizes_are_not_guessed_from_source_lines(self):
        functions = listing_functions((EVIDENCE / 'raster.lst').read_text())
        self.assertEqual(functions['_udeks_vic_bitmap_fill'], {'offset': 0x6E5, 'size': 647})
        self.assertEqual(sum(item['size'] for item in functions.values()), 4258)

    def test_bad_procedure_listing_fails(self):
        for text in ('', '000000r 1 .proc foo\n',
                     '000000r 1 .endproc\n',
                     '000000r 1 .proc foo\n000001r 1 .proc bar\n',
                     '000000r 1 .proc foo\n000000r 1 .endproc\n',
                     '000000r 1 .proc foo\n000002r 1 .endproc\n'
                     '000001r 1 .proc bar\n000003r 1 .endproc\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                listing_functions(text)

    def test_reserve_extent_is_assembled(self):
        text = (EVIDENCE / 'transport.lst').read_text()
        self.assertEqual(measured_reserve(text, 'outline_mask_placement_reserve'), 8)
        self.assertEqual(measured_reserve(text, 'raster_scratch_placement_reserve'), 49)
        with self.assertRaisesRegex(ValueError, 'extent mismatch'):
            measured_reserve(text.replace('00042Er', '00042Fr'), 'raster_scratch_placement_reserve')
        with self.assertRaisesRegex(ValueError, 'missing measured'):
            measured_reserve(text, 'missing')

    def test_object_measurements_require_code_and_state(self):
        self.assertEqual(object_sizes((EVIDENCE / 'cache.segments.txt').read_text())['CODE'], 607)
        for dump in ('', 'Name: "CODE"\nFlags: 0\nSize: 607\n',
                     'Name: "CODE"\nFlags: 0\nSize: 1\nName: "CODE"\nFlags: 0\nSize: 1\n'):
            with self.assertRaises(ValueError):
                object_sizes(dump)

    def test_evidence_hashes_and_exact_input_bindings(self):
        report = json.loads((EVIDENCE / 'report.json').read_text())
        for line in (EVIDENCE / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), digest, name)
        for name, digest in report['inputs_sha256'].items():
            self.assertEqual(hashlib.sha256((EVIDENCE / 'inputs' / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(hashlib.sha256((EVIDENCE / 'audit.py').read_bytes()).hexdigest(), report['audit_sha256'])


if __name__ == '__main__':
    unittest.main()
