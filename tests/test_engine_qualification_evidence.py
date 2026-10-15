# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind slice-3 qualification claims to preserved programs and machine bytes."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from o65_to_udex import relocate_executable

RESULTS=ROOT/'bench/results/2026-10-15-engine-qualification'
APPS=ROOT/'bench/artifacts/2026-10-15-engine-demo'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def raw(path):return path.read_bytes()[2:]

class EngineQualificationEvidence(unittest.TestCase):
    def test_archive_is_bound_and_excludes_private_snapshots(self):
        entries={}
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1)
            self.assertEqual(digest(RESULTS/name),expected,name)
            entries[name]=expected
        self.assertEqual(set(entries),{str(p.relative_to(RESULTS)) for p in RESULTS.rglob('*') if p.is_file() and p.name!='SHA256SUMS'})
        self.assertFalse(list(RESULTS.rglob('*.vsf')))

    def test_vice_both_peers_bounds_restart_soak_and_guards(self):
        for fmt in ('d71','d81'):
            for suffix,cycles in [('soak',12),('cancel',1)]:
                work=RESULTS/f'vice-{fmt}-{suffix}'
                report=json.loads((work/'report.json').read_text())
                self.assertEqual(report['disk_sha256'],digest(work/('test.'+fmt)))
                self.assertEqual(report['base_disk_sha256'],digest(APPS/('udeks-engine.'+fmt)))
                self.assertEqual(report['harness_sha256'],digest(work/'executed-engine-vice-probe.py'))
                self.assertTrue(report['live_cancellation']);self.assertTrue(report['bounds'])
                self.assertFalse(report['physical_c128'])
                records=report['records'];restart=[r for r in records if 'cycle' in r]
                self.assertEqual(len(restart),cycles)
                handles=[r['handle'] for r in restart]
                self.assertEqual(handles,sorted(set(handles)))
                self.assertTrue(all(r['exact_wave'] and r['clean_stop'] for r in restart))
                self.assertTrue(any(r.get('check')=='raw-wire-bounds' and r['checks']==104 and r['exact_waves']==96 and r['invalid_requests']==7 for r in records))
                self.assertTrue(any(r.get('check')=='cancel-public-client-during-orphaned-STOP' and r['exit']==130 and r['recovered'] for r in records))
                self.assertTrue(any(r.get('check')=='cancel-public-server-during-STOP-ACK-wait' and r['exit']==130 and r['stale_send_errno']==9 for r in records))
                if suffix=='cancel':
                    observed=[r for r in records if r.get('check')=='Ctrl-C-input-while-blocked']
                    self.assertEqual(len(observed),2)
                    for r in observed:
                        self.assertEqual(r['server_state'],2);self.assertEqual(r['exit'],130)
                        self.assertEqual(set(r['owners']),{r['server_task'],r['peer_task']})
                        self.assertEqual(r['peer_state'],1 if r['peer_app']=='client' else 2)
                self.assertEqual(raw(work/'client-samples3.bin'),bytes((250,0,6,9,14,19,23,25)))
                self.assertEqual(raw(work/'client-result3.bin'),b'\x32\0')
                pool=raw(work/'ipc-final.bin')
                self.assertEqual(pool[:2],b'\0\0');self.assertEqual(pool[6:8],b'\0\0')
                for app,stem,base,limit in [('client','ENGTEST',0x2300,0x3500),('server','ENGINE',0x8000,0x9000)]:
                    self.assertEqual(report['program_sha256'][app],digest(APPS/(stem+'.BIN')))
                    self.assertEqual(raw(work/(app+'-code.bin')),relocate_executable((APPS/(stem+'.BIN')).read_bytes(),base,limit-base)[16:])
                    for offset in (0,176):self.assertEqual(raw(work/(app+'-guard'+str(offset)+'.bin')),b'\xa5'*16)

    def test_native_both_cancellations_real_input_and_three_restarts(self):
        work=RESULTS/'native-1986-d81'
        report=json.loads((work/'report.json').read_text())
        provenance=json.loads((work/'provenance.json').read_text())
        self.assertEqual(report['revision'],provenance['revision'])
        self.assertEqual(report['format'],'d81');self.assertEqual(report['restart_cycles'],3)
        self.assertTrue(report['live_cancellation']);self.assertFalse(report['physical_c128'])
        self.assertEqual(report['disk_sha256'],digest(work/'test.d81'))
        self.assertEqual(provenance['base_disk_sha256'],digest(APPS/'udeks-engine.d81'))
        self.assertTrue(provenance['resumed_checkpoint'])
        for name,expected in provenance['harness_sha256'].items():
            self.assertEqual(digest(work/'executed-sources'/name),expected)
        log=(work/'run.log').read_text()
        for marker in ('PASS native public client CANCEL and ACK timeout recovery',
                       'PASS native public server CANCEL and stale handle cleanup',
                       'PASS native 1986 engine:'):
            self.assertIn(marker,log)
        self.assertEqual(log.count('PASS engine restart cycle '),3)
        self.assertEqual((work/'samples.bin').read_bytes(),bytes((250,0,6,9,14,19,23,25)))
        self.assertEqual((work/'result.bin').read_bytes(),b'\x32\0')
        pool=(work/'ipc-final.bin').read_bytes()
        self.assertEqual(pool[:2],b'\0\0');self.assertEqual(pool[6:8],b'\0\0')
        for app,path,base,limit in [('client',APPS/'ENGTEST.BIN',0x2300,0x3500),
                                   ('server',APPS/'ENGINE.BIN',0x8000,0x9000),
                                   ('server_fg',APPS/'ENGINE.BIN',0x2300,0x3500),
                                   ('peer',RESULTS/'fixtures/peer/ENGPEER.BIN',0x8000,0x9000)]:
            self.assertEqual((work/(app+'-code.bin')).read_bytes(),relocate_executable(path.read_bytes(),base,limit-base)[16:])

    def test_failed_native_attempts_are_not_reported_as_passes(self):
        failure=RESULTS/'native-d71-loading-failure'
        self.assertFalse((failure/'report.json').exists())
        console=(failure/'missing-console.bin').read_bytes()
        self.assertIn(b'Input/output error',console);self.assertIn(b'loader error',console)
        self.assertIn('state=0 error=0',(failure/'run.log').read_text())
        for name in ('native-d81-incomplete-soak','native-d81-incomplete-cancel'):
            work=RESULTS/name
            self.assertFalse((work/'report.json').exists())
            self.assertFalse(json.loads((work/'incomplete.json').read_text())['qualified'])
            self.assertNotIn('PASS native 1986 engine:',(work/'run.log').read_text())
