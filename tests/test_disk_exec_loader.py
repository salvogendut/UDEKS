# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from gen_disk_loader_bindings import render


class DiskExecLoader(unittest.TestCase):
    def test_ownership_binding_uses_linked_scheduler(self):
        fixture = ('Exports list by name:\n'
                   '_udeks_lifecycle_slots_private 00C7D9 RLA\n'
                   'Exports list by value:\n')
        self.assertIn('$c7e2', render(fixture))
        for bad in (fixture.replace('RLA', 'RLZ'), fixture.replace('00C7D9', '00F000')):
            with self.assertRaises(ValueError): render(bad)
        with self.assertRaises(KeyError): render(fixture.replace('_private', '_missing'))
        state = (ROOT/'src/kernel/task_state.c').read_text()
        self.assertIn('#define TASK_SLOT_STATE     1u', state)
        self.assertIn('#define TASK_SLOT_STRIDE    8u', state)

    def test_guard_precedes_launcher_and_argument_writes(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        foreground = source.split('task_load_foreground:', 1)[1].split('task_initialize:', 1)[0]
        self.assertLess(foreground.index('lda DISK_LOADER_CHILD_STATE'),
                        foreground.index('sta TASK_ARGV_LO'))
        busy = foreground.split('task_busy_return:', 1)[1].split('rts', 1)[0]
        self.assertIn('ldx #$01', busy)
        self.assertNotIn('sta TASK_', busy)

    def test_exact_read_close_and_validated_entry_contract(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        self.assertIn('cmp #$10\n        beq task_disk_overflow', source)
        self.assertIn('lda #9                      ; CLOSE, even on overflow/read failure', source)
        self.assertIn('sta DISK_REQUEST,x', source.split('task_disk_restore_request:', 1)[1])
        self.assertIn('sta task_call_entry+1', source)
        self.assertIn('sta task_call_entry+2', source)
        self.assertIn('cmp task_file_size_lo', source)
        self.assertIn('cmp task_file_size_hi', source)

    def test_split_output_is_a_declared_build_dependency(self):
        make = (ROOT/'Makefile').read_text()
        self.assertIn('$(STAGE1_GATEWAY_BIN) $(TASK_LOADER_BIN) $(TASK_LOOKUP_BIN) &:', make)
        self.assertIn('$(TASK_LOOKUP_BIN)', (ROOT/'mk/storage.mk').read_text())
        self.assertIn('start = $1A00, size = $0600', (ROOT/'cfg/8502-stage1-gateway.cfg').read_text())
        self.assertIn('start=$1200, size=$0800', (ROOT/'cfg/8502-storage.cfg').read_text())
