# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_repaint_latency import measurements, source


def sample():
    return '\n'.join(f'repaint service: case={case} service={service} calls=2 retries=1 '
        'max_call=200 max_gap=400 span=1000' for case in (*range(16), 100, 101)
        for service in ('manager', 'keyboard')) + '\n' + \
        'PASS: native clock-only/overlap drag-start timing and shutdown\n'


class WindowRepaintLatencyTests(unittest.TestCase):
    def test_decoder_requires_all_moves_and_both_clock_cases(self):
        data = measurements(sample())
        self.assertEqual(len(data), 36)
        self.assertEqual(data[-1]['case'], 101)
        self.assertEqual(data[0]['max_gap_bus_cycles'], 400)
        with self.assertRaises(ValueError): measurements('\n'.join(sample().splitlines()[1:]))
        with self.assertRaises(ValueError): measurements(sample().replace('case=100', 'case=102'))

    def test_rejects_duplicate_zero_calls_bad_durations_and_missing_shutdown(self):
        for invalid in (sample() + sample().splitlines()[0], sample().replace('calls=2', 'calls=0'),
                        sample().replace('max_call=200', 'max_call=1001'),
                        sample().replace('max_gap=400', 'max_gap=0'),
                        sample().replace('PASS:', 'INCOMPLETE:')):
            with self.assertRaises(ValueError): measurements(invalid)

    def test_rejects_mismatched_observation_windows(self):
        log = sample().replace('service=keyboard calls=2 retries=1 max_call=200 max_gap=400 span=1000',
                               'service=keyboard calls=2 retries=1 max_call=200 max_gap=400 span=999', 1)
        with self.assertRaises(ValueError): measurements(log)

    def test_actual_source_seams_and_link_derived_entries(self):
        native = (ROOT / 'bench/results/2026-09-29-window-cache-integration/native.c').read_text()
        code = source(native, {'_udeks_window_manager_poll': (0x1234, 'RLA'),
                               '_udeks_keyboard_poll': (0x5678, 'RLA')})
        self.assertIn('#define REPAINT_MANAGER_PC 0x1234u', code)
        self.assertIn('#define REPAINT_KEYBOARD_PC 0x5678u', code)
        for case in ('100', '101', 'i'):
            self.assertEqual(code.count(f'repaint_begin({case});'), 1)
            self.assertEqual(code.count(f'repaint_finish({case});'), 1)
        self.assertIn('clock drag-start exceeded 30 frames', code)
        self.assertIn('overlap clock drag-start exceeded 30 frames', code)
        self.assertLess(code.index('repaint_finish(101);'), code.index('"clock drag left shadow/VIC disagreement"'))
        symbols = {'_udeks_window_manager_poll': (0x1234, 'RLA'), '_udeks_keyboard_poll': (0x5678, 'RLA')}
        with self.assertRaises(ValueError): source(native.replace('static void profile_stop(void) {', 'changed'), symbols)

    def test_observer_resumes_partial_frames_and_preserves_irq_return_accounting(self):
        code = (ROOT / 'bench/window-cache-manager/repaint-latency.inc').read_text()
        self.assertIn('machine->bus_cycles-w->started', code)
        self.assertIn('w->sp==machine->cpu.sp', code)
        self.assertIn('w->return_pc==caller', code)
        self.assertIn('machine->cpu.sp!=((w->sp+2)&255)', code)
        self.assertIn('repaint_watches[1-i].return_id!=id', code)
        self.assertNotRegex(code, r'(?:c128_debug_mem_write|machine->mem.ram\[.*?\]\s*=)')
        native = (ROOT / 'bench/results/2026-09-29-window-cache-integration/native.c').read_text()
        self.assertIn('while((unsigned)c128_frame_count==before)', native)


if __name__ == '__main__':
    unittest.main()
