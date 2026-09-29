# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import window_cache_partial as partial


class PartialCacheTests(unittest.TestCase):
    def test_host_pixels_atomicity_and_restart(self):
        providers = {
            'policy': partial.fixed_policy((ROOT/'src/services/window/move_cache_state.c').read_text()),
            'command': partial.command((ROOT/'src/services/window/cache_overlay.c').read_text()),
            'flow': partial.compact.shared_geometry((ROOT/'src/services/window/move_cache_flow.c').read_text()),
            'controller': partial.controller((ROOT/'bench/window-cache-controller/controller.c').read_text()),
        }
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            for name,source in providers.items():(work/(name+'.c')).write_text(source)
            (work/'config.h').write_text('''#include "udeks/window_cache_flow.h"
extern struct udeks_cache_flow fixed_flow;
#define UDEKS_CACHE_FLOW_ADDRESS (&fixed_flow)
#define UDEKS_CACHE_COMMAND_HOST_TEST 1
#define UDEKS_CACHE_FLOW_HOST_TEST 1
#define UDEKS_CACHE_FLOW_IN_BANK 1
#define flow_test_handle cache_test_owner
#define flow_test_generation cache_test_generation
#define flow_test_geometry cache_test_geometry
#define flow_test_eligible cache_test_eligible
#define UDEKS_CACHE_CONTROLLER_HOST_TEST 1
#define UDEKS_CACHE_LEASE_ADDRESS 0x5220u
#define UDEKS_CACHE_IMAGE_ADDRESS 0x5350u
#define UDEKS_CACHE_IMAGE_CAPACITY 2224u
#define __fastcall__
''')
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'include'),'-include',str(work/'config.h'),
                *[str(work/(n+'.c')) for n in providers],
                str(ROOT/'bench/window-cache-controller/partial-host.c'),
                '-o',str(work/'test')],check=True)
            subprocess.run([str(work/'test')],check=True)

    def test_generation_rejects_changed_seams(self):
        for transform in (partial.fixed_policy,partial.command,partial.controller):
            with self.assertRaises(ValueError):transform('changed source')


if __name__=='__main__':unittest.main()
