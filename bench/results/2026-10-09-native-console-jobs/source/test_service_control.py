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
#define udeks_shell_tokenize real_tokenize
#include "user/lib/shell_parser.c"
#undef udeks_shell_tokenize
unsigned char session_memory[65536], active, clock_run, wave_run, calls, starts, app_result;
unsigned char token_count, init_error, native_argc_seen;
unsigned char load_error, load_exit, loads, loaded_count;
unsigned char session_load(unsigned char count, unsigned char **args) {
    ++loads; loaded_count=count;
    session_memory[UDEKS_TASK_STATUS_BASE+UDEKS_TASK_ERROR_OFFSET]=load_error;
    session_memory[UDEKS_TASK_STATUS_BASE+UDEKS_TASK_EXIT_OFFSET]=load_exit;
    return 0;
}
char last_name[17], output[256];
unsigned char udeks_shell_read_line(unsigned char *s, unsigned char n) { return UDEKS_LINE_EDITOR_EMPTY; }
unsigned char udeks_shell_tokenize(unsigned char *s, unsigned char *o, unsigned char n) {
    return token_count==255 ? 255 : real_tokenize(s,o,n);
}
unsigned char udeks_stream_write(unsigned char fd, const unsigned char *s) { strncat(output,(const char *)s,255-strlen(output)); return 0; }
unsigned char udeks_stream_write_byte(unsigned char fd, unsigned char c) { return 0; }
unsigned char udeks_root_terminal_prompt(void) { return 0; }
void udeks_window_manager_reset(void) { ++calls; }
unsigned char udeks_vic_graphics_is_active(void) { return active; }
unsigned char udeks_vic_graphics_initialize(void) { ++calls; if(!init_error) active=1; return init_error; }
unsigned char udeks_vic_graphics_shutdown(void) { ++calls; active=0; return 0; }
unsigned char udeks_xclock_start(void) { ++calls; ++starts; if (!app_result) clock_run=1; return app_result; }
unsigned char udeks_xwave_start(void) { ++calls; ++starts; if (!app_result) wave_run=1; return app_result; }
unsigned char udeks_xclock_stop(void) { ++calls; clock_run=0; return 0; }
unsigned char udeks_xwave_stop(void) { ++calls; wave_run=0; return 0; }
unsigned char udeks_xclock_is_running(void) { return clock_run; }
unsigned char udeks_xwave_is_running(void) { return wave_run; }
unsigned char banked_run[4];
unsigned char udeks_banked_graphics_selected;
char native_argv_seen[8][55];
unsigned char udeks_banked_graphics_exec(const unsigned char *name) {
    unsigned char i;
    native_argc_seen=udeks_shell_native_argc;
    for(i=0;i<native_argc_seen;++i) strcpy(native_argv_seen[i], (char *)arguments[i]);
    ++calls; ++starts; strncpy(last_name,(const char *)name,16);
    if(app_result) return app_result;
    for(udeks_banked_graphics_selected=0;udeks_banked_graphics_selected<4;++udeks_banked_graphics_selected)
        if(!banked_run[udeks_banked_graphics_selected]) break;
    if(udeks_banked_graphics_selected==4) return 4;
    banked_run[udeks_banked_graphics_selected]=1; return 0;
}
unsigned char udeks_banked_graphics_start(unsigned char i) { ++calls; ++starts; if (!app_result) banked_run[i]=1; return app_result; }
unsigned char udeks_banked_graphics_stop(unsigned char i) { ++calls; banked_run[i]=0; return 0; }
unsigned char udeks_banked_graphics_stop_name(const unsigned char *name) { return udeks_banked_graphics_stop(0); }
unsigned char udeks_banked_graphics_running(unsigned char i) { return banked_run[i]; }
unsigned char udeks_z80_submit(unsigned char op, unsigned int a, unsigned int b,
    unsigned int n, unsigned int *r) { ++calls; *r=0; return 0; }
void reset(void) {
    memset(session_memory, 0, sizeof(session_memory));
    memset(banked_run,0,sizeof(banked_run));
    active=clock_run=wave_run=calls=starts=app_result=0;
    token_count=init_error=load_error=load_exit=loads=loaded_count=native_argc_seen=0;
    memset(last_name,0,sizeof(last_name)); output[0]=0;
    memset(native_argv_seen,0,sizeof(native_argv_seen));
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

    def request(self, target=1, action=0, background=0, minor=7, descriptor=0, flags=0, count=3):
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

    def test_unknown_background_names_select_instances_without_foreground(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=2
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        for name in (b'orbit', b'canvas', b'third', b'fourth'):
            data=name+b' &\0'; line[:len(data)]=data
            self.lib.udeks_shell_dispatch_line()
            self.assertEqual(bytes((ctypes.c_char*17).in_dll(self.lib,'last_name')).split(b'\0')[0],name)
            self.assertEqual(self.memory[0xf184],0)  # no foreground job
        line[:8]=b'extra &\0'
        self.lib.udeks_shell_dispatch_line()
        self.assertIn(b'task slot busy',bytes((ctypes.c_char*256).in_dll(self.lib,'output')))
        self.assertEqual(bytes((ctypes.c_ubyte*4).in_dll(self.lib,'banked_run')),b'\1\1\1\1')

    def test_generic_launch_does_not_initialize_desktop(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=2
        ctypes.c_ubyte.in_dll(self.lib,'init_error').value=1
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        line[:8]=b'orbit &\0'
        self.lib.udeks_shell_dispatch_line()
        self.assertEqual(self.value('starts'),1)
        self.assertEqual(self.value('active'),0)

    def test_fixed_console_arguments_and_exit_do_not_enter_native_loader(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=2
        ctypes.c_ubyte.in_dll(self.lib,'load_exit').value=37
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        line[:11]=b'args alpha\0'
        self.lib.udeks_shell_dispatch_line()
        self.assertEqual(self.value('loaded_count'),2)
        self.assertEqual(self.value('starts'),0)
        self.assertEqual(self.memory[0xf17a],37)
        self.assertEqual(self.value('active'),0)

    def test_minor2_foreground_fallback_and_targeted_interrupt(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=1
        ctypes.c_ubyte.in_dll(self.lib,'load_error').value=5
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        line[:6]=b'orbit\0'
        self.lib.udeks_shell_dispatch_line()
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184],1)
        self.assertEqual(self.value('active'),0)
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),1)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184],1) # parent has not cancelled/reaped yet
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),bytes((165,3,3,0,0)))
        (ctypes.c_ubyte*4).in_dll(self.lib,'banked_run')[0]=0
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184],0)

    def test_other_loader_errors_do_not_fall_back(self):
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        for error,count in ((11,1),(3,1),(4,1),(11,2),(3,2)):
            self.lib.reset()
            ctypes.c_ubyte.in_dll(self.lib,'token_count').value=count
            ctypes.c_ubyte.in_dll(self.lib,'load_error').value=error
            line[:10]=b'orbit arg\0'
            self.lib.udeks_shell_dispatch_line()
            self.assertEqual(self.value('starts'),0)

    def test_native_arguments_are_published_only_during_serialized_load(self):
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        for error in (5,9):
            self.lib.reset()
            ctypes.c_ubyte.in_dll(self.lib,'token_count').value=2
            ctypes.c_ubyte.in_dll(self.lib,'load_error').value=error
            line[:10]=b'orbit arg\0'
            self.lib.udeks_shell_dispatch_line()
            self.assertEqual(self.value('native_argc_seen'),2)
            self.assertEqual(self.value('udeks_shell_native_argc'),0)
            self.assertEqual(self.value('starts'),1)

    def test_native_image_larger_than_legacy_staging_uses_native_validation(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=1
        ctypes.c_ubyte.in_dll(self.lib,'load_error').value=9
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        line[:6]=b'orbit\0'
        self.lib.udeks_shell_dispatch_line()
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('starts'),1)
        self.assertEqual(self.memory[0xf184],1)
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),1)

    def test_enqueue_has_no_graphics_or_engine_side_effects(self):
        self.assertEqual(self.request(),0)
        self.assertEqual(self.value('calls'),0)
        self.assertEqual(self.memory[0xf364],1)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('calls'),1)
        self.assertEqual(self.value('active'),1)
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),bytes((165,1,0,0,0)))
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('calls'),1)

    def test_invalid_requests_leave_queue_and_reply_untouched(self):
        for options in ({'descriptor':1},{'flags':1},{'count':2},{'count':4},
                        {'action':9},{'background':2},{'background':1}):
            self.lib.reset()
            self.memory[0xf3a0:0xf3a5]=b'abcde'
            self.assertEqual(self.request(**options),22)
            self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),b'abcde')
            self.lib.udeks_shell_poll()
            self.assertEqual(self.value('calls'),0)
        self.assertEqual(self.request(minor=6),38)
        for target in (0,2,3,5,6,7,255):
            self.assertEqual(self.request(target=target),38)
            self.assertEqual(self.value('starts'),0)

    def test_busy_does_not_replace_pending_operation(self):
        self.assertEqual(self.request(),0)
        self.assertEqual(self.request(target=4,action=2),16)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('active'),1)
        self.memory[0xf187]=1
        self.assertEqual(self.request(target=4,action=2),16)

    def launch(self,name,background=True):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=2 if background else 1
        ctypes.c_ubyte.in_dll(self.lib,'load_error').value=5
        line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
        data=name+(b' &' if background else b'')+b'\0'
        line[:len(data)]=data
        self.lib.udeks_shell_dispatch_line()
        self.lib.udeks_shell_poll()

    def test_excess_arguments_do_not_reach_either_loader(self):
        ctypes.c_ubyte.in_dll(self.lib,'token_count').value=255
        self.lib.udeks_shell_dispatch_line()
        for name in ('calls','starts','loads','native_argc_seen','udeks_shell_native_argc'):
            self.assertEqual(self.value(name),0,name)
        self.assertEqual(self.memory[0xf17a],2)
        self.assertEqual(list((ctypes.c_ubyte*4).in_dll(self.lib,'banked_run')),[0]*4)

    def test_background_arguments_strip_only_final_standalone_operator(self):
        for command,expected in (
            (b'orbit a B c &', [b'orbit',b'a',b'B',b'c']),
            (b'  orbit\ta\t& \t', [b'orbit',b'a']),
            (b'orbit a b c d e f g &', [b'orbit',b'a',b'b',b'c',b'd',b'e',b'f',b'g']),
            (b'orbit a& & b &', [b'orbit',b'a&',b'&',b'b']),
        ):
            self.lib.reset()
            ctypes.c_ubyte.in_dll(self.lib,'load_exit').value=37
            self.memory[0xf287]=37 # stale fixed-loader exit must not be reused
            line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
            line[:len(command)+1]=command+b'\0'
            self.lib.udeks_shell_dispatch_line(); self.lib.udeks_shell_poll()
            self.assertEqual(self.value('loads'),0)
            self.assertEqual(self.value('native_argc_seen'),len(expected))
            args=(ctypes.c_char*55*8).in_dll(self.lib,'native_argv_seen')
            self.assertEqual([bytes(a).split(b'\0')[0] for a in args[:len(expected)]],expected)
            self.assertEqual((self.memory[0xf184],self.memory[0xf185],self.memory[0xf17a]),(0,1,0))

    def test_nonfinal_or_embedded_ampersand_is_not_a_background_operator(self):
        for command in (b'orbit a&',b'orbit & argument'):
            self.lib.reset()
            line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
            line[:len(command)+1]=command+b'\0'
            self.lib.udeks_shell_dispatch_line()
            self.assertEqual(self.value('loads'),1)
            self.assertEqual(self.value('starts'),0)

    def test_background_parse_errors_have_no_launch_side_effects(self):
        for command in (b'&',b' \t&  ',b'orbit a b c d e f g h &',b'orbit a b c d e f g h'):
            self.lib.reset()
            line=(ctypes.c_ubyte*55).in_dll(self.lib,'udeks_shell_command_line')
            line[:len(command)+1]=command+b'\0'
            self.lib.udeks_shell_dispatch_line()
            self.assertEqual(self.memory[0xf17a],2)
            self.assertEqual((self.value('loads'),self.value('starts')),(0,0))

    def test_four_jobs_targeted_interrupt_and_desktop_shutdown(self):
        banked=(ctypes.c_ubyte*4).in_dll(self.lib,'banked_run')
        for name in (b'one',b'two',b'three'): self.launch(name)
        self.launch(b'four',False)
        self.assertEqual(self.memory[0xf185],3)
        self.assertEqual(self.memory[0xf184],8)
        self.assertEqual(list(banked),[1,1,1,1])
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),1)
        self.assertEqual(list(banked),[1,1,1,1])
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),bytes((165,6,3,0,0)))
        banked[3]=0 # normal poll observes scheduler cancellation and reaps
        self.lib.udeks_shell_poll()
        self.assertEqual(self.memory[0xf184],0)
        self.launch(b'reused')
        self.assertEqual(self.memory[0xf185],4)
        self.assertEqual(self.request(action=1),0)
        self.lib.udeks_shell_poll()
        self.assertEqual(list(banked),[0,0,0,0])
        self.assertEqual(self.memory[0xf185],0)

    def test_interrupt_notice_targets_each_slot_without_stopping_any_peer(self):
        for foreground in range(4):
            self.lib.reset()
            for i in range(foreground): self.launch(b'peer')
            self.launch(b'front',False)
            banked=(ctypes.c_ubyte*4).in_dll(self.lib,'banked_run')
            before=list(banked); calls=self.value('calls')
            for _ in range(2):
                self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),1)
                self.assertEqual(list(banked),before)
                self.assertEqual(self.value('calls'),calls)
                self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),bytes((165,foreground+3,3,0,0)))
                self.assertEqual(self.memory[0xf184],1<<foreground)
            self.assertEqual(self.memory[0xf186],2)

    def test_no_interrupt_notice_at_prompt_or_without_native_shell(self):
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),0)
        self.launch(b'front',False)
        self.memory[0xf3d9]=0
        before=bytes(self.memory)
        self.assertEqual(self.lib.udeks_shell_interrupt_foreground(),0)
        self.assertEqual(bytes(self.memory),before)

    def test_engine_runs_only_at_poll_boundary(self):
        self.assertEqual(self.request(target=4,action=2),0)
        self.assertEqual(self.value('calls'),0)
        self.lib.udeks_shell_poll()
        self.assertEqual(self.value('calls'),1)
        self.assertEqual(bytes(self.memory[0xf3a0:0xf3a5]),bytes((165,4,2,0,0)))

    def test_launch_errors_do_not_claim_jobs(self):
        for error in range(1,7):
            self.lib.reset()
            ctypes.c_ubyte.in_dll(self.lib,'app_result').value=error
            self.launch(b'unknown')
            self.assertEqual(self.memory[0xf184],0)
            self.assertEqual(self.memory[0xf185],0)

    def test_assembly_wrapper_clears_scheduler_suspend_flag(self):
        text = (ROOT/'src/8502/syscall_gate.s').read_text()
        wrapper = text.split('task_extended_request:')[1].split('task_exec_pending:')[0]
        self.assertIn('jsr _udeks_service_control_request', wrapper)
        self.assertIn('clc\n        rts', wrapper)
        self.assertNotIn('jmp _udeks_service_control_request', wrapper)


if __name__ == '__main__': unittest.main()
