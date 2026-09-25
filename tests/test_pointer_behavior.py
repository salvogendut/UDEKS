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
class PointerBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        library = Path(cls.temporary.name) / "pointer_drivers.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/input/mouse1351.c"),
                str(ROOT / "src/services/input/joystick.c"),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.driver = ctypes.CDLL(str(library))
        cls.driver.udeks_mouse1351_initialize.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
        ]
        cls.driver.udeks_mouse1351_decode.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
            ctypes.c_ubyte,
            ctypes.POINTER(ctypes.c_byte),
            ctypes.POINTER(ctypes.c_byte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        cls.driver.udeks_joystick_initialize.argtypes = [ctypes.c_ubyte]
        cls.driver.udeks_joystick_decode.argtypes = [
            ctypes.c_ubyte,
            ctypes.POINTER(ctypes.c_byte),
            ctypes.POINTER(ctypes.c_byte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def mouse_decode(self, x, y=0x40, active=0):
        dx = ctypes.c_byte()
        dy = ctypes.c_byte()
        buttons = ctypes.c_ubyte()
        self.driver.udeks_mouse1351_decode(
            x, y, active,
            ctypes.byref(dx), ctypes.byref(dy), ctypes.byref(buttons),
        )
        return dx.value, dy.value, buttons.value

    def joystick_decode(self, active):
        dx = ctypes.c_byte()
        dy = ctypes.c_byte()
        buttons = ctypes.c_ubyte()
        self.driver.udeks_joystick_decode(
            active, ctypes.byref(dx), ctypes.byref(dy), ctypes.byref(buttons)
        )
        return dx.value, dy.value, buttons.value

    def test_mouse_uses_noise_filtered_modulo_64_motion(self):
        self.driver.udeks_mouse1351_initialize(0x40, 0x40)
        self.assertEqual(self.mouse_decode(0x42), (1, 0, 0))
        self.assertEqual(self.mouse_decode(0x43), (0, 0, 0))
        self.assertEqual(self.mouse_decode(0x44), (1, 0, 0))

        self.driver.udeks_mouse1351_initialize(0x7E, 0x40)
        self.assertEqual(self.mouse_decode(0x00), (1, 0, 0))
        self.assertEqual(self.mouse_decode(0x7E), (-1, 0, 0))

    def test_mouse_y_and_buttons_are_normalized(self):
        self.driver.udeks_mouse1351_initialize(0x40, 0x40)
        self.assertEqual(self.mouse_decode(0x40, 0x42, 0x11), (0, -1, 3))

    def test_joystick_debounces_then_moves_five_pixels(self):
        self.driver.udeks_joystick_initialize(0)
        self.assertEqual(self.joystick_decode(0x08), (0, 0, 0))
        self.assertEqual(self.joystick_decode(0x08), (5, 0, 0))
        self.assertEqual(self.joystick_decode(0x14), (0, 0, 0))
        self.assertEqual(self.joystick_decode(0x14), (-5, 0, 1))


if __name__ == "__main__":
    unittest.main()
