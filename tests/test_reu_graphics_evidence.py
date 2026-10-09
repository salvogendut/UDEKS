# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'bench/results/2026-10-09-reu-graphics'


class ReuGraphicsEvidence(unittest.TestCase):
    def test_preserved_hashes_and_source_binding(self):
        for line in (E/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((E/name).read_bytes()).hexdigest(),digest,name)
        disk=hashlib.sha256((E/'artifacts/udeks-packed.d81').read_bytes()).hexdigest()
        for case,kib in (('vice-512',512),('vice-stock',0)):
            report=json.loads((E/case/'report.json').read_text())
            self.assertEqual(report['reu_kib'],kib)
            self.assertEqual(report['disk_sha256'],disk)
            for name,digest in report['pictures'].items():
                self.assertEqual(hashlib.sha256((E/'artifacts'/name).read_bytes()).hexdigest(),digest)
            for path,digest in report['source_sha256'].items():
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
    def test_independent_pixels_backing_bytes_code_guards_and_cleanup(self):
        picture=(E/'artifacts/CLOCK160.CBM').read_bytes()[11:]
        reu=(E/'vice-512/reu.img').read_bytes();expected=bytearray([165])*len(reu)
        second=(E/'artifacts/ALEX128.CBM').read_bytes()[11:]
        expected[:len(picture)]=picture
        expected[8192:8192+len(second)]=second
        self.assertEqual(reu,expected)
        module=(E/'artifacts/bitmap-hidden-sealed.bin').read_bytes()
        for case in ('vice-stock','vice-512'):
            def raw(name):return (E/case/(name+'.bin')).read_bytes()[2:]
            code=raw('installed-code');self.assertEqual(code,module[:len(code)])
            self.assertEqual(raw('final-code'),code)
            self.assertNotEqual(raw('pointer-count'),raw('pointer-after'))
            self.assertEqual(raw('final-bootfs'),raw('bootfs-backup'))
            self.assertEqual(raw('final-backup'),raw('bootfs-backup'))
            for side in ('low','high'):
                self.assertEqual(raw('buffer-'+side+'-guard'),raw('final-'+side+'-guard'))
            self.assertFalse(any(raw('lengths')))
            self.assertFalse(any(raw('store')[:36]))
            for tag in ('initial','reuse'):
                canvas=raw(tag+'-bitmap');self.assertEqual(raw(tag+'-shadow'),canvas)
                for y in range(100):
                    for x in range(160):
                        actual=bool(canvas[((18+y)//8)*320+((24+x)//8)*8+(18+y)%8]&(128>>((24+x)%8)))
                        self.assertEqual(actual,bool(picture[y*20+x//8]&(128>>(x%8))))
        canvas=(E/'vice-512/two-large-bitmap.bin').read_bytes()[2:]
        self.assertEqual(canvas,(E/'vice-512/two-large-shadow.bin').read_bytes()[2:])
        for y in range(80):
            for x in range(128):
                actual=bool(canvas[((18+y)//8)*320+((24+x)//8)*8+(18+y)%8]&(128>>((24+x)%8)))
                self.assertEqual(actual,bool(second[y*16+x//8]&(128>>(x%8))))
