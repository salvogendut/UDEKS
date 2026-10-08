# SPDX-License-Identifier: GPL-3.0-or-later
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_time_overlay import overlay_config, qualify, resident_objects
from service_image import TIME_BASE, TIME_LIMIT


class TimeOverlayTests(unittest.TestCase):
    def baseline(self):
        return dict(CODE=(0x2006, 0x8000, 0x5ffb), RODATA=(0x8001, 0x8100, 256),
                    DATA=(0x8101, 0x8103, 3), BSS=(0x8104, TIME_BASE-1, TIME_BASE-0x8104),
                    VDCASSETS=(TIME_LIMIT, 0x9aff, 0x9b00-TIME_LIMIT),
                    SYSCALLS=(0xcf00, 0xcffe, 255), ZEROPAGE=(4, 0x1f, 28))

    def check_layout(self, modify=None, image_modify=None):
        baseline = self.baseline()
        candidate = dict(baseline, SERVICEBOOT=(TIME_BASE, TIME_BASE+517, 518))
        if modify:
            modify(candidate)
        symbols = {'_udeks_time_slot_set': (0x4000, 'RLA'), '_udeks_time_now': (0x5000, 'RLA')}
        image = bytearray(0xb000)
        image[0xaf40:0xaf43] = b'\x4c\0\x40'
        image[0xaf60:0xaf63] = b'\x4c\0\x50'
        if image_modify:
            image_modify(image)
        return qualify(baseline, candidate, symbols, image)

    def test_actual_live_end_not_sum_estimate_controls_free_space(self):
        result = self.check_layout()
        self.assertEqual(result['remaining_before_slot'], 0)
        self.assertEqual(result['startup_bytes'], 518)

    def test_resident_one_byte_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, 'BSS overlaps'):
            self.check_layout(lambda c: c.update(BSS=(0x8104, TIME_BASE, TIME_BASE-0x8104+1)))

    def test_startup_code_cannot_exceed_module_region(self):
        with self.assertRaisesRegex(ValueError, 'startup overlay'):
            self.check_layout(lambda c: c.update(SERVICEBOOT=(TIME_BASE, TIME_LIMIT, TIME_LIMIT-TIME_BASE+1)))

    def test_protected_memory_cannot_be_borrowed_for_fit(self):
        for name in ('VDCASSETS', 'ZEROPAGE', 'SYSCALLS'):
            with self.subTest(segment=name), self.assertRaisesRegex(ValueError, 'protected segment'):
                self.check_layout(lambda c: c.update({name: (c[name][0]-1, c[name][1], c[name][2]+1)}))

    def test_hidden_new_reservations_and_removed_regions_rejected(self):
        with self.assertRaisesRegex(ValueError, 'new or missing'):
            self.check_layout(lambda c: c.update(HIDDEN=(0xf000, 0xf010, 17)))
        with self.assertRaisesRegex(ValueError, 'new or missing'):
            self.check_layout(lambda c: c.pop('ZEROPAGE'))

    def test_both_published_clock_vectors_are_checked_in_binary(self):
        for offset in (0xaf40, 0xaf60):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'clock vector'):
                self.check_layout(image_modify=lambda data: data.__setitem__(offset, 0x60))

    def test_every_split_output_is_redirected_and_bss_is_not_emitted(self):
        text = (ROOT/'cfg/8502-bootstrap.cfg').read_text()
        # Exercise the historical transformation on a pre-cutover config.
        text = re.sub(r'^    SERVICEBOOT:.*\n','',text,flags=re.M)
        result = overlay_config(text, Path('/tmp/udeks-overlay-test'))
        for name in re.findall(r'file\s*=\s*"([^"]*)"', result):
            self.assertTrue(not name or name.startswith('/tmp/udeks-overlay-test/build/'))
        self.assertIn('file = ""', result)
        self.assertIn(f'start = ${TIME_BASE:04X}', result)
        self.assertIn('file = %O', result)

    def test_unexpected_output_path_or_already_overlaid_config_rejected(self):
        for text in ('file="/tmp/foreign.bin";\n    VDCASSETS:',
                     'file="build/../foreign.bin";\n    VDCASSETS:',
                     'SERVICEBOOT:\n    VDCASSETS:'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                overlay_config(text, Path('/tmp/udeks-overlay-test'))

    def test_resident_link_order_preserved_and_library_is_not_double_linked(self):
        names = ['a.o', 'syscall_gate.o', 'time.o', 'service_registry.o', 'time_descriptor.o']
        text = ''.join(f'{name}:\n    CODE Offs=000000 Size=000001\n' for name in names)
        text += '/usr/share/cc65/lib/none.lib(helper.o):\n    CODE Offs=000000 Size=000001\n'
        self.assertEqual(resident_objects(text), names)
        with self.assertRaisesRegex(ValueError, 'time.o'):
            resident_objects(text.replace('time.o:', 'other.o:'))

    def test_all_candidate_placements_agree_with_host_contract(self):
        include = (ROOT/'src/services/module/time_slot.inc').read_text()
        base = int(re.search(r'SLOT = \$([0-9a-f]+)', include)[1], 16)
        limit = int(re.search(r'LIMIT = \$([0-9a-f]+)', include)[1], 16)
        self.assertEqual((base, limit), (TIME_BASE, TIME_LIMIT))
        cfg = (ROOT/'cfg/8502-time-module.cfg').read_text()
        self.assertIn(f'start=${base:04X}, size=${limit-base:04X}', cfg)
        fixture = (ROOT/'bench/time-module/slot_check.c').read_text()
        self.assertIn(f'#define SLOT 0x{base:04x}u', fixture)
        # NMOS indirect JMP must not straddle a page boundary.
        self.assertNotEqual((base+42)&255, 255)


if __name__ == '__main__':
    unittest.main()
