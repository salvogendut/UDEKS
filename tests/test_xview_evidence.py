# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_app_layout import check_coexistence, fitting_allocations
from add_cbm_viewer import add_viewer
from storage_public_probe import files
from png_to_cbm import parse

A=ROOT/'bench/results/2026-10-09-cbm-viewer-r2'


class ViewerEvidence(unittest.TestCase):
    def test_qualified_program_fits_two_ordinary_slots_and_peer_launch_orders(self):
        app=(A/'XVIEW.BIN').read_bytes()
        self.assertEqual((len(app),int.from_bytes(app[10:12],'little'),int.from_bytes(app[12:14],'little')),
                         (3184,2442,1385))
        self.assertEqual(fitting_allocations(app),[3,5])
        disk=files((ROOT/'bench/results/2026-10-09-native-console-files/build/udeks.d81').read_bytes())
        self.assertEqual(check_coexistence({'viewer':fitting_allocations(app),
            'clock':fitting_allocations(disk[b'XCLOCK.BIN']),
            'wave':fitting_allocations(disk[b'XWAVE.BIN'])}),6)
        self.assertEqual(check_coexistence({'one':[3,5],'two':[3,5]}),2)

    def test_evidence_hashes_and_final_demo_packaging(self):
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        app=(A/'XVIEW.BIN').read_bytes()
        pics=[(n,(ROOT/'PICS'/n).read_bytes()) for n in ('ALEX.CBM','CLOCKWORK.CBM','ALEX2.CBM')]
        for drive,fmt in (('1571','d71'),('1581','d81')):
            report=json.loads((A/drive/'report.json').read_text())
            base=(ROOT/f'bench/results/2026-10-09-native-console-files/build/udeks.{fmt}').read_bytes()
            image=add_viewer(base,app,pics)
            self.assertEqual(hashlib.sha256(image).hexdigest(),report['source_sha256'])
            self.assertEqual(hashlib.sha256(app).hexdigest(),report['app_sha256'])
            self.assertEqual(files(image),files(base)|{b'XVIEW.BIN':app}|{n.encode():p for n,p in pics})
            checks={c['check']:c for c in report['checks'] if 'check' in c}
            self.assertEqual(checks['viewer-clock-wave-fully-presented']['retained_bytes'],[1128,344,728,0])
            self.assertTrue(checks['two-independent-viewers-close-cancel-reuse']['passed'])
            self.assertTrue(checks['close-cancel-reuse-and-guards']['passed'])

    def test_two_distinct_pictures_and_survivor_pixels_in_both_drive_captures(self):
        for drive,first,second in (('1571','CLOCKWORK','ALEX2'),('1581','ALEX','CLOCKWORK')):
            for tag,pictures in (('two-pictures',((first,184),(second,24))),
                                 ('background-survives-ctrl-c',((first,184),))):
                data=(A/drive/(tag+'-bitmap.bin')).read_bytes()
                self.assertEqual(data[:2],b'\0\x60')
                for name,x in pictures:
                    w,h,rows=parse((ROOT/'PICS'/(name+'.CBM')).read_bytes())
                    for y in range(h):
                        for xx in range(w):
                            b=data[2+((18+y)//8)*320+((x+xx)//8)*8+(18+y)%8]
                            self.assertEqual(bool(b&(128>>((x+xx)%8))),bool(rows[y][xx]))
            self.assertEqual((A/drive/'three-retained-lengths.bin').read_bytes()[2:],
                             bytes.fromhex('68845801d8020000'))
