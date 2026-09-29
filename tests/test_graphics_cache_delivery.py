# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from graphics_cache_delivery import CORE,HEADER,NAME,envelope,envelope_fixture,validate_slot
from placement_audit import parse_map


def canonical():
    page=bytes((i*13+7)&255 for i in range(1024));tail=bytes(range(256))
    h=b'USOV\x00\x03'+b'\x00\x1c\x00\x04\x20\xc1\x00\x01\x20\xc2\x03\x00'
    h+=(sum(page+tail)&65535).to_bytes(2,'little')
    return b'\x00\x50'+h+page+tail+bytes(234+192)


class GraphicsCacheDeliveryTests(unittest.TestCase):
    def test_secondary_prefix_leaves_all_scheduler_bytes_at_original_addresses(self):
        scheduler=canonical();core=bytes(range(213));payload=envelope(scheduler,core)
        self.assertEqual(payload[:2],b'\x00\x42')
        self.assertEqual(payload[2:2+512],envelope_fixture(core))
        self.assertEqual(payload[2+512:2+0xe00],bytes(0xe00-512))
        self.assertEqual(payload[2+0xe00:],scheduler[2:])
        self.assertEqual(0x4200+len(payload)-2,0x5000+len(scheduler)-2)
        validate_slot(payload[2:514],core)

    def test_builder_rejects_bad_identity_capacity_layout_and_checksum(self):
        scheduler=canonical()
        for core in (b'',bytes(HEADER-CORE+1)):
            with self.assertRaises(ValueError):envelope(scheduler,core)
        for offset in (0,2,6,7,8,10,12,14,20,22):
            broken=bytearray(scheduler);broken[offset]^=0x80
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                envelope(broken,b'core')
        # A different BSS placement/size inside the reservation is legal. Test
        # the actual bounds rather than rejecting arbitrary bit changes.
        for start,size in ((0xc220,0),(0xc220,256),(0xc11f,3),
                           (0xc900,3),(0xc8ff,3)):
            broken=bytearray(scheduler)
            broken[16:18]=start.to_bytes(2,'little')
            broken[18:20]=size.to_bytes(2,'little')
            with self.subTest(start=start,size=size),self.assertRaises(ValueError):
                envelope(broken,b'core')
        allowed=bytearray(scheduler)
        allowed[16:18]=(0xc2a0).to_bytes(2,'little')
        allowed[18:20]=(131).to_bytes(2,'little')
        self.assertEqual(envelope(allowed,b'core')[2+0xe00:],allowed[2:])
        with self.assertRaises(ValueError):envelope(scheduler[:-1],b'core')
        slot=envelope_fixture(b'core')
        for offset in (0,3,4,HEADER-CORE-1,HEADER-CORE,511):
            broken=bytearray(slot);broken[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):validate_slot(broken,b'core')
        with self.assertRaises(ValueError):validate_slot(slot[:-1],b'core')

    def test_preserved_delivery_is_a_one_byte_loader_change_and_core_prefix_only(self):
        directory=ROOT / 'bench/artifacts' / NAME
        build=directory / 'build';report=json.loads((build / 'build-report.json').read_text())
        self.assertTrue({'build/boot/stage1.bin','build/boot/stage1-gateway.bin',
            'build/8502/scheduler-overlay-delivery.inc','tools/vice_capture.py',
            'tools/capability_relocation_probe.py'} <= set(report['inputs_sha256']))
        original=(directory / 'build/boot/stage1.bin').read_bytes()
        changed=(build / 'stage1.bin').read_bytes()
        self.assertEqual(len(original),len(changed))
        diff=[i for i,(a,b) in enumerate(zip(original,changed)) if a!=b]
        self.assertEqual(diff,[report['stage1_changed_offset']])
        self.assertEqual((original[diff[0]],changed[diff[0]]),(0x50,0x42))
        self.assertGreaterEqual(diff[0],0x3bb)
        scheduler=(directory / 'build/boot/scheduler-overlay.prg').read_bytes()
        payload=(build / 'secondary.prg').read_bytes();core=(build / 'core.bin').read_bytes()
        self.assertEqual(payload,envelope(scheduler,core))
        self.assertEqual(report['end'],0x5000+len(scheduler)-2)
        for name,sha in report['disk_sha256'].items():
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),sha)
        for name,sha in report['inputs_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha)

    def test_lifetime_captures_and_native_input_drag_logs(self):
        artifacts=ROOT / 'bench/artifacts' / NAME
        results=ROOT / 'bench/results' / NAME
        core=(artifacts / 'build/core.bin').read_bytes()
        vice=json.loads((results / 'vice-results.json').read_text())
        native=json.loads((results / '1986-results.json').read_text())
        self.assertEqual(set(vice),{'d71','d64'});self.assertEqual(set(native),{'d71','d64'})
        expected={'boot','xinit','clock','wave','complete','utilities','shutdown','restart'}
        for fmt in ('d71','d64'):
            self.assertEqual(set(vice[fmt]),expected)
            for label in expected:
                capture=(results / f'vice-{fmt}-{label}-core.bin').read_bytes()
                self.assertEqual(capture[:2],b'\x00\x42')
                self.assertEqual(validate_slot(capture[2:],core),vice[fmt][label])
            self.assertEqual(validate_slot((results / f'1986-{fmt}-core.bin').read_bytes(),core),native[fmt])
            log=(results / f'1986-{fmt}.log').read_text()
            self.assertIn('PASS: repeated native wave drags and console cancellation',log)
            self.assertEqual(sum(line.startswith('stress ') for line in log.splitlines()),32)
        for directory in (artifacts,results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
            self.assertFalse(list(directory.rglob('*.vsf')))

    def test_c_policy_helper_link_is_measured_not_claimed_executed(self):
        directory=ROOT / 'bench/artifacts' / NAME
        build=directory / 'build';report=json.loads((build / 'policy-report.json').read_text())
        self.assertIn('unexecuted',report['qualification'])
        self.assertEqual(report['policy_object']['CODE'],1828)
        self.assertEqual(report['policy_object']['BSS'],0)
        self.assertEqual(report['helper_bytes'],526)
        self.assertEqual(report['linked_bytes'],213+1828+526)
        self.assertEqual(report['cc65_record_bytes'],{'lease':13,'row':9})
        self.assertEqual(report['candidate_private_stack'],[0x4d00,0x4def])
        self.assertEqual(report['candidate_identity'],[0x4df0,0x4dff])
        self.assertEqual(report['candidate_image'],[0x4e00,0x5bff])
        self.assertLessEqual(21*104,0x5c00-0x4e00)
        self.assertGreater(28*160,0x5c00-0x4e00)
        objects,segments=parse_map((build / 'policy-module.map').read_text())
        self.assertEqual(objects['move-cache-state.o']['CODE'],1828)
        self.assertEqual(dict((n,(s,e)) for n,s,e in segments)['ZEROPAGE'],(6,31))
        for name,sha in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha)
        for name,key in (('policy-module.bin','binary_sha256'),('policy-module.map','map_sha256')):
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),report[key])
