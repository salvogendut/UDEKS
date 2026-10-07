# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from storage_public_probe import files

ARTIFACTS=ROOT/'bench/artifacts/2026-10-07-storage-public'
RESULTS=ROOT/'bench/results/2026-10-07-storage-public'


class PublicStorage(unittest.TestCase):
    def test_preserved_checksums(self):
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            digest,path=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)

    def test_all_formats_binary_persistence_and_existing_files(self):
        for drive,ext in (('1541','d64'),('1571','d71'),('1581','d81')):
            result=json.loads((RESULTS/(drive+'.json')).read_text())
            original=(ARTIFACTS/('udeks.'+ext)).read_bytes()
            written=(ARTIFACTS/('written.'+ext)).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(),result['disk_sha256'])
            self.assertEqual(hashlib.sha256(written).hexdigest(),result['written_disk_sha256'])
            before,after=files(original),files(written)
            self.assertEqual(len(before),result['original_files_unchanged'])
            for name,data in before.items(): self.assertEqual(after[name],data,name)
            expected={n.encode():bytes(i&255 for i in range(size)) for n,size in
                      dict(WRTEST=515,EMPTY=0,ONE=1,EXACT=254,LIVE=24).items()}
            self.assertEqual({n:d for n,d in after.items() if n not in before},expected)
            for n in expected:
                self.assertIn('save -c /'+n.decode()+' '+str(len(expected[n])),
                              [r['command'] for r in result['checks'] if r['boot']==1])
            for boot in (0,1):
                denied=next(r for r in result['checks'] if r['boot']==boot and r['command']=='save /NOWRITE 1')
                self.assertEqual(denied['status'],1)
                self.assertIn('Read-only filesystem',denied['console'])
            self.assertIn('save /LIVE 24',[r['command'] for r in result['checks']])

    def test_save_is_the_separately_built_disk_binary(self):
        image=(ARTIFACTS/'SAVE.BIN').read_bytes()
        self.assertEqual(image[:4],b'UDEX')
        self.assertEqual(int.from_bytes(image[8:10],'little'),0x200)
        self.assertLessEqual(len(image)-16+int.from_bytes(image[12:14],'little'),0xa00)
        for ext in ('d64','d71','d81'):
            self.assertEqual(files((ARTIFACTS/('udeks.'+ext)).read_bytes())[b'SAVE.BIN'],image)

    def test_boundary_preserves_console_and_recovery(self):
        dispatcher=(ROOT/'src/8502/syscall_gate.s').read_text()
        write=dispatcher.split('task_write:\n',1)[1].split('task_write_valid:',1)[0]
        self.assertIn('cmp #$01',write); self.assertIn('cmp #$02',write)
        self.assertIn('jmp $c880',write)
        self.assertIn('.byte "UTRQ",0,14',(ROOT/'user/lib/fs_request.s').read_text())
        self.assertIn('.byte "UTRQ",0,14',(ROOT/'user/lib/mount_rw_request.s').read_text())
        self.assertNotIn('remount',(ROOT/'user/bin/mount.c').read_text())
        self.assertIn('--entry mount=$(USER_RECOVERY_MOUNT_UDEX)',(ROOT/'Makefile').read_text())


if __name__=='__main__': unittest.main()
