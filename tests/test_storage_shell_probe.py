# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from storage_shell_probe import keyboard_queue_address, type_command

MAP = '''keyboard.o:
    BSS               Offs=00007F  Size=000047  Align=00001  Fill=0000
Segment list:
BSS                   009F28  00A1DF  0002B8  00001
'''
ASSEMBLY = '''.segment "BSS"
_event_queue: .res 64,$00
_queue_head: .res 1,$00
_queue_tail: .res 1,$00
_queue_count: .res 1,$00
'''


class StorageShellProbe(unittest.TestCase):
    def test_queue_resolution_and_fail_closed_layout(self):
        self.assertEqual(keyboard_queue_address(MAP, ASSEMBLY), 0x9FA7)
        for text, asm in ((MAP.replace('keyboard.o', 'other.o'), ASSEMBLY),
                          (MAP.replace('000047', '000048'), ASSEMBLY),
                          (MAP, ASSEMBLY.replace('64,$00', '32,$00'))):
            with self.assertRaises(ValueError):
                keyboard_queue_address(text, asm)

    def test_commands_use_terminal_return_event_without_cpu_takeover(self):
        with patch('storage_shell_probe.sp.wait_for_byte') as wait, \
             patch('storage_shell_probe.sp.write_kernel_blocks') as write:
            type_command(1234, 0x9FA7, 'mount 8 /mnt', 20)
        wait.assert_called_once_with(1234, 0x9FE9, 0, 20)
        port, writes = write.call_args.args
        self.assertEqual(port, 1234)
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0][0], 0x9FA7)
        events = writes[0][1]
        self.assertEqual(events[2::4], b'mount 8 /mnt\n')
        self.assertEqual(events[-4:], bytes((1, 1, 10, 0)))
        self.assertEqual(writes[1], (0x9FE7, bytes((13, 0, 13))))

    def test_queue_capacity_includes_return_and_wraps_head(self):
        with patch('storage_shell_probe.sp.wait_for_byte'), \
             patch('storage_shell_probe.sp.write_kernel_blocks') as write:
            type_command(1234, 0x9000, 'x'*15, 20)
            self.assertEqual(write.call_args.args[1][-1], (0x9040, bytes((0, 0, 16))))
            with self.assertRaises(ValueError):
                type_command(1234, 0x9000, 'x'*16, 20)
            self.assertEqual(write.call_count, 1)
