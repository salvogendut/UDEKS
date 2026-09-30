# SPDX-License-Identifier: GPL-3.0-or-later
"""The line-level probe must reject partial or corrupted named-file reads."""
import unittest

from tools.iec_directory_probe import validate_file, validate_long_file, validate_short_file


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

    def test_rejects_wrong_multi_sector_bytes(self):
        data = bytearray(0x300)
        data[:6] = b'\x02\x00\x00\x00\x00\x02'
        data[10:13] = b'\x01\x00\x01'
        data[14:16] = b'\x03\x03'
        source = bytes(range(256)) * 2
        data[0x100:0x300] = source
        validate_long_file(bytes(data), source)
        data[0x201] ^= 1
        with self.assertRaises(ValueError):
            validate_long_file(bytes(data), source)

    def test_rejects_missing_eoi_on_short_file(self):
        from tools.iec_directory_probe import SHORT_FILE
        expected = SHORT_FILE.read_bytes()
        data = bytearray(0x200)
        data[:6] = bytes((2, 0, 1, 0, len(expected), 0))
        data[10:13] = b'\x01\x00\x01'
        data[14:16] = b'\x03\x03'
        data[0x100:0x100 + len(expected)] = expected
        validate_short_file(bytes(data))
        data[2] = 0
        with self.assertRaises(ValueError):
            validate_short_file(bytes(data))


if __name__ == '__main__':
    unittest.main()
