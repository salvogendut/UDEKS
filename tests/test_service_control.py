# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual resident queue with side-effect-counting host services."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <string.h>
#define UDEKS_SESSION_HOST_TEST
#include "src/services/shell/shell.c"
unsigned char session_memory[65536], active, clock_run, wave_run, calls, starts, app_result;
unsigned char udeks_shell_read_line(unsigned char *s, unsigned char n) { return UDEKS_LINE_EDITOR_EMPTY; }
unsigned char udeks_shell_tokenize(unsigned char *s, unsigned char *o, unsigned char n) { return 0; }
unsigned char udeks_stream_write(unsigned char fd, const unsigned char *s) { return 0; }
unsigned char udeks_stream_write_byte(unsigned char fd, unsigned char c) { return 0; }
unsigned char udeks_root_terminal_prompt(void) { return 0; }
void udeks_window_manager_reset(void) { ++calls; }
unsigned char udeks_vic_graphics_is_active(void) { return active; }
unsigned char udeks_vic_graphics_initialize(void) { ++calls; active=1; return 0; }
unsigned char udeks_vic_graphics_shutdown(void) { ++calls; active=0; return 0; }
unsigned char udeks_xclock_start(void) { ++calls; ++starts; if (!app_result) clock_run=1; return app_result; }
unsigned char udeks_xwave_start(void) { ++calls; ++starts; if (!app_result) wave_run=1; return app_result; }
unsigned char udeks_xclock_stop(void) { ++calls; clock_run=0; return 0; }
unsigned char udeks_xwave_stop(void) { ++calls; wave_run=0; return 0; }
unsigned char udeks_xclock_is_running(void) { return clock_run; }
unsigned char udeks_xwave_is_running(void) { return wave_run; }
unsigned char banked_run[2];
unsigned char udeks_banked_graphics_start(unsigned char i) { ++calls; ++starts; if (!app_result) banked_run[i]=1; return app_result; }
unsigned char udeks_banked_graphics_stop(unsigned char i) { ++calls; banked_run[i]=0; return 0; }
unsigned char udeks_banked_graphics_running(unsigned char i) { return banked_run[i]; }
unsigned char udeks_z80_submit(unsigned char op, unsigned int a, unsigned int b,
    unsigned int n, unsigned int *r) { ++calls; *r=0; return 0; }
void reset(void) {
    memset(session_memory, 0, sizeof(session_memory));
    active=clock_run=wave_run=banked_run[0]=banked_run[1]=calls=starts=app_result=0;
    udeks_shell_start(); session_memory[UDEKS_USH_STATUS_BASE+1]=UDEKS_USH_STATE_READY;
}
unsigned char valid(unsigned char t, unsigned char a, unsigned char b) { return udeks_control_valid(t,a,b); }
'''


class ServiceControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        source = Path(cls.temp.name)/'test.c'; library = source.with_suffix('.so')
        source.write_text(HARNESS)
        subprocess.run(['cc', '-shared', '-fPIC', '-O0', '-D__fastcall__=', '-Wno-unknown-pragmas',
            '-I', str(ROOT), '-I', str(ROOT/'include'), str(source), '-o', str(library)], check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.memory = (ctypes.c_ubyte*65536).in_dll(cls.lib, 'session_memory')

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.lib.reset()

    def value(self, name): return ctypes.c_ubyte.in_dll(self.lib, name).value

    def request(self, target=2, action=0, background=1, minor=7, descriptor=0, flags=0, count=3):
        record = b'UTRQ'+bytes((0, minor, 1, 20, 93, descriptor, count, 0, 0, flags, target, action, background))
        self.memory[0xf359:0xf359+len(record)] = record
        self.lib.udeks_service_control_request()
        self.assertEqual(self.memory[0xf361], 93)  # sequence preserved
        return self.memory[0xf365]

    def test_exact_operation_combinations(self):
        allowed = {(1,0,0),(1,1,0),(2,0,0),(2,0,1),(2,1,0),
                   (3,0,0),(3,0,1),(3,1,0),(4,2,0),(5,0,0),(5,0,1),(5,1,0),
                   (6,0,0),(6,0,1),(6,1,0)}
        for t in range(256):
            for a in range(4):
                for b in range(3):
                    self.assertEqual(bool(self.lib.valid(t,a,b)), (t,a,b) in allowed)
        for t in range(1,5):
            for v in range(3,256):
                self.assertFalse(self.lib.valid(t,v,0))
                self.assertFalse(self.lib.valid(t,0,v))

    def test_enqueue_has_no_graphics_or_engine_side_effects(self):
        self.assertEqual(self.request(), 0)
        self.assertEqual(self.value('calls'), 0)
        self.assertEqual(self.memory[0xf364], 1)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('starts'), 1)
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]), bytes((165,2,0,1,0)))
        self.assertEqual(self.memory[0xf185], 1)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('starts'), 1)

    def test_invalid_requests_leave_queue_and_reply_untouched(self):
        for options in ({'descriptor':1}, {'flags':1}, {'count':2}, {'count':4},
                        {'target':0}, {'target':7}, {'action':9}, {'background':2},
                        {'target':1, 'background':1}, {'action':1, 'background':1}):
            self.lib.reset()
            self.memory[0xf3a0:0xf3a5] = b'abcde'
            self.assertEqual(self.request(**options), 22)
            self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]), b'abcde')
            self.lib.udeks_shell_poll()
            self.assertEqual(self.value('calls'), 0)
        self.assertEqual(self.request(minor=6), 38)

    def test_busy_does_not_replace_pending_operation(self):
        self.assertEqual(self.request(), 0)
        self.assertEqual(self.request(target=3), 16)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('clock_run'), 1)
        self.assertEqual(self.value('wave_run'), 0)
        self.memory[0xf187] = 1
        self.assertEqual(self.request(target=4, action=2, background=0), 16)

    def test_foreground_interrupt_and_desktop_shutdown(self):
        self.assertEqual(self.request(background=0), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184], 1)
        self.assertEqual(self.request(target=3), 16)
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(), 1)
        self.assertEqual(self.memory[0xf3a4], 130)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184], 0)
        self.assertEqual(self.request(target=3), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.request(target=1, action=1, background=0), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('wave_run'), 0)
        self.assertEqual(self.value('active'), 0)

    def test_engine_runs_only_at_poll_boundary(self):
        self.assertEqual(self.request(target=4, action=2, background=0), 0)
        self.assertEqual(self.value('calls'), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('calls'), 1)
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]), bytes((165,4,2,0,0)))

    def test_four_jobs_and_targeted_banked_interrupt(self):
        banked = (ctypes.c_ubyte*2).in_dll(self.lib, 'banked_run')
        for target in (2,3,5,6):
            self.assertEqual(self.request(target=target), 0)
            self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf185], 4)
        self.assertEqual(list(banked), [1,1])
        self.assertEqual(self.request(target=6, action=1, background=0), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf185], 3)
        self.assertEqual(self.request(target=6, background=0), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184], 8)
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(), 1)
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]), bytes((165,6,1,0,130)))
        self.assertEqual(list(banked), [1,0])
        self.assertEqual((self.value('clock_run'),self.value('wave_run')), (1,1))
        self.lib.udeks_shell_poll()
        self.assertEqual(self.request(target=6), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.request(target=1, action=1, background=0), 0)
        self.lib.udeks_shell_poll()
        self.assertEqual(list(banked), [0,0])
        self.assertEqual(self.memory[0xf185], 0)

    def test_managed_errors_are_preserved_without_claiming_a_running_job(self):
        for target in (2, 3, 5, 6):
            for error in range(1, 7):
                self.lib.reset()
                ctypes.c_ubyte.in_dll(self.lib, 'app_result').value = error
                self.assertEqual(self.request(target=target, background=0), 0)
                self.lib.udeks_shell_poll()
                self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]), bytes((165,target,0,0,error)))
                self.assertEqual(self.memory[0xf184], 0)
                self.assertEqual(self.memory[0xf185], 0)

    def test_assembly_wrapper_clears_scheduler_suspend_flag(self):
        text = (ROOT/'src/8502/syscall_gate.s').read_text()
        wrapper = text.split('task_extended_request:')[1].split('task_exec_pending:')[0]
        self.assertIn('jsr _udeks_service_control_request', wrapper)
        self.assertIn('clc\n        rts', wrapper)
        self.assertNotIn('jmp _udeks_service_control_request', wrapper)


if __name__ == '__main__': unittest.main()
