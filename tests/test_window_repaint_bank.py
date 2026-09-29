# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('repaint_bank', ROOT / 'tools/window_repaint_bank.py')
bank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bank)


class RepaintBankTests(unittest.TestCase):
    def test_complete_link_layout_rejects_growth_and_hidden_state(self):
        segments = [('ZEROPAGE',6,31),('ENTRY',0xD100,0xD102),
                    ('CODE',0xD103,0xDDD5),('HIGHBSS',0xDFE0,0xDFF1)]
        self.assertEqual(bank.verify_layout(segments,3286)['CODE'], (0xD103,0xDDD5))
        for bad, size in (
                (segments+[('BSS',0x5200,0x5201)],3286),
                (segments[:-1]+[('HIGHBSS',0xDFE0,0xDFF2)],3286),
                (segments[:2]+[('CODE',0xD103,0xDFE0)]+segments[-1:],0xEE1),
                ([('ZEROPAGE',4,29)]+segments[1:],3286),
                (segments,3287)):
            with self.subTest(segments=bad, size=size), self.assertRaises(ValueError):
                bank.verify_layout(bad,size)

    def test_copied_diagnostic_has_no_unrelocated_control_flow(self):
        text = bank.diagnostic_driver((bank.OLD / 'driver.s').read_text())
        for name in ('upload','seed','scan'):
            block = text.split('\n'+name+':\n',1)[1].split('\n'+name+'_end:',1)[0]
            self.assertNotRegex(block, r'\b(?:jmp|jsr)\s+[a-z_]')
        self.assertIn('cpx #scan_end-scan\n        bcc install_scan', text)
        self.assertNotIn('bpl install_scan', text)
        self.assertIn('sta $dff2,x',text)
        self.assertIn('cmp $d000,y',text)
        self.assertIn('lda $5220,x',text)
        self.assertIn('lda $523a,x',text)

    def test_neighbor_ownership_cannot_silently_grow_into_the_candidate(self):
        memory = (ROOT / 'include/udeks/memory.h').read_text()
        cache = (ROOT / 'src/services/window/cache/layout.inc').read_text()
        bank.verify_ownership(memory,cache)
        with self.assertRaises(ValueError):
            bank.verify_ownership(memory.replace('0xD100u','0xD200u'),cache)
        with self.assertRaises(ValueError):
            bank.verify_ownership(memory,cache.replace('STACK_BOTTOM+$f0','STACK_BOTTOM+$110'))

    def test_packed_host_runs_the_same_command_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / 'oracle'
            subprocess.run(['cc','-std=c99','-O2','-fpack-struct=1','-Wno-unknown-pragmas',
                '-DREPAINT_HOST','-I'+str(ROOT / 'include'),'-I'+str(bank.SOURCE),
                str(bank.SOURCE / 'probe.c'),str(bank.SOURCE / 'dispatch.c'),
                str(ROOT / 'src/services/window/repaint_lane.c'),'-o',str(program)],check=True)
            self.assertEqual(subprocess.check_output([str(program)],text=True).strip(), '1415 53093 0')

    def test_binding_holds_irq_mask_until_map_restoration(self):
        binding = (bank.SOURCE / 'binding.s').read_text()
        self.assertIn('jsr RUN\n        plp\n        rts', binding)
        self.assertNotIn('plp\n        jmp RUN', binding)
        gate = (bank.SOURCE / 'gateway.s').read_text()
        self.assertIn('sta WORKER',gate)
        self.assertLess(gate.index('sta KERNEL'), gate.index('restore_zp:'))
        self.assertLess(gate.index('restore_zp:'), gate.index('        plp'))

    def test_decoder_rejects_runtime_leaks_even_with_a_correct_trace(self):
        expected = {'calls':1415,'trace':53093}
        data = bytearray(8096)
        data[:8] = b'RBNK\x01\x02\0\0'
        data[8:10] = (1415).to_bytes(2,'little')
        data[10:12] = (53093).to_bytes(2,'little')
        data[12] = 1; data[23] = 0xB0; data[24] = 15
        self.assertEqual(bank.decode(data,expected)['detected_fields'],[])
        for offset in (7,8,10,16,17,18,19,20,21,22,24,25,8095):
            bad = bytearray(data); bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                bank.decode(bad,expected)
        bad = bytearray(data); bad[23] = 0x3F
        with self.assertRaises(ValueError): bank.decode(bad,expected)

    def test_each_injected_fault_requires_its_exact_observation(self):
        expected = {'calls':1415,'trace':53093}
        for case, fields in (('zp-leak',(17,)),('irq-leak',(16,)),('shell-stack',(20,22))):
            data = bytearray(8096); data[:8] = b'RBNK\x01\x02\0\0'
            data[8:10] = (1415).to_bytes(2,'little')
            data[10:12] = (53093).to_bytes(2,'little')
            data[12] = 1; data[23] = 0xF0 if case == 'shell-stack' else 0xB0; data[24] = 15
            for i in fields: data[i] = 1
            self.assertEqual(bank.decode(data,expected,case)['detected_fields'],list(fields))
            with self.assertRaises(ValueError): bank.decode(data,expected)
            data[fields[0]] = 0
            with self.assertRaises(ValueError): bank.decode(data,expected,case)
