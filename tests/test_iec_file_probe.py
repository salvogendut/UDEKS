# SPDX-License-Identifier: GPL-3.0-or-later
"""The line-level probe must reject partial or corrupted named-file reads."""
import unittest

from tools.iec_directory_probe import validate_file


SOURCE = bytes(range(32))


def result():
    data = bytearray(512)
    data[:6] = b'\x02\x00\x00\x00\x20\x00'
    data[10:13] = b'\x01\x00\x01'
    data[14:16] = b'\x03\x03'
    data[0x100:0x120] = SOURCE
    return data


class IecFileProbeTests(unittest.TestCase):
    def test_exact_file_and_restored_machine_state(self):
        validate_file(bytes(result()), SOURCE)

    def test_rejects_short_read_and_changed_data(self):
        data = result()
        data[4] = 31
        with self.assertRaises(ValueError):
            validate_file(bytes(data), SOURCE)
        data = result()
        data[0x111] ^= 1
        with self.assertRaises(ValueError):
            validate_file(bytes(data), SOURCE)

    def test_rejects_unrestored_speed_and_vic_bank(self):
        data = result()
        data[12] = 0
        with self.assertRaises(ValueError):
            validate_file(bytes(data), SOURCE)
        data = result()
        data[15] = 2
        with self.assertRaises(ValueError):
            validate_file(bytes(data), SOURCE)


if __name__ == '__main__':
    unittest.main()
