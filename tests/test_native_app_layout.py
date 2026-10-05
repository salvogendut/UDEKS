# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_app_layout import ALLOCATIONS,ADMISSION_ORDER,check_assembly_layout,check_linked_tables


class NativeAllocationLayout(unittest.TestCase):
    def test_all_four_tables_agree_with_loader_and_initializer(self):
        text=(ROOT/'src/services/app/native_layout.inc').read_text()
        check_assembly_layout(text)
        for before,after in (('NATIVE_CLIENTS = 4','NATIVE_CLIENTS = 2'),
                             ('$23,$35,$80,$c6','$23,$35,$81,$c6'),
                             ('$34,$3f,$8f,$cf','$34,$3f,$90,$cf'),
                             ('$d5,$d7,$d0,$00','$d5,$d7,$d1,$00'),
                             ('$d6,$d8,$e2,$01','$d6,$d8,$e3,$01')):
            with self.assertRaises(ValueError): check_assembly_layout(text.replace(before,after))
        for task,base,limit,stack,zp,hp in ALLOCATIONS:
            self.assertEqual(limit-stack,256)
            self.assertLess(base,stack)
            self.assertNotEqual(zp,hp)
        self.assertEqual(ADMISSION_ORDER,tuple(row[0] for row in sorted(ALLOCATIONS,key=lambda r:r[2]-r[1])))
        source=(ROOT/'src/services/app/banked_loader.s').read_text()
        self.assertIn('auto_order: .byte '+','.join(map(str,ADMISSION_ORDER)),source)

    def test_actual_linked_tables_must_agree_not_just_source(self):
        exports={'_udeks_native_base_pages':(0xe310,'RLA'),'_udeks_native_stack_pages':(0xe314,'RLA')}
        blob=bytes(16)+bytes(row[1]>>8 for row in ALLOCATIONS)+bytes(row[3]>>8 for row in ALLOCATIONS)
        check_linked_tables(blob,exports)
        for bad in (blob[:-1],blob[:-1]+b'\0',bytes(len(blob))):
            with self.assertRaises(ValueError): check_linked_tables(bad,exports)
        with self.assertRaises(ValueError):
            check_linked_tables(blob,exports|{'_udeks_native_base_pages':(0xe310,'RLZ')})

    def test_private_page_initialization_preserves_cpu_port_and_kernel_stack(self):
        source=(ROOT/'src/services/window/banked_access.s').read_text()
        body=source.split('_udeks_banked_pages_init:',1)[1].split('.segment "MODULERODATA"',1)[0]
        self.assertIn('ldy #2\n        lda #0',body)
        self.assertIn('sta $02',body)
        self.assertIn('sta $03',body)
        self.assertIn('sta $01fe',body)
        self.assertIn('sta $01ff',body)
        self.assertNotIn('jsr ',body)
        self.assertNotIn('pha',body)
        self.assertNotIn('pla',body)
        self.assertIn('sta $d508\n        sta $d507\n        sta $d50a\n        lda #1\n        sta $d509\n        rts',body)

    def test_delivery_completes_before_any_native_allocation_is_published(self):
        text=(ROOT/'src/services/window/banked_graphics.c').read_text()
        launch=text.split('unsigned char udeks_banked_graphics_launch(void)',1)[1]
        self.assertLess(launch.index('complete_install();'),launch.index('udeks_banked_call(0)'))
        self.assertLess(launch.index('udeks_banked_graphics_installed=1;'),launch.index('udeks_banked_call(0)'))
        self.assertIn('if(!udeks_banked_graphics_installed)',launch)
        shell=(ROOT/'src/services/shell/shell.c').read_text()
        service=(ROOT/'src/services/app/managed_apps.s').read_text()
        for name in ('xclock','xwave','xcalc','xdraw'):
            self.assertNotIn(name,shell.lower())
            self.assertNotIn(name,service.lower())
