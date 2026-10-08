# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaging and ABI checks; test_xsprdef_behavior executes the C editor."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class XsprdefSourceTests(unittest.TestCase):
    def test_editor_uses_public_versioned_tiles_not_window_internals(self):
        source = (ROOT/'user/bin/xsprdef.c').read_text()
        self.assertIn('UDEKS_GFX_TILE(cell)',source)
        self.assertNotIn('udeks_window_',source)
        self.assertIn('P[2] = 248; P[4] = 192;',source)
        header = (ROOT/'include/udeks/banked_graphics.h').read_text()
        self.assertIn('#define UDEKS_GFX_COMMANDS 160u',header)

    def test_window_geometry_fits_the_create_byte_fields(self):
        source = (ROOT/'user/bin/xsprdef.c').read_text()
        width = int(re.search(r'P\[4\] = (\d+);',source)[1])
        height = int(re.search(r'P\[5\] = (\d+);',source)[1])
        self.assertLessEqual(width,255)
        self.assertGreaterEqual(width,240)
        self.assertLessEqual(height,196)
        self.assertGreaterEqual(height,192)

    def test_makefile_builds_and_ships_the_app(self):
        makefile = (ROOT/'Makefile').read_text()
        self.assertIn('USER_XSPRDEF_UDEX := $(BUILD_USER)/xsprdef.udx',makefile)
        self.assertIn('--graphics-abi 17 --output $(BUILD_USER)/native-xsprdef',makefile)
        self.assertIn('--static-locals --capacity 7424',makefile)
        self.assertIn('--source user/bin/xspr_file.c',makefile)
        self.assertIn('--xsprdef $(USER_XSPRDEF_UDEX)',makefile)

    def test_disk_builder_validates_and_installs_the_editor(self):
        builder = (ROOT/'tools/build_d71.py').read_text()
        self.assertIn('validate_native_app(xsprdef)',builder)
        self.assertIn('install_prg_file(image, "XSPRDEF.BIN", xsprdef',builder)

    def test_retained_command_cap_is_consistent(self):
        self.assertIn('#define UDEKS_RETAINED_COMMANDS 160u',
                      (ROOT/'include/udeks/retained_paths.h').read_text())
        self.assertIn('at most 160 eight-byte commands',(ROOT/'abi/window.md').read_text())

    def test_probe_reads_status_under_kernel_map_and_verifies_normal_speed(self):
        source=(ROOT/'tools/xsprdef_probe.py').read_text()
        self.assertIn("return capture('status-'+format(address,'04x'),address,1)[0]",source)
        self.assertNotIn('byte(port,',source)
        self.assertNotIn('sp.wait_for_byte(',source)
        self.assertIn("if b'Warp mode is off.' not in reply:",source)
