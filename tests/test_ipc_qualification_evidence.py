# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind IPC qualification claims to preserved disks, programs and raw captures."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from o65_to_udex import relocate_executable
RESULTS=ROOT/'bench/results/2026-10-11-ipc-qualification'
APPS=ROOT/'bench/artifacts/2026-10-11-ipc-examples'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def raw(path):return path.read_bytes()[2:]

class IpcQualificationEvidence(unittest.TestCase):
    def test_native_engine_provenance_and_machine_captures(self):
        work=RESULTS/'native-1986-d81'
        report=json.loads((work/'report.json').read_text())
        provenance=json.loads((work/'provenance.json').read_text())
        revision='d360c114e33216bf38a086f65af27533f581f6ba'
        self.assertEqual(report['revision'],revision)
        self.assertEqual(provenance['emulator_revision'],revision)
        self.assertFalse(report['flatpak_qualified'])
        self.assertFalse(report['physical_c128'])
        self.assertEqual(report['disk_sha256'],digest(APPS/'udeks-ipc.d81'))
        self.assertEqual(provenance['disk_sha256'],report['disk_sha256'])
        log=(work/'run.log').read_text()
        self.assertIn('PASS native 1986 IPC:',log)
        self.assertEqual(log.count('PASS reply: restart'),3)
        self.assertIn('PASS reply: 1234567890abcde',log)
        self.assertIn('PASS reply: recovered',log)
        self.assertEqual((work/'reply.bin').read_bytes()[:9],b'\x02GRAPHICS')
        pool=(work/'ipc-final.bin').read_bytes()
        self.assertEqual(pool[:2],b'\0\0')
        self.assertEqual(pool[6:8],b'\0\0')
        for name,base,limit in [('client',0x2300,0x3500),('server',0x8000,0x9000)]:
            image=APPS/('IPCPING.BIN' if name=='client' else 'IPCSRV.BIN')
            self.assertEqual((work/f'{name}-code.bin').read_bytes(),relocate_executable(image.read_bytes(),base,limit-base)[16:])
        for name,expected in provenance['harness_sha256'].items():
            self.assertEqual(digest(RESULTS/'native-sources'/name),expected)

    def test_every_preserved_file_is_bound_and_checksums_match(self):
        entries={}
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1);entries[name]=expected
            self.assertEqual(digest(RESULTS/name),expected,name)
        files={str(path.relative_to(RESULTS)) for path in RESULTS.rglob('*') if path.is_file() and path.name!='SHA256SUMS'}
        self.assertEqual(set(entries),files)
        self.assertFalse(any(path.suffix=='.vsf' for path in RESULTS.rglob('*')))
    def test_actual_public_peer_retirement_and_restart_evidence(self):
        for fmt in ('d71','d81'):
            with self.subTest(format=fmt):
                work=RESULTS/f'vice-{fmt}-both-peers';report=json.loads((work/'report.json').read_text())
                self.assertEqual(report['disk_sha256'],digest(work/('test.'+fmt)))
                self.assertEqual(report['base_disk_sha256'],digest(APPS/('udeks-ipc.'+fmt)))
                self.assertTrue(report['server_cancel']);self.assertTrue(report['lifecycle'])
                self.assertEqual(report['programs']['client'],digest(APPS/'IPCPING.BIN'))
                self.assertEqual(report['programs']['server'],digest(APPS/'IPCSRV.BIN'))
                self.assertEqual(report['programs']['orphan'],digest(RESULTS/'waiting-peer/WAITPING.BIN'))
                events=report['records']
                self.assertTrue(any(x.get('check')=='cancel-client-during-request' and x['recovered'] for x in events))
                self.assertTrue(any(x.get('check')=='cancel-server-during-request' and x['client_errno']==11 and x['stale_send_errno']==9 for x in events))
                interrupts=[x for x in events if x.get('input_queued_while_request_pending')]
                self.assertEqual(len(interrupts),2)
                self.assertTrue(all(x['exit_status']==130 for x in interrupts))
                cycles=[x for x in events if x.get('check')=='restart-cycle']
                self.assertEqual(len(cycles),12)
                handles=[x['server_handle'] for x in cycles];self.assertEqual(handles,sorted(set(handles)))
                pool=raw(work/'ipc-pool.bin');self.assertEqual(pool[:2],b'\0\0');self.assertEqual(pool[6:8],b'\0\0')
                self.assertEqual(raw(work/'orphan-stale5.bin'),b'\x09')
                self.assertEqual(raw(work/'orphan-error5.bin'),b'\x0b')
                for app,name,base,limit in [('client','IPCPING',0x2300,0x3500),('server','IPCSRV',0x8000,0x9000),('orphan','WAITPING',0x8000,0x9000)]:
                    image=(RESULTS/'waiting-peer'/f'{name}.BIN') if app=='orphan' else APPS/f'{name}.BIN'
                    self.assertEqual(raw(work/f'{app}-code.bin'),relocate_executable(image.read_bytes(),base,limit-base)[16:])
                    for offset in (0,176):self.assertEqual(raw(work/f'{app}-guard{offset}.bin'),b'\xa5'*16)
    def test_raw_boundary_cases_and_guarded_disk_programs(self):
        expected={'duplicate names','overlong name','unknown operation','endpoint pool full','invalid receive capacity','foreign access','16 exact copied bytes','full/empty/short receive','stale handle','sender EXIT purges peer queue','normal EXIT','foreground CANCEL','reuse','clock/drawing coexistence','graphics stopped'}
        image=RESULTS/'raw-fixture/IPCTEST.BIN'
        for fmt in ('d71','d81'):
            with self.subTest(format=fmt):
                work=RESULTS/f'vice-boundary-{fmt}';report=json.loads((work/'result.json').read_text())
                self.assertEqual(set(report['checks']),expected)
                self.assertEqual(report['disk_sha256'],digest(work/('test.'+fmt)))
                self.assertEqual(report['fixture_sha256'],digest(image))
                for task,base,limit in ((3,0x2300,0x3500),(5,0x8000,0x9000)):
                    self.assertEqual(raw(work/f'installed{task}.bin'),relocate_executable(image.read_bytes(),base,limit-base)[16:])
                    self.assertEqual(raw(work/f'failure{task}.bin'),b'\0')
                    for offset in (0,176):self.assertEqual(raw(work/f'guard{task}{offset}.bin'),b'\xa5'*16)
