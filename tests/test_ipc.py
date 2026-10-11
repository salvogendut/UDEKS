# SPDX-License-Identifier: GPL-3.0-or-later
"""Production 6502 IPC policy and real dispatcher/retirement integration."""
from pathlib import Path
import shutil
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(all(shutil.which(x) for x in ('ca65','cl65','sim65')), 'cc65 CPU simulator required')
class IpcCpuTests(unittest.TestCase):
    def test_production_gate_queue_model_and_retirement_negative_control(self):
        result=subprocess.run(['python3','tools/check_ipc.py'],cwd=ROOT,text=True,capture_output=True,timeout=150)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('3000 differential steps, handle exhaustion',result.stdout)
        self.assertIn('missing IPC retirement hook detected',result.stdout)
