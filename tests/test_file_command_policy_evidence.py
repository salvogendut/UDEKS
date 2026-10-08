# SPDX-License-Identifier: GPL-3.0-or-later
"""A failing service-fit gate must never be represented as shipped commands."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from storage_mutation_layout import headroom
from build_scheduler_overlay import map_segments

A = ROOT/'bench/artifacts/2026-10-08-file-command-policy'
R = ROOT/'bench/results/2026-10-08-file-command-policy'


class FileCommandPolicyEvidence(unittest.TestCase):
    def test_all_artifacts_and_reports_are_hash_checked(self):
        for directory in (A,R):
            names=set()
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split()
                self.assertNotIn(name,names); names.add(name)
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(names,{p.name for p in directory.iterdir() if p.name!='SHA256SUMS'})

    def test_failed_policy_budget_remains_an_explicit_failed_gate(self):
        text=(A/'policy-overflow.map').read_text()
        with self.assertRaises(ValueError): headroom(text)
        budget=headroom(text,allow_overflow=True)
        report=json.loads((R/'layout.json').read_text())
        self.assertFalse(report['link_passed'])
        self.assertEqual(report['with_backend'],budget)
        self.assertEqual(budget['STORAGEHIGH'],-586)
        self.assertEqual(budget['code_total'],-305)
        self.assertEqual(budget['BSS'],10)
        self.assertIn('overflows memory area', (R/'link.log').read_text())

    def test_commands_are_independent_fixed_allocation_udex_images(self):
        for name,size in (('cp',2157),('mv',2157),('rm',2026)):
            program=(A/(name.upper()+'.BIN')).read_bytes()
            self.assertEqual(len(program),size)
            self.assertEqual(program[:8],b'UDEX\0\1\1\0')
            self.assertEqual(int.from_bytes(program[8:10],'little'),0x200)
            self.assertEqual(int.from_bytes(program[14:16],'little'),0x200)
            image=int.from_bytes(program[10:12],'little')
            bss=int.from_bytes(program[12:14],'little')
            self.assertEqual(len(program),image+16)
            self.assertLessEqual(0x200+image+bss,0x0b00)
            segments=map_segments((A/(name+'.map')).read_text())
            self.assertEqual(segments['BSS'],(0x200+image,0x200+image+bss-1,bss))

    def test_sim65_sdk_proof_is_not_claimed_as_live_filesystem_qualification(self):
        q=json.loads((R/'qualification.json').read_text())
        self.assertEqual(q['sdk_sim65_exit'],0)
        self.assertEqual(q['sdk_scenarios'],21)
        self.assertIn('PASS 21 SDK scenarios', (R/'sdk.log').read_text())
        self.assertFalse(q['candidate_shipped'])
        self.assertFalse(q['live_mutation_qualification'])
        self.assertFalse(q['policy_link_passed'])
        self.assertEqual(q['production_minor'],17)
        self.assertEqual(q['candidate_minor'],18)
        production=ROOT/'bench/artifacts/2026-10-08-storage-namespace/udeks.d64'
        self.assertEqual(hashlib.sha256(production.read_bytes()).hexdigest(),q['production_d64_sha256'])
