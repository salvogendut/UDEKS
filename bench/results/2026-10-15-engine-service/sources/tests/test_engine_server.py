# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class EngineServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();so=Path(cls.tmp.name)/'server.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-DUDEKS_Z80_WORKER_HOST_TEST','-Iinclude','-Iuser/include',
            'tests/fixtures/engine_server.c','src/z80/worker.c','-o',str(so)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(so));cls.lib.engine_test_run.argtypes=[c.c_uint8];cls.lib.engine_test_run.restype=c.c_uint8
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def value(self,name):return c.c_uint.in_dll(self.lib,name).value
    def replies(self):
        lengths=(c.c_uint8*16).in_dll(self.lib,'engine_test_lengths');data=((c.c_uint8*16)*16).in_dll(self.lib,'engine_test_replies')
        return [bytes(data[i][:lengths[i]]) for i in range(self.value('engine_test_reply_count'))]
    def test_real_worker_results_and_snapshot_before_output_is_borrowed_again(self):
        self.assertEqual(self.lib.engine_test_run(0),0);replies=self.replies()
        self.assertEqual(replies[1],bytes((1,2,2,0,0,50,0,8,250,0,6,9,14,19,23,25)))
        self.assertEqual(self.value('engine_test_worker_calls'),3);self.assertEqual(self.value('engine_server_jobs'),3)
        self.assertEqual(self.value('engine_test_closes'),1)
    def test_malformed_stop_never_arms_shutdown_or_executes_worker(self):
        self.assertEqual(self.lib.engine_test_run(0),0);replies=self.replies()
        self.assertEqual([r[4] for r in replies],[0,0,22,22,0,71,38,0])
        for r in replies:
            if r[4]:self.assertEqual(r[5:],b'\0\0\0')
        self.assertEqual(replies[4][2],5)
    def test_ack_checks_source_sequence_and_reserved_operands(self):
        self.assertEqual(self.lib.engine_test_run(0),0)
        self.assertEqual(self.value('engine_test_sleeps'),3)
        self.assertEqual(c.c_uint8.in_dll(self.lib,'engine_server_state').value,4)
    def test_missing_ack_is_bounded_even_under_junk_traffic_and_recovers(self):
        self.assertEqual(self.lib.engine_test_run(1),0);self.assertEqual(self.value('engine_test_sleeps'),600)
        self.assertEqual(self.replies()[-1][2],99);self.assertEqual(self.value('engine_test_closes'),1)
    def test_retired_peer_and_full_mailbox_leave_service_available(self):
        self.assertEqual(self.lib.engine_test_run(2),0);self.assertEqual(self.value('engine_test_worker_calls'),3)
        self.assertEqual(self.lib.engine_test_run(3),0);self.assertEqual(self.value('engine_test_sleeps'),5)
        self.assertEqual(self.replies()[1][8:],bytes((250,0,6,9,14,19,23,25)))
