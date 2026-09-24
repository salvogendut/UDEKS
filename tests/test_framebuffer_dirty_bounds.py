# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")


@unittest.skipUnless(CC, "host C compiler is unavailable")
class FramebufferDirtyBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        temporary = Path(cls.temporary.name)
        stub = temporary / "font_stub.c"
        stub.write_text(
            "static const unsigned char glyph[7] = {0};\n"
            "const unsigned char *udeks_font_glyph(unsigned char c) "
            "{ (void)c; return glyph; }\n",
            encoding="ascii",
        )
        library = temporary / "surface.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/framebuffer/surface.c"),
                str(stub),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.surface = ctypes.CDLL(str(library))
        cls.surface.udeks_surface_plot.argtypes = [
            ctypes.c_uint,
            ctypes.c_ubyte,
            ctypes.c_ubyte,
        ]
        cls.surface.udeks_surface_dirty_bounds.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        cls.surface.udeks_surface_dirty_bounds.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def bounds(self):
        first = ctypes.c_ubyte()
        last = ctypes.c_ubyte()
        present = self.surface.udeks_surface_dirty_bounds(
            ctypes.byref(first), ctypes.byref(last)
        )
        return present, first.value, last.value

    def test_tracks_only_rows_touched_since_last_clean(self):
        self.surface.udeks_surface_reset()
        self.surface.udeks_surface_clean_all()
        self.assertEqual(self.bounds()[0], 0)
        self.surface.udeks_surface_plot(0, 50, 1)
        self.assertEqual(self.bounds(), (1, 50, 50))
        self.surface.udeks_surface_plot(0, 10, 1)
        self.surface.udeks_surface_plot(0, 100, 1)
        self.assertEqual(self.bounds(), (1, 10, 100))
        self.surface.udeks_surface_clean_all()
        self.assertEqual(self.bounds()[0], 0)


if __name__ == "__main__":
    unittest.main()
