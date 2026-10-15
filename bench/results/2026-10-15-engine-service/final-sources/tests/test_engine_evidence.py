# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind engine slice-2 reports to preserved programs, disks and machine bytes."""
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from native_app_layout import fitting_allocations,check_coexistence
from o65_to_udex import relocate_executable
from add_disk_apps import directory_names
ART=ROOT/'bench/artifacts/2026-10-15-engine-demo';RESULTS=ROOT/'bench/results/2026-10-15-engine-service'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class EngineEvidence(unittest.TestCase):
    def test_all_preserved_files_are_bound_and_final_native_captures_match(self):
        for folder in (ART,RESULTS):
            entries={}
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                expected,name=line.split('  ',1);self.assertEqual(digest(folder/name),expected,name);entries[name]=expected
            self.assertEqual(set(entries),{str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS'})
            self.assertFalse(list(folder.rglob('*.vsf')))
        work=RESULTS/'native-1986-d81';report=json.loads((work/'report.json').read_text());prov=json.loads((work/'provenance.json').read_text())
        self.assertEqual(report['revision'],prov['revision']);self.assertEqual(report['disk_sha256'],digest(ART/'udeks-engine.d81'))
        self.assertFalse(report['physical_c128']);self.assertEqual((work/'samples.bin').read_bytes(),bytes((250,0,6,9,14,19,23,25)))
        self.assertEqual((work/'result.bin').read_bytes(),b'\x32\0')
        self.assertIn('PASS native 1986 engine:',(work/'run.log').read_text())
        pool=(work/'ipc-final.bin').read_bytes();self.assertEqual(pool[:2],b'\0\0');self.assertEqual(pool[6:8],b'\0\0')
        for app,stem,base,limit in [('client','ENGTEST',0x2300,0x3500),('server','ENGINE',0x8000,0x9000)]:
            self.assertEqual((work/(app+'-code.bin')).read_bytes(),relocate_executable((ART/(stem+'.BIN')).read_bytes(),base,limit-base)[16:])
        for name,expected in prov['harness_sha256'].items():self.assertEqual(digest(RESULTS/'sources/tools'/name),expected)
    def test_demo_program_hashes_sizes_and_all_launch_orders(self):
        manifest=json.loads((ART/'manifest.json').read_text());fits={}
        for name in ('ENGINE','ENGTEST'):
            path=ART/(name+'.BIN');self.assertEqual(digest(path),manifest['programs'][name]['sha256'])
            fits[name]=fitting_allocations(path.read_bytes());self.assertEqual(fits[name],manifest['programs'][name]['fits'])
        for name,filename in [('xclock','XCLOCK.BIN'),('xdraw','XDRAW.BIN')]:
            path=ART/filename;fits[name]=fitting_allocations(path.read_bytes())
            self.assertEqual(digest(path),manifest['graphics'][name]['sha256'])
            self.assertEqual(fits[name],manifest['graphics'][name]['fits'])
        self.assertEqual(check_coexistence(fits),manifest['launch_orders']);self.assertEqual(manifest['launch_orders'],24)
        for fmt in ('d71','d81'):
            path=ART/('udeks-engine.'+fmt);self.assertEqual(digest(path),manifest['disks'][fmt]['sha256'])
            self.assertTrue({b'ENGINE.BIN',b'ENGTEST.BIN'}<=directory_names(path.read_bytes()))
        self.assertIn('d64',manifest);self.assertFalse((ART/'udeks-engine.d64').exists())
