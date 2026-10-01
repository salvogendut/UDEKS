# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from gen_banked_bindings import render, WAIT_FIELDS


def table(values):
    return 'Exports list by name:\n'+''.join(f'{name} {value:06X} RLA\n' for name,value in values.items())+'Exports list by value:\n'


class BankedBindings(unittest.TestCase):
    def setUp(self):
        self.gateway=table({'banked_access':0xFEF5})
        values={'_udeks_lifecycle_slots_private':0xC7D9,
                '_udeks_lifecycle_current_private':0xC819,
                '_udeks_lifecycle_last_event_private':0xC81C}
        values.update({f'_udeks_task_wait_{f}_private':0xC820+8*i for i,f in enumerate(WAIT_FIELDS)})
        self.scheduler=table(values)
        self.context=table({'_udeks_task_contexts_private':0xCEA7})

    def test_exact_private_addresses_from_real_export_types(self):
        result=render(self.gateway,self.scheduler,self.context)
        for name,value in (('BANK0_ACCESS','fef5'),('BANK0_SLOTS','c7d9'),
                           ('BANK0_EVENT','c81c'),('BANK0_WAITS','c820'),('BANK0_CONTEXTS','cea7')):
            self.assertIn(f'{name} = ${value}',result)

    def test_bad_types_sizes_missing_and_noncontiguous_waits_rejected(self):
        cases=((self.gateway.replace('RLA','RLZ'),self.scheduler,self.context),
               (self.gateway.replace('00FEF5','00FEFF'),self.scheduler,self.context),
               (self.gateway,self.scheduler.replace('00C820','00C821'),self.context),
               (self.gateway,self.scheduler.replace('00C7D9','00C870'),self.context),
               (self.gateway,self.scheduler,self.context.replace('00CEA7','00CEA9')))
        for g,s,c in cases:
            with self.assertRaises(ValueError): render(g,s,c)
        with self.assertRaises(KeyError): render(self.gateway.replace('banked_access','missing'),self.scheduler,self.context)
