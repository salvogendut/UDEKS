# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_window_cache import bindings, identity, wrap_scheduler, write_changed, layout_maps
from window_drag_start import candidate
from window_cache_runtime_probe import validate_live_slot
import window_cache_partial as partial
import test_window_drag_start as drag_tests

PROOF = ROOT / 'bench/artifacts/2026-09-29-window-cache-partial/build/bench/window-cache-partial'


class WindowCacheIntegrationTests(unittest.TestCase):
    def test_promoted_manager_matches_qualified_generic_candidate(self):
        self.assertEqual((ROOT / 'src/services/window/window_manager_cached.c').read_text().rstrip(),
                         candidate((ROOT / 'src/services/window/window_manager.c').read_text()).rstrip())

    def test_promoted_controller_matches_host_qualified_sources(self):
        providers = {
            'policy': partial.fixed_policy((ROOT / 'src/services/window/move_cache_state.c').read_text()),
            'command': partial.command((ROOT / 'src/services/window/cache_overlay.c').read_text()),
            'flow': partial.compact.shared_geometry((ROOT / 'src/services/window/move_cache_flow.c').read_text()),
            'controller': partial.controller((ROOT / 'bench/window-cache-controller/controller.c').read_text()),
        }
        providers['flow'] = providers['flow'].replace(
            '/* Budget/host-test prototype only. No normal build invokes these entries. */',
            '/* Bank-1 continuation for the selected window-cache build. */')
        for name, text in providers.items():
            self.assertEqual((ROOT / 'src/services/window/cache' / (name + '.c')).read_text().rstrip(),
                             text.rstrip(), name)

    def test_actual_promoted_manager_full_canvas_move_resize_close_and_cached_move(self):
        source = (ROOT / 'src/services/window/window_manager_cached.c').read_text()
        with patch('test_window_drag_start.candidate', lambda _: source):
            drag_tests.DragStartTests('test_deferred_client_calls_and_complete_canvas_after_release').\
                test_deferred_client_calls_and_complete_canvas_after_release()

    def test_bindings_derive_module_length_checksum_and_gateway_source(self):
        module, gate = (PROOF / 'module.bin').read_bytes(), (PROOF / 'gateway.bin').read_bytes()
        acceptance, loader = bindings(module, gate, (PROOF / 'module.map').read_text())
        self.assertIn('CACHE_LAST_PAGE = $0f', acceptance)
        self.assertIn('CACHE_LAST_BYTES = $83', acceptance)
        self.assertIn(f'CACHE_CHECKSUM = ${sum(module) & 65535:04x}', acceptance)
        self.assertEqual(loader, 'GATE_SOURCE = $50bf\nGATE_BYTES = $c4\n')
        self.assertEqual(identity(module), bytes.fromhex('5643433200010042830f') +
                         (sum(module) & 65535).to_bytes(2, 'little') + bytes.fromhex('d542b008'))
        changed = bytearray(module); changed[300] ^= 1
        self.assertNotEqual(bindings(bytes(changed), gate, (PROOF / 'module.map').read_text())[0], acceptance)

    def test_bindings_reject_missing_or_misplaced_gateway_and_private_state(self):
        module, gate = (PROOF / 'module.bin').read_bytes(), (PROOF / 'gateway.bin').read_bytes()
        text = (PROOF / 'module.map').read_text()
        for bad_module, bad_gate, bad_map in (
                (module[:-1], gate, text), (module, gate[:-1], text),
                (module, gate, text.replace('005220', '005221')),
                (module, gate, text.replace('004200', '004201'))):
            with self.assertRaises(ValueError):
                bindings(bad_module, bad_gate, bad_map)

    def test_secondary_disk_load_is_distinct_from_scheduler_header_source(self):
        reference = ROOT / 'bench/artifacts/2026-09-29-window-drag-start/inputs/build/window-drag-start/repo'
        payload = (reference / 'build/boot/scheduler-overlay.prg').read_bytes()
        constants = (reference / 'build/8502/scheduler-overlay-delivery.inc').read_text()
        module = (PROOF / 'module.bin').read_bytes()
        result, relocated = wrap_scheduler(payload, constants, module)
        self.assertEqual(result[:2], b'\x00\x42')
        self.assertEqual(result[2 + 0x6000 - 0x4200:], payload[2:])
        self.assertIn('SCHEDULER_OVERLAY_LOAD = $6000', relocated)
        self.assertEqual(result, (reference / 'build/boot/cache-secondary.prg').read_bytes())
        self.assertEqual(relocated, (reference / 'build/cache-delivery/scheduler-overlay-delivery.inc').read_text())
        with self.assertRaises(ValueError): wrap_scheduler(b'bad', constants, module)
        with self.assertRaises(ValueError): wrap_scheduler(payload, constants.replace('TASK_ACTIVATION_TAIL_SOURCE', 'BAD'), module)
        with self.assertRaises(ValueError): identity(bytes(0x1011))
        with self.assertRaises(ValueError): identity(b'')

    def test_configuration_timestamp_changes_only_on_selection_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            write_changed(path, b'0\n'); first = path.stat().st_mtime_ns
            write_changed(path, b'0\n'); self.assertEqual(path.stat().st_mtime_ns, first)
            write_changed(path, b'1\n'); self.assertEqual(path.read_bytes(), b'1\n')
        make = (ROOT / 'mk/window-cache.mk').read_text()
        self.assertIn('WINDOW_CACHE ?= 1', make)
        self.assertIn('$(CACHE_CONFIG)', make)
        self.assertNotIn('window_projection', make)
        self.assertNotIn('bench/artifacts', make)
        result = subprocess.run(['make', '-n', 'WINDOW_CACHE=2', 'boot'], cwd=ROOT, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_packaging_guard_rejects_shadow_drift_missing_segment_and_panic_mismatch(self):
        reference = ROOT / 'bench/artifacts/2026-09-29-window-drag-start/inputs/build/window-drag-start/repo/build/8502'
        normal = (reference / 'udeks-8502.map').read_text()
        panic = (reference / 'udeks-8502-panic-probe.map').read_text()
        self.assertEqual(layout_maps(normal, panic)['VICSHADOW'], (0xa1e0, 0xc11f, 8000))
        for text in (normal.replace('00A1E0', '00A1E1'), normal.replace('VICSHADOW', 'MISSING')):
            with self.assertRaises(ValueError): layout_maps(text, panic)
            with self.assertRaises(ValueError): layout_maps(normal, text)

    def test_command_reclaim_does_not_relax_public_reservations(self):
        reference = ROOT / 'bench/artifacts/2026-09-29-window-drag-start/inputs/build/window-drag-start/repo/build/8502'
        normal = (reference/'udeks-8502.map').read_text()
        for before, after in (('00E2E1  00012A', '00E2E2  00012B'),
                              ('00F904  000105', '00F909  00010A'),
                              ('00A1DF  0002B8', '00A1E0  0002B9')):
            damaged = normal.replace(before, after)
            self.assertNotEqual(normal, damaged)
            with self.assertRaises(ValueError): layout_maps(damaged, damaged)
        moved = normal.replace('00E2E1  00012A', '00E2E0  000129')
        with self.assertRaises(ValueError): layout_maps(normal, moved)

    def test_runtime_probe_normalizes_only_qualified_live_operands_and_scratch(self):
        module = (PROOF / 'module.bin').read_bytes()
        slot = bytearray(module.ljust(0x1010, b'\0') + identity(module))
        last = (0x5350 + 103 * 21).to_bytes(2, 'little')
        slot[0x4d:0x4f] = slot[0x74:0x76] = last
        slot[0xd1:0xd5] = bytes(4)
        self.assertEqual(validate_live_slot(slot, module, 168, 104)['bytes'], len(module))
        slot[300] ^= 1
        with self.assertRaises(ValueError): validate_live_slot(slot, module, 168, 104)
        slot[300] ^= 1; slot[0x4d] ^= 1
        with self.assertRaises(ValueError): validate_live_slot(slot, module, 168, 104)


if __name__ == '__main__':
    unittest.main()
