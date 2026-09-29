# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'bench/artifacts/2026-09-29-repaint-bank'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-bank'
spec = importlib.util.spec_from_file_location('bank_evidence', ROOT / 'tools/window_repaint_bank.py')
bank = importlib.util.module_from_spec(spec); spec.loader.exec_module(bank)


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class RepaintBankEvidenceTests(unittest.TestCase):
    def test_complete_closure_and_inputs_are_preserved_without_claiming_integration(self):
        report = json.loads((ART / 'build/build-report.json').read_text())
        self.assertIn('not cold-boot delivery, poll integration, NMI or hardware', report['scope'])
        self.assertEqual(report['module_bytes'],3286)
        self.assertEqual(report['state_bytes'],18)
        self.assertEqual(report['packet_bytes'],82)
        self.assertEqual(report['gateway_bytes'],59)
        self.assertEqual(report['binding_bytes'],84)
        self.assertEqual(report['code_spare'],522)
        self.assertEqual(report['segments']['CODE'],[0xD103,0xDDD5])
        self.assertEqual(report['segments']['HIGHBSS'],[0xDFE0,0xDFF1])
        self.assertGreater(len(report['helpers']),10)
        self.assertIn('memcpy.o',report['helpers'])
        self.assertGreater((ART / 'build/none.lib').stat().st_size,10000)
        for name,sha in report['input_sha256'].items():
            self.assertEqual(digest(ART / 'inputs' / name),sha,name)
        for name,sha in report['output_sha256'].items():
            self.assertEqual(digest(ART / 'build' / name),sha,name)

    def test_both_emulators_cover_semantics_and_exact_negative_controls(self):
        report = json.loads((ART / 'build/build-report.json').read_text())
        program = (ART / 'build/probe-normal.prg').read_bytes()
        for case,patch in report['negative_controls'].items():
            bad = (ART / 'build' / f'probe-{case}.prg').read_bytes()
            self.assertEqual(len(program),len(bad))
            differences = [i for i,(a,b) in enumerate(zip(program,bad)) if a != b]
            self.assertEqual(differences,[patch['offset']])
            self.assertEqual(program[patch['offset']],patch['before'])
            self.assertEqual(bad[patch['offset']],patch['after'])
        for engine in ('1986','vice'):
            run = json.loads((RESULT / f'{engine}-run.json').read_text())
            self.assertEqual(run['build_report_sha256'],digest(ART / 'build/build-report.json'))
            self.assertEqual(set(run['decoded']),set(bank.CASES))
            for case in bank.CASES:
                path = RESULT / f'{engine}-{case}.bin'
                self.assertEqual(digest(path),run['raw_sha256'][path.name])
                data = path.read_bytes()
                self.assertEqual(bank.decode(data,report['expected'],case),run['decoded'][case])
                if case != 'normal':
                    with self.assertRaises(ValueError): bank.decode(data,report['expected'])

    def test_manifests_cover_every_preserved_file(self):
        for directory in (ART,RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name = line.split('  ',1); declared[name] = sha
                self.assertEqual(digest(directory / name),sha,name)
            self.assertEqual(set(declared),{str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p.name != 'SHA256SUMS'})
