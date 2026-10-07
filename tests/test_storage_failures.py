# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_d71 as d71
import build_d81 as d81
from storage_failure_probe import make_data,audit
from storage_public_probe import files

ARTIFACTS=ROOT/'bench/artifacts/2026-10-07-storage-acceptance'
RESULTS=ROOT/'bench/results/2026-10-07-storage-acceptance'


class AcceptanceEvidence(unittest.TestCase):
    def test_preserved_hashes(self):
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            digest,path=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)

    def test_vice_failure_records_and_independent_media_audit(self):
        for drive,ext in (('1541','d64'),('1571','d71'),('1581','d81')):
            folder=RESULTS/('vice-'+drive)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual(hashlib.sha256((ARTIFACTS/('udeks.'+ext)).read_bytes()).hexdigest(),
                             report['disk_sha256'])
            self.assertEqual(hashlib.sha256((folder/('system.'+ext)).read_bytes()).hexdigest(),
                             report['system_sha256'])
            self.assertEqual(report.get('skipped',[]),
                             ['media-removal-during-write'] if drive=='1581' else [])
            normal={'RETURN1','RETURN2','OWNER0','OWNER1','CHILD','RECOVER3','AFTER'}
            if drive!='1581': normal.add('RECOVER2')
            allowed={'protected':set(),'normal':normal,'full':set(),'partial':{'PARTIAL'},
                     'removed':set() if drive=='1581' else {'OWNER2'},'close':{'OWNER3'}}
            for name,remaining in (('protected',None),('normal',None),('full',0),('partial',3),
                                   ('removed',None),('close',None)):
                before=make_data(drive,remaining)
                after=(folder/(name+'.'+ext)).read_bytes()
                self.assertEqual(hashlib.sha256(before).hexdigest(),report['media'][name]['before_sha256'])
                self.assertEqual(hashlib.sha256(after).hexdigest(),report['media'][name]['after_sha256'])
                self.assertEqual(audit(before,after,allowed[name]),report['files'][name])
                if name=='protected': self.assertEqual(before,after)
            actual=files((folder/('normal.'+ext)).read_bytes())
            for name in normal:
                self.assertEqual(actual[name.encode()],bytes(i&255 for i in range(515 if name=='AFTER' else 24)))
            self.assertEqual(set(actual),{b'KEEP'}|{n.encode() for n in normal})
            for name in ('FULL 515','PARTIAL 4096'):
                row=next(r for r in report['checks'] if r.get('command')=='save /mnt/'+name)
                self.assertEqual(row['status'],1)
                self.assertIn('No space left on device',row['console'])
            for row in report['checks']:
                if 'retired' in row:
                    self.assertEqual(row['after'],(row['before']+1)&255)
                    self.assertEqual(row['cleanup_error'],0)
                if 'fault' in row:
                    self.assertIn(row['close_error'],(5,19))
            faults={r['fault'] for r in report['checks'] if 'fault' in r}
            self.assertEqual(faults,{'close'} if drive=='1581' else {'removed','close'})

    def test_native_1986_persistence_and_nmi_records(self):
        for drive,ext in (('1571','d64'),('1581','d81')):
            folder=RESULTS/('native-'+drive)
            report=json.loads((folder/'result.json').read_text())
            original=(ARTIFACTS/('udeks.'+ext)).read_bytes()
            written=(folder/('test.'+ext)).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(),report['disk_sha256'])
            self.assertEqual(hashlib.sha256(written).hexdigest(),report['written_disk_sha256'])
            before,after=files(original),files(written)
            for name,data in before.items(): self.assertEqual(after[name],data)
            expected={n.encode():bytes(i&255 for i in range(size)) for n,size in
                      dict(BINARY=515,ZERO=0,NMITEST=515,GRAPHICS=24).items()}
            self.assertEqual({n:d for n,d in after.items() if n not in before},expected)
            self.assertIn('PASS RESTORE and CIA2 NMI drained',(folder/'create.log').read_text())
            for name,size in report['created'].items():
                self.assertIn('PASS save -c /'+name.lower()+' '+str(size),(folder/'reboot.log').read_text())


class FailureMedia(unittest.TestCase):
    def test_full_fixtures_have_real_file_chains_and_exact_free_counts(self):
        for drive in ('1541','1571','1581'):
            for remaining in (0,3):
                image=make_data(drive,remaining)
                inventory=files(image)
                self.assertEqual(inventory[b'KEEP'],bytes(range(24)))
                self.assertEqual(inventory[b'FILL'],b'Z'*len(inventory[b'FILL']))
                if drive=='1581':
                    free=sum(image[d81.bam_entry(t)] for t in range(1,81) if t!=40)
                    capacity=79*40
                else:
                    bam=d71.sector_offset(18,0)
                    free=sum(image[bam+4+(t-1)*4] for t in range(1,36) if t!=18)
                    capacity=664
                    if drive=='1571':
                        free+=sum(image[bam+0xdd+t-36] for t in range(36,71) if t!=53)
                        capacity=1328
                self.assertEqual(free,remaining)
                self.assertEqual(len(inventory[b'FILL'])//254+1+remaining,capacity)

    def test_audit_rejects_unexpected_new_files_and_changed_existing_data(self):
        before=make_data('1541'); changed=bytearray(before)
        d71.install_prg_file(changed,'UNEXPECTED',b'new',file_type=0x81)
        with self.assertRaises(AssertionError): audit(before,changed,set())
        self.assertEqual(audit(before,changed,{'UNEXPECTED'})['UNEXPECTED']['bytes'],3)
        entry=next(d81.entries(changed,d71.sector_offset,18,1))
        changed[d71.sector_offset(entry[1],entry[2])+2]^=1
        with self.assertRaises(AssertionError): audit(before,changed,{'UNEXPECTED'})

    def test_fixture_clients_use_public_requests_not_private_service_calls(self):
        source=(ROOT/'bench/storage-failures/holder.c').read_text()
        self.assertIn('R[5]=14',source)
        self.assertIn('jsr $ff16',source)
        self.assertNotIn('$120f',source.lower())
        self.assertNotIn('$c880',source.lower())
        self.assertIn('request(6,3,11)',source)
        self.assertIn('request(2,4,24)',source)
        self.assertIn('request(9,4,0)',source)
        child=(ROOT/'bench/storage-failures/child.s').read_text()
        self.assertIn('.byte "UTRQ",0,14',child)
        self.assertIn('jmp $ff16',child)


if __name__=='__main__': unittest.main()
