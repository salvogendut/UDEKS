# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from nmi_integration_probe import NAME, STUB, Z80_BOOT, Z80_RETURN, inspect_nmi
from window_completion_probe import inspect as inspect_completion
from gen_capability_imports import map_exports
from placement_audit import parse_map
from graphics_cache_placement import audit, listing_functions


class NmiIntegrationTests(unittest.TestCase):
    def test_decoder_requires_live_stub_vector_drain_and_unmodified_z80_gates(self):
        data = bytearray(48)
        data[:18] = Z80_RETURN
        data[18:26] = STUB
        data[29:37] = Z80_BOOT
        data[38:40] = (1000).to_bytes(2, 'little')
        data[42:44] = b'\xe2\xff'
        self.assertEqual(inspect_nmi(data)['coalesced_drains'], 1000)
        for offset in (*range(26), *range(29, 38), 42, 43):
            bad = bytearray(data); bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                inspect_nmi(bad)
        data[38:40] = bytes(2)
        with self.assertRaises(ValueError):
            inspect_nmi(data)

    def test_actual_link_charge_call_sites_and_frozen_memory(self):
        directory = ROOT / 'bench/artifacts' / NAME
        previous = ROOT / 'bench/artifacts/2026-09-28-window-completion'
        old, old_segments = parse_map((previous / 'build/8502/udeks-8502.map').read_text())
        text = (directory / 'build/8502/udeks-8502.map').read_text()
        modules, segments = parse_map(text)
        self.assertEqual(segments, old_segments)
        self.assertEqual(modules['nmi.o'], {'CODE': 71})
        self.assertEqual(modules['pointer.o'], {**old['pointer.o'], 'CODE': old['pointer.o']['CODE']+6})
        self.assertEqual(modules['vic_graphics_transport.o']['CODE'], old['vic_graphics_transport.o']['CODE']-77)
        for name in old:
            if name not in ('pointer.o', 'vic_graphics_transport.o'):
                self.assertEqual(modules[name], old[name], name)
        symbols = map_exports(text)
        kernel = (directory / 'build/8502/udeks-8502.bin').read_bytes()
        pointer_offset = next(int(value, 16) for value in re.findall(
            r'pointer.o:\n\s+CODE\s+Offs=([0-9A-F]+)', text))
        pointer = kernel[6+pointer_offset:6+pointer_offset+modules['pointer.o']['CODE']]
        for name in ('_udeks_nmi_start', '_udeks_nmi_drain'):
            address = symbols[name][0]
            self.assertEqual(pointer.count(b'\x20'+address.to_bytes(2, 'little')), 1, name)
        self.assertEqual(kernel.count(STUB), 1)
        panic, panic_segments = parse_map((directory / 'build/8502/udeks-8502-panic-probe.map').read_text())
        self.assertEqual(panic_segments, segments)
        self.assertEqual(panic['nmi.o'], modules['nmi.o'])
        self.assertEqual(panic['pointer.o'], modules['pointer.o'])
        source = (directory / 'src/8502/pointer_irq.s').read_text()
        start = source.split('_udeks_pointer_start:', 1)[1].split('_udeks_pointer_resynchronize:', 1)[0]
        self.assertLess(start.index('jsr _udeks_nmi_start'), start.index('sta PTR+5\n        cli'))
        irq = source.split('pointer_irq:', 1)[1]
        self.assertIn('cld\n        jsr _udeks_nmi_drain', irq)

    def test_preserved_normal_disk_and_run_input_bindings(self):
        directory = ROOT / 'bench/artifacts' / NAME
        results = ROOT / 'bench/results' / NAME
        report = json.loads((directory / 'build-report.json').read_text())
        self.assertEqual((report['resident_nmi_charge'], report['remaining_padding'],
            report['binding_bytes'], report['remaining_before_manager_delivery']), (77, 281, 241, 40))
        for name, sha in report['inputs_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), sha, name)
        self.assertEqual(hashlib.sha256((directory / 'native.c').read_bytes()).hexdigest(), report['native_sha256'])
        for fmt, sha in report['disk_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / f'udeks.{fmt}').read_bytes()).hexdigest(), sha)
        for root in (directory, results):
            for line in (root / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), sha, name)
        for engine in ('1986', 'vice'):
            run = json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['build_report_sha256'], hashlib.sha256((directory / 'build-report.json').read_bytes()).hexdigest())
            for name, sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / name).read_bytes()).hexdigest(), sha, name)
            for fmt in ('d71', 'd64'):
                actual = {**inspect_nmi((results / f'{engine}-{fmt}-nmi.bin').read_bytes()),
                    **inspect_completion((results / f'{engine}-{fmt}-windows.bin').read_bytes(),
                        (results / f'{engine}-{fmt}-gateway.bin').read_bytes(), report['completion_entry'])}
                self.assertEqual(actual, run['decoded'][fmt])
                self.assertGreater(actual['coalesced_drains'], 100)
            if engine == '1986':
                for fmt in ('d71', 'd64'):
                    log = (results / f'{engine}-{fmt}.log').read_text()
                    self.assertIn('NMI: RESTORE and CIA2 timer drained', log)
                    self.assertIn('PASS: native boot', log)

    def test_production_never_links_diagnostic_nmi_observer(self):
        makefile = (ROOT / 'Makefile').read_text()
        self.assertNotIn('bench/window-cache-nmi/probe.s', makefile)
        self.assertIn('src/8502/nmi.s src/8502/nmi-common.inc', makefile)
        include = (ROOT / 'src/8502/nmi-common.inc').read_text()
        self.assertIn('UDEKS_NMI_ENTRY = $ffe2', include)
        self.assertIn('UDEKS_NMI_PENDING = $fff5', include)
        self.assertIn('UDEKS_NMI_DRAINS = $fff6', include)

    def test_shadow_install_budget_and_nmi_growth_rejection(self):
        directory = ROOT / 'bench/results' / (NAME+'-layout')
        artifacts = ROOT / 'bench/artifacts' / NAME
        report = json.loads((directory / 'report.json').read_text())
        build = json.loads((artifacts / 'build-report.json').read_text())
        self.assertEqual(report['disk_sha256'], build['disk_sha256']['d71'])
        self.assertEqual((report['shadow_clear_bytes'], report['tail_preimage_bytes'],
            report['remaining_padding'], report['owned_post_shadow_bytes']), (8000, 50, 281, 3552))
        self.assertFalse(any((directory / 'shadow-boot.bin').read_bytes()[:8000]))
        self.assertEqual((directory / 'shadow-drawn.bin').read_bytes(), (directory / 'vic-bitmap.bin').read_bytes())
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), sha, name)
        # Reconstruct the audit using frozen inputs. Existing scheduler inputs
        # are shared with the earlier audit and bound by their exact hashes.
        from test_graphics_cache_placement import inputs
        args = inputs()
        args[0] = (artifacts / 'build/8502/udeks-8502.map').read_text()
        args[10] = listing_functions((directory / 'raster.lst').read_text())
        args[12] = [(directory / f'{name}.segments.txt').read_text() for name in ('cache','rows','transfer')]
        placement = json.loads((directory / 'placement.json').read_text())
        primitives = placement['integrated_primitives']
        actual = audit(*args, primitives=primitives, primitive_reserve=173, shared_reserve=59)
        self.assertEqual(actual, {name: placement[name] for name in actual})
        old = args[0]
        for module, field in (('nmi.o', 'CODE'), ('pointer.o', 'CODE')):
            args[0] = re.sub(r'('+re.escape(module)+r':\n\s+'+field+r'\s+Offs=[0-9A-F]+\s+Size=)([0-9A-F]+)',
                lambda m: m[1]+f'{int(m[2],16)+1:06X}', old, count=1)
            with self.subTest(module=module), self.assertRaisesRegex(ValueError, 'NMI footprint'):
                audit(*args, primitives=primitives, primitive_reserve=173, shared_reserve=59)
