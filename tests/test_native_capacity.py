# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_app_layout import ALLOCATIONS, JOINED_ALLOCATION, fitting_allocations
from graphics_app_layout import graphics_lifetimes, Region, disjoint
from native_capacity_probe import fixture, fixtures
from build_graphical_example import check_native_capacity
from build_d71 import validate_native_app


class NativeCapacity(unittest.TestCase):
    def test_join_is_exact_union_without_new_cpu_pages(self):
        task,base,limit,stack,zp,hp=JOINED_ALLOCATION
        self.assertEqual((task,base,zp,hp),(3,ALLOCATIONS[0][1],*ALLOCATIONS[0][4:]))
        self.assertEqual(ALLOCATIONS[0][2],ALLOCATIONS[1][1])
        self.assertEqual((limit,stack),ALLOCATIONS[1][2:4])
        self.assertEqual((stack-base,limit-base),(7168,7424))

    def test_alternative_lifetime_excludes_donor_and_overlaps_fail(self):
        regions=[Region('worker',1,0x2000,0x2300),Region('display',1,0x4000,0x8000)]
        phases=graphics_lifetimes(regions)
        joined=[Region(**r) for r in phases['joined_3_4_excludes_donor']]
        self.assertEqual(len(joined),14)
        self.assertFalse(any('app 4' in r.name for r in joined))
        disjoint(joined+regions)
        with self.assertRaisesRegex(ValueError,'overlap'):
            disjoint(joined+[Region('donor',1,0x3500,0x4000)])

    def test_both_runtime_and_disk_staging_boundaries(self):
        for image in (fixture(7168),fixture(32,7136),fixture(4352),fixture(4000,0,range(1,1001))):
            check_native_capacity(image)
            validate_native_app(image)
            self.assertIn(3,fitting_allocations(image,joined=True))
        # A small installed image can have a large relocation tail.
        self.assertEqual(len(fixtures()['tailonly']),7424)
        self.assertEqual(len(fixtures()['filebad']),7425)
        self.assertFalse(fitting_allocations(fixtures()['tailonly']))
        for name in ('bssbad','filebad','badlarge'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                check_native_capacity(fixtures()[name])
            with self.subTest(name=name),self.assertRaises(ValueError):
                validate_native_app(fixtures()[name])
        check_native_capacity(fixture(4352))
        self.assertEqual(fitting_allocations(fixture(4352)),[3])
        self.assertFalse(fitting_allocations(fixture(4353)))
        self.assertEqual(fitting_allocations(fixture(4353),joined=True),[3])

    def test_bank0_bounds_are_published_before_task_runs(self):
        loader=(ROOT/'src/services/app/banked_loader.s').read_text()
        activate=loader.split('activate:',1)[1].split('reap:',1)[0]
        self.assertIn('lda stack_pages,x           ; effective bound',activate)
        self.assertLess(activate.index('jsr MEMORY_GATE'),activate.index('; RUNNABLE is the publication'))
        access=(ROOT/'src/services/window/banked_access.s').read_text()
        self.assertIn('_udeks_banked_pages_init:\n        sta _udeks_native_stack_pages,x',access)
        self.assertIn('limit=(unsigned int)udeks_native_stack_pages[index]<<8;',
                      (ROOT/'src/services/window/retained_paths.c').read_text())

    def test_loan_is_service_policy_and_all_failure_paths_unjoin(self):
        source=(ROOT/'src/services/app/banked_loader.s').read_text()
        self.assertIn('release:\n        jsr unjoin',source)
        self.assertIn('done:\n        pha\n        beq :+\n        jsr unjoin',source)
        self.assertIn('lda banked_owned+1\n        bne join_return',source)
        self.assertIn('ldx #24',source.split('try_join:',1)[1])
        entry=source.split('banked_entry:',1)[1].split('check_name:',1)[0]
        self.assertLess(entry.index('cmp #3                      ; reserved'),entry.index('jcs reap'))
        for name in ('xsprdef','xclock','xwave','large','bigcon'):
            self.assertNotIn('"'+name+'"',source.lower())


if __name__=='__main__': unittest.main()
