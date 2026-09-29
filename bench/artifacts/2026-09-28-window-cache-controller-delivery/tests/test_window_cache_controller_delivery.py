# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_controller_delivery import NAME, CORE, HEADER, SCHEDULER, SLOT_BYTES, LABELS, envelope, fixture, relocated_constants, validate_slot

class WindowCacheControllerDeliveryTests(unittest.TestCase):
    def test_exact_module_and_identity_oracle(self):
        qualified = ROOT / 'bench/artifacts/2026-09-28-window-cache-controller/build/module.bin'
        module = qualified.read_bytes(); slot = fixture(module)
        self.assertEqual(len(slot), SLOT_BYTES)
        self.assertEqual(slot[HEADER-CORE:HEADER-CORE+8], b'VCC2\x00\x01\x00\x42')
        validate_slot(slot, module)
        for index in (0,212,213,len(module)-1,len(module),HEADER-CORE,HEADER-CORE+5,SLOT_BYTES-1):
            bad = bytearray(slot); bad[index] ^= 1
            with self.subTest(offset=index), self.assertRaises(ValueError): validate_slot(bad, module)
        with self.assertRaises(ValueError): fixture(b'')
        with self.assertRaises(ValueError): fixture(bytes(HEADER-CORE+1))

    def test_source_relocation_moves_only_sources_never_installed_destinations(self):
        directory = ROOT / 'bench/artifacts' / NAME
        original = (directory / 'build/8502/scheduler-overlay-delivery.inc').read_text()
        expected = (directory / 'build/scheduler-overlay-delivery.inc').read_text()
        self.assertEqual(relocated_constants(original), expected)
        pattern = r'^(\w+)\s*=\s*\$([0-9a-f]+)$'
        old = {n:int(v,16) for n,v in re.findall(pattern,original,re.M)}
        new = {n:int(v,16) for n,v in re.findall(pattern,expected,re.M)}
        self.assertEqual(set(old),set(new))
        moved = {'SCHEDULER_OVERLAY_LOAD','SCHEDULER_OVERLAY_END','SCHEDULER_OVERLAY_PAGE_SOURCE',
            'SCHEDULER_OVERLAY_TAIL_SOURCE','TASK_ACTIVATION_CONTEXT_SOURCE','TASK_ACTIVATION_TAIL_SOURCE'}
        self.assertEqual({n for n in old if old[n]!=new[n]}, moved)
        for n in moved: self.assertEqual(new[n]-old[n],0x1000)
        with self.assertRaises(ValueError): relocated_constants(original.replace('$5000','$5100'))
        with self.assertRaises(ValueError): relocated_constants(original.replace('TASK_ACTIVATION_TAIL_SOURCE','BAD'))

    def test_envelope_contains_the_qualified_whole_module_and_exact_scheduler(self):
        directory = ROOT / 'bench/artifacts' / NAME; build = directory / 'build'
        report = json.loads((build / 'build-report.json').read_text())
        module = (build / 'core.bin').read_bytes()
        scheduler = (directory / 'build/boot/scheduler-overlay.prg').read_bytes()
        payload = envelope(scheduler, module)
        self.assertEqual(payload,(build / 'secondary.prg').read_bytes())
        self.assertEqual(payload[:2],b'\x00\x42')
        self.assertEqual(payload[2:2+SLOT_BYTES],fixture(module))
        self.assertFalse(any(payload[2+SLOT_BYTES:2+SCHEDULER-CORE]))
        self.assertEqual(payload[2+SCHEDULER-CORE:],scheduler[2:])
        self.assertEqual(CORE+len(payload)-2,0x7229)
        self.assertEqual(report['resident_delivery_bytes_added'],0)
        for key, root in (('inputs_sha256',directory),('linked_sha256',build),('disk_sha256',build)):
            for n,sha in report[key].items():
                self.assertEqual(hashlib.sha256((root / n).read_bytes()).hexdigest(),sha,n)
        for n,deltas in report['relocation_deltas'].items():
            old=(directory / 'build/boot' / (n+'.bin')).read_bytes();new=(build / (n+'.bin')).read_bytes()
            self.assertEqual(len(old),len(new))
            self.assertEqual([(i,a,b) for i,(a,b) in enumerate(zip(old,new)) if a!=b],
                [tuple(v) for v in deltas])
        # Every copied live activation byte keeps its checksum covered.
        include=(build / 'boot-console-delivery.inc').read_text()
        checksum=int(re.search(r'BOOT_CONSOLE_IMAGE_CHECKSUM = \$([0-9a-f]+)',include)[1],16)
        self.assertEqual(checksum,sum((directory / 'build/boot/8502-boot-console.bin').read_bytes()+
            (build / 'task-switch-activation.bin').read_bytes())&65535)
        for offset in (0,2,6,20,22+0x400+0xc6b-1):
            bad=bytearray(scheduler);bad[offset]^=1
            # The historical parser checks the installed scheduler checksum,
            # not its separate context extension (covered elsewhere).
            with self.subTest(offset=offset),self.assertRaises(ValueError): envelope(bad,module)

    def test_two_formats_two_emulators_bind_all_lifetime_captures_and_drag_gates(self):
        directory=ROOT / 'bench/artifacts' / NAME; results=ROOT / 'bench/results' / NAME
        report=json.loads((directory / 'build/build-report.json').read_text())
        module=(directory / 'build/core.bin').read_bytes()
        for engine in ('vice','1986'):
            binding=json.loads((results / f'{engine}-binding.json').read_text())
            self.assertEqual(binding['disk_sha256'],report['disk_sha256'])
            self.assertEqual(binding['build_report_sha256'],hashlib.sha256((directory / 'build/build-report.json').read_bytes()).hexdigest())
            for n,sha in binding['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / n).read_bytes()).hexdigest(),sha,n)
            run=json.loads((results / f'{engine}-results.json').read_text())
            self.assertEqual(set(run),{'d71','d64'})
            for fmt in ('d71','d64'):
                if engine=='vice':
                    self.assertEqual(set(run[fmt]),LABELS)
                    for label in LABELS:
                        raw=(results / f'vice-{fmt}-{label}-core.bin').read_bytes()
                        self.assertEqual(raw[:2],b'\x00\x42')
                        self.assertEqual(validate_slot(raw[2:],module),run[fmt][label])
                else:
                    raw=(results / f'1986-{fmt}-core.bin').read_bytes()
                    self.assertEqual(validate_slot(raw,module),run[fmt])
                    log=(results / f'1986-{fmt}.log').read_text()
                    self.assertEqual(sum(s.startswith('stress ') for s in log.splitlines()),32)
                    self.assertIn('PASS: repeated native wave drags and console cancellation',log)
        for path in (directory,results):
            for line in (path / 'SHA256SUMS').read_text().splitlines():
                sha,n=line.split('  ',1)
                self.assertEqual(hashlib.sha256((path / n).read_bytes()).hexdigest(),sha,n)
