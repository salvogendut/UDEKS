# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_d71 import blank_d71, build_image, d64_compatibility_image, validate_managed_app, install_prg_file
from managed_app_fixture import dos_file, fixture, ERRORS


def app(base):
    return (b'UDEX\0\x01\x01\x02'+base.to_bytes(2, 'little')+b'\x13\0\x01\0'
            +base.to_bytes(2, 'little')+(b'\x4c'+(base+18).to_bytes(2, 'little'))*6+b'\x60')


class ManagedDiskTests(unittest.TestCase):
    def test_fourth_executable_has_independent_bounded_disk_image(self):
        from build_udex import build_executable
        draw=build_executable(b'\x60',cpu=1,load_address=0x3500,
            entry_address=0x3500,bss_size=0xaff)
        def pack(data):return build_image(b'CBM\0\x1c\0\xd4',b'',b'',b'',xdraw=data)
        disk=pack(draw)
        for image in (disk,d64_compatibility_image(disk)):
            _,offsets=dos_file(image,'XDRAW.BIN')
            self.assertEqual(bytes(image[p] for p in offsets),draw)
        for offset,value in ((9,0x23),(13,0x0b),(14,1),(7,2),(10,2)):
            bad=bytearray(draw);bad[offset]=value
            with self.subTest(offset=offset),self.assertRaises(ValueError):pack(bad)
        # Task 4 stages the header in its own smaller allocation too.
        full=build_executable(bytes(0xb00),cpu=1,load_address=0x3500,entry_address=0x3500)
        with self.assertRaises(ValueError):pack(full)

    def test_native_calculator_image_and_bss_bounds_before_packaging(self):
        from build_udex import build_executable
        calc=build_executable(b'\x60',cpu=1,load_address=0x2300,
            entry_address=0x2300,bss_size=0x11ff,flags=0)
        def pack(data):
            return build_image(b'CBM\0\x1c\0\xd4'+bytes(25),b'',b'',b'',xcalc=data)
        disk=pack(calc)
        _,offsets=dos_file(disk,'XCALC.BIN')
        self.assertEqual(bytes(disk[p] for p in offsets),calc)
        for offset,value in ((0,0),(5,2),(6,2),(7,1),(9,0x35),(10,2),(13,0x12),(14,1)):
            bad=bytearray(calc);bad[offset]=value
            with self.subTest(offset=offset), self.assertRaises(ValueError): pack(bad)
        for bad in (calc[:-1],calc+b'x',calc[:16]):
            with self.assertRaises(ValueError): pack(bad)
        # Header bytes also count against the loader's staging capacity.
        too_big=build_executable(bytes(0x1200),cpu=1,load_address=0x2300,
            entry_address=0x2300,bss_size=0,flags=0)
        with self.assertRaises(ValueError): pack(too_big)

    def test_calculator_extended_slot_is_explicit_and_staging_bounded(self):
        data=bytearray(app(0x0200))
        data[12:14]=(0x1000-19).to_bytes(2,'little')
        validate_managed_app(data,0x0200,0x1000)
        with self.assertRaises(ValueError): validate_managed_app(data,0x0200)
        with self.assertRaises(ValueError): validate_managed_app(app(0x1200),0x1200,0x1000)
        data[12:14]=(0x1000-18).to_bytes(2,'little')
        with self.assertRaises(ValueError): validate_managed_app(data,0x0200,0x1000)
        data=bytearray(app(0x0200))
        data.extend(bytes(0x1000-19))
        data[10:12]=(0x1000).to_bytes(2,'little');data[12:14]=b'\0\0'
        with self.assertRaisesRegex(ValueError,'staging'):
            validate_managed_app(data,0x0200,0x1000)
    def test_calculator_packaged_separately_not_as_an_ordinary_command(self):
        calc=app(0x0200)
        disk=build_image(b'CBM\0\x1c\0\xd4'+bytes(25),b'',b'',b'',xcalc=calc)
        for image in (disk,d64_compatibility_image(disk)):
            _,offsets=dos_file(image,'XCALC.BIN')
            self.assertEqual(bytes(image[p] for p in offsets),calc)
        self.assertNotIn('XCALC',(ROOT/'Makefile').read_text().split('$(USER_BOOTFS):',1)[1].split('\n\n',1)[0])

    def test_apps_are_raw_seq_on_both_formats(self):
        clock, wave = app(0x0200), app(0x1200)
        disk = build_image(b'CBM\0\x1c\0\xd4'+bytes(25), b'', b'', b'', xclock=clock, xwave=wave)
        for image in (disk, d64_compatibility_image(disk)):
            for name, data, base in (('XCLOCK', clock, 0x0200), ('XWAVE', wave, 0x1200)):
                _, offsets = dos_file(image, name+'.BIN')
                self.assertEqual(bytes(image[p] for p in offsets), data)
                validate_managed_app(data, base)

    def test_corrupt_app_rejected_before_packaging(self):
        for name, base in (('XCLOCK', 0x0200), ('XWAVE', 0x1200)):
            image = bytearray(blank_d71())
            install_prg_file(image, name, app(base), file_type=0x81)
            for variant in ERRORS.keys()-{'missing'}:
                with self.subTest(name=name, variant=variant):
                    bad = fixture(image, name, variant)
                    _, offsets = dos_file(bad, name)
                    with self.assertRaises(ValueError):
                        validate_managed_app(bytes(bad[p] for p in offsets), base)

    def test_all_six_callbacks_checked(self):
        for index in range(6):
            data = bytearray(app(0x0200)); data[16+3*index] = 0x60
            with self.assertRaises(ValueError): validate_managed_app(data, 0x0200)

    def test_exact_slot_limit_allowed_bss_overflow_rejected(self):
        data = bytearray(app(0x1200)); data[12:14] = (0xa00-19).to_bytes(2, 'little')
        validate_managed_app(data, 0x1200)
        data[12:14] = (0xa00-18).to_bytes(2, 'little')
        with self.assertRaises(ValueError): validate_managed_app(data, 0x1200)

    def test_truncated_extra_and_header_only_files_rejected(self):
        for data in (app(0x200)[:-1], app(0x200)+b'x', app(0x200)[:16]):
            with self.assertRaises(ValueError): validate_managed_app(data, 0x200)

    def test_normal_bootfs_has_no_graphical_payloads(self):
        rule = (ROOT/'Makefile').read_text().split('$(USER_BOOTFS):', 1)[1].split('\n\n', 1)[0]
        self.assertNotIn('XCLOCK', rule); self.assertNotIn('XWAVE', rule)
        self.assertIn('RECOVERY_USH', rule)

    def test_loader_failure_preserves_nonzero_condition_for_asm_caller(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        tail = source.split('task_fail_kernel:', 1)[1].split('rts', 1)[0]
        self.assertLess(tail.index('ldx #$00'), tail.index('lda #$01'))

    def test_reader_handles_second_directory_sector(self):
        image = bytearray(blank_d71())
        for n in range(8): install_prg_file(image, str(n), b'x', file_type=0x81)
        install_prg_file(image, 'XWAVE', app(0x1200), file_type=0x81)
        _, offsets = dos_file(image, 'XWAVE')
        self.assertEqual(bytes(image[p] for p in offsets), app(0x1200))
