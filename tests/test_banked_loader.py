# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from banked_loader_probe import fixture, poll_hook, request_record, SCRATCH
from graphics_app_layout import managed_size, disjoint, Region, CANDIDATE


class BankedLoader(unittest.TestCase):
    def test_banked_fixtures_use_absolute_callbacks_and_exact_limits(self):
        for base, capacity in ((0x2300, 0x1200), (0x3500, 0xB00)):
            program = fixture(base, capacity-16, 16)
            header = managed_size(program)
            self.assertEqual(header['allocation'], capacity)
            self.assertEqual(header['load'], base)
            self.assertEqual(len(program), capacity)
            self.assertEqual(program[34], 0x60)

    def test_probe_preserves_the_real_request_and_runs_at_normal_poll(self):
        record = request_record('load3')
        self.assertEqual(len(record), 38)
        self.assertEqual(record[:6], b'UTRQ\0\10')
        self.assertEqual(record[14:20], b'\x05load3')
        hook = poll_hook(0x8123, b'\xa9\0\x60', 3, record)
        self.assertEqual(hook[0xA0:0xC6], record)
        self.assertLessEqual(SCRATCH+len(hook), 0x1200)
        self.assertIn(b'\x20\x1c\xf9', hook)  # call, not goto, private gate
        self.assertIn(b'\x4c\x23\x81', hook)  # original managed poll continues
        self.assertIn(b'\xbd\x00\x0d\x9d\x59\xf3', hook)  # restore original UTRQ
        with self.assertRaises(ValueError): request_record('x'*17)

    def test_module_and_new_cpu_pages_do_not_overlap(self):
        disjoint(list(CANDIDATE)+[Region('loader', 1, 0xD900, 0xE000)])
        with self.assertRaises(ValueError):
            disjoint(list(CANDIDATE)+[Region('loader', 1, 0xD800, 0xE000)])

    def test_private_gate_and_lifetime_contracts(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        loader = (ROOT/'src/services/app/banked_loader.s').read_text()
        self.assertIn('boot_saved_activation = $0c00', source)
        self.assertNotIn('boot_saved_activation:  .res', source)
        self.assertIn('task_loader_end <= $fe20', source)
        self.assertIn('* <= $ff00', source)
        self.assertIn('lda DISK_LOADER_CHILD_STATE-8,x', source)
        gate = source.split('banked_load_gate:', 1)[1].split('task_loader_end:', 1)[0]
        self.assertLess(gate.index('php'), gate.index('sei'))
        self.assertLess(gate.index('cmp banked_signature,x'), gate.index('jsr $d900'))
        self.assertIn('sta MMU_LCR_KERNEL_IO\n        plp', gate)
        entry = loader.split('banked_entry:', 1)[1].split('load_image:', 1)[0]
        self.assertEqual(entry.count('jsr MEMORY_GATE'), 3)
        self.assertIn('jsr read_address', entry)
        publication = loader.split('jsr validate', 1)[1].split('done:', 1)[0]
        self.assertLess(publication.index('jsr install'), publication.index('sta banked_owned,x'))
        self.assertNotIn('$cf50', loader)
        self.assertNotIn('jmp ($', loader)

    def test_native_contexts_publish_last_and_managed_images_cannot_run(self):
        source = (ROOT/'src/services/app/banked_loader.s').read_text()
        activation = source.split('activate:',1)[1].split('reap:',1)[0]
        self.assertIn('lda banked_headers+7,x\n        jne bad_image', activation)
        self.assertLess(activation.index('jsr clear_metadata'), activation.index('; RUNNABLE is the publication'))
        self.assertIn('sta banked_owned,x           ; active/exited', activation)
        self.assertIn('initial_context: .byte 0,0,0,$24,$fd,0,0,$d5,1,$d6,1', source)
        self.assertIn('zero_pages: native_zero_pages', source)
        self.assertIn('stack_pages: native_stacks', source)
        self.assertIn('context_offsets: .byte 32,43', source)
        self.assertIn('jsr $ff16', source.split('return_code:',1)[1])
        self.assertIn('banked_owned,x\n        jeq invalid', source.split('reap:',1)[1])

    def test_delivery_declares_build_inputs(self):
        make = (ROOT/'Makefile').read_text()
        self.assertIn('$(TASK_YIELD_HANDLER_BIN) $(BANKED_LOADER_BIN)', make)
        self.assertIn('--banked-loader $(BANKED_LOADER_BIN)', make)
        self.assertIn('$(BANKED_LOADER_BIN) $(BUILD_BOOT)/banked-loader.map $(BANKED_RELOC_BIN) $(BANKED_ACCESS_BIN) &:', make)
        self.assertIn('--banked-reloc $(BANKED_RELOC_BIN)', make)
        self.assertIn('--banked-access $(BANKED_ACCESS_BIN)', make)
        self.assertIn('size = $0700', (ROOT/'cfg/8502-banked-loader.cfg').read_text())
