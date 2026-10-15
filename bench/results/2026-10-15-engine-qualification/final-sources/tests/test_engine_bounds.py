# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the machine bounds fixture against real worker C and wire policy."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class EngineBounds(unittest.TestCase):
    def test_frozen_oracle_and_error_cases_complete_without_endpoint_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            so=Path(tmp)/'bounds.so'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                '-DUDEKS_Z80_WORKER_HOST_TEST','-Iinclude','-Iuser/include',
                'tests/fixtures/engine_bounds.c','src/z80/worker.c','-o',str(so)],cwd=ROOT,check=True)
            lib=ctypes.CDLL(str(so))
            lib.engine_bounds_run.restype=ctypes.c_ubyte
            self.assertEqual(lib.engine_bounds_run(),0)
            for name,value in [('engine_bounds_checks',104),('engine_bounds_worker_calls',97),('engine_bounds_closed',1)]:
                self.assertEqual(ctypes.c_uint.in_dll(lib,name).value,value)
            self.assertEqual(ctypes.c_ubyte.in_dll(lib,'engine_bounds_state').value,2)
            self.assertEqual(ctypes.c_ubyte.in_dll(lib,'engine_bounds_error').value,0)
