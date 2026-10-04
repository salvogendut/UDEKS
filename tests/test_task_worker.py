# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def surface(row):
    heights=(40,38,34,27,18,10,2,-4,-8,-9,-8,-5,-2,1,4,5,5,4,2,0,-2,-3,-4,-3,-2,0,1,2,3,3,2,1,-1,-2,-2)
    result=[]
    for col in range(25):
        high,low=sorted((abs(col-12)*5,abs(row-10)*6),reverse=True)
        radius=min(34,((high+(low>>2)+(low>>3))*2+2)//5)
        result.append(heights[radius]&255)
    return bytes(result)

class TaskWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); target=Path(cls.temp.name)/'worker.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-D__fastcall__=','-I'+str(ROOT/'include'),str(ROOT/'tests/fixtures/task_worker.c'),
            '-o',str(target)],check=True)
        cls.lib=c.CDLL(str(target)); cls.lib.test_request.restype=c.c_ubyte
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.lib.test_reset()
        self.r=(c.c_ubyte*38).in_dll(self.lib,'udeks_graphics_record')
        self.output=(c.c_ubyte*64).in_dll(self.lib,'udeks_worker_output')
        self.status=(c.c_ubyte*32).in_dll(self.lib,'udeks_worker_status')
        self.calls=c.c_uint.in_dll(self.lib,'test_calls')
    def request(self,payload,**fields):
        self.r[:]=b'UTRQ\0\x0b\x01\x18\x6d\0\x04'+bytes(27)
        self.r[14:18]=bytes(payload)
        for key,value in fields.items(): self.r[int(key)]=value
        result=self.lib.test_request()
        self.assertEqual(self.r[8],0x6d)
        self.assertEqual(self.r[11],0 if result else 3)
        self.assertEqual(self.r[6],0x80 if result else 2)
        self.assertEqual(c.c_ubyte.in_dll(self.lib,'test_busy').value,0)
        return result
    def test_boot_selftest_and_nop(self):
        self.assertEqual(bytes(self.status[:6]),b'ZWRK\x01\x02')
        self.assertEqual(self.status[11],0)
        self.assertEqual(self.request((0,0,0,0)),0)
        self.assertEqual(bytes(self.r[14:17]),bytes(3))
        self.assertEqual(bytes(self.output),b'\xa5'*64)
        self.assertEqual(self.calls.value,1)
    def test_rejected_envelope_never_leases_or_changes_output(self):
        for fields,error in (({'5':10},38),({'9':1},22),({'13':1},22),({'10':3},22),({'10':5},22)):
            with self.subTest(fields=fields): self.assertEqual(self.request((0,0,0,0),**fields),error)
        for payload,error in (((1,0,0,0),38),((0,1,0,0),22),((0,0,1,0),22),
                              ((0,0,0,1),22),((4,0,0,0),22),((4,0,0,65),22)):
            self.assertEqual(self.request(payload),error)
        self.assertEqual(self.calls.value,0)
        self.assertEqual(bytes(self.output),b'\xa5'*64)
    def test_worker_rejects_bad_operands_in_one_bounded_lease(self):
        for payload in ((5,21,1,25),(5,255,1,25),(5,20,2,50),(5,0,0,25),(5,0,3,25),(5,0,1,24)):
            before=self.calls.value
            self.assertEqual(self.request(payload),22)
            self.assertEqual(self.calls.value,before+1)
            self.assertEqual(bytes(self.output),b'\xa5'*64)
        self.assertEqual(self.status[5],2) # rejection does not poison readiness
        self.assertEqual(self.request((5,10,1,25)),0)
    def test_every_surface_row_and_two_row_bound(self):
        for row in range(21):
            self.assertEqual(self.request((5,row,1,25)),0)
            self.assertEqual(bytes(self.r[14:17]),bytes((row+1,0,25)))
            self.assertEqual(bytes(self.output[:25]),surface(row))
            self.assertEqual(bytes(self.output[25:]),b'\xa5'*39)
        self.assertEqual(self.request((5,19,2,50)),0)
        self.assertEqual(bytes(self.output[:50]),surface(19)+surface(20))
    def test_wave_64_wrap_and_private_copies(self):
        self.assertEqual(self.request((4,250,7,64)),0)
        first=bytes(self.output)
        self.assertEqual(bytes(self.r[14:17]),bytes(((250+7*64)&255,0,64)))
        self.assertEqual(self.request((4,0,0,64)),0)
        self.assertEqual(bytes(self.output),bytes(64))
        self.assertNotEqual(first,bytes(self.output)) # clients retain their own copy
    def test_offline_and_protocol_failures_are_io_errors(self):
        self.status[5]=0
        self.assertEqual(self.request((5,10,1,25)),5)
        self.assertEqual(self.calls.value,0)
        for fault in (1,2):
            self.lib.test_reset(); c.c_ubyte.in_dll(self.lib,'test_fault').value=fault
            self.assertEqual(self.request((5,10,1,25)),5)
    def test_sequence_and_transaction_counter_wrap(self):
        for _ in range(260): self.assertEqual(self.request((0,0,0,0)),0)
        self.assertEqual(int.from_bytes(bytes(self.status[12:14]),'little'),261)
        self.assertEqual(int.from_bytes(bytes(self.status[8:10]),'little'),261)

    def test_frozen_gate_and_shared_response_tails(self):
        source=(ROOT/'src/8502/syscall_gate.s').read_text()
        dispatch=source.split('task_extended_request:',1)[1].split('cmp #23',1)[0]
        self.assertIn('cmp #24',dispatch)
        self.assertIn('jsr _udeks_task_worker_request',dispatch)
        self.assertIn('jmp _udeks_bootfs_finish_error',dispatch)
        self.assertIn('lda #3\n        jmp _udeks_bootfs_finish_ok',dispatch)
        veneer=(ROOT/'user/lib/graphics_request.s').read_text()
        self.assertIn('.if UDEKS_GFX_ABI >= 11',veneer)
        self.assertIn('UDEKS_GFX_ABI = 9',veneer) # older apps are not upgraded implicitly
        self.assertIn('_udeks_worker_output = $f300',veneer)
        transport=(ROOT/'src/8502/z80_handoff.s').read_text()
        self.assertIn('inc _udeks_worker_status,x\n        bne :+\n        inc _udeks_worker_status+1,x',transport)

if __name__=='__main__': unittest.main()
