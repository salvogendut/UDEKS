# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EIO, EBADF, EBUSY, EEXIST, ENODEV, EINVAL, ENOSPC, EROFS = 5, 9, 16, 17, 19, 22, 28, 30


class CbmWrite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        output = Path(cls.temp.name)/'writer.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_IEC_WRITE', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/cbm_write.c'),
                        str(ROOT/'tests/fixtures/write_transport.c'), '-o', str(output)], check=True)
        cls.lib = c.CDLL(str(output))
        cls.lib.udeks_cbm_create.argtypes = [c.c_uint8, c.c_char_p, c.c_uint8]
        cls.lib.udeks_cbm_write.argtypes = [c.c_char_p, c.c_uint8]
        for name in ('udeks_cbm_create', 'udeks_cbm_write', 'udeks_cbm_write_close'):
            getattr(cls.lib, name).restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.lib.udeks_cbm_write_close()
        self.lib.test_reset()
        self.calls = (c.c_uint16*8).in_dll(self.lib, 'test_calls')
        self.filename = (c.c_uint8*22).in_dll(self.lib, 'udeks_iec_filename')

    def byte(self, name): return c.c_uint8.in_dll(self.lib, name)
    def word(self, name): return c.c_uint16.in_dll(self.lib, name)
    def create(self, name=b'NEWFILE', device=8):
        return self.lib.udeks_cbm_create(device, name, len(name))
    def write(self, data): return self.lib.udeks_cbm_write(data, len(data))
    def close(self): return self.lib.udeks_cbm_write_close()
    def status(self, values):
        data = (c.c_uint16*64).in_dll(self.lib, 'test_status')
        data[:len(values)] = values
        self.word('test_status_size').value = len(values)
    def dos(self, code): self.status([48+code//10, 48+code%10, 44, 269])

    def test_create_uses_exact_name_and_never_replace_syntax(self):
        for name in (b'A', b'MY FILE.TXT', b'1234567890123456'):
            before = self.calls[4]
            self.assertEqual(self.create(name), 0)
            length = self.byte('udeks_iec_filename_length').value
            self.assertEqual(bytes(self.filename[:length]), b'0:'+name+b',S,W')
            self.assertEqual(self.calls[4], before+1)
            self.assertEqual(self.close(), 0)

    def test_invalid_names_devices_and_null_do_not_touch_transport_or_filename(self):
        for name in (b'', b'A'*17, b'@A', b'A,W', b'A*', b'A?', b'A:B', b'A\0B',
                     b'A/B', b'\xc1', b'$', b'.', b'..', b'lowercase', b' A', b'A '):
            self.assertEqual(self.create(name), EINVAL)
        for device in (0, 7, 12, 255): self.assertEqual(self.create(device=device), EINVAL)
        self.assertEqual(self.lib.udeks_cbm_create(8, None, 1), EINVAL)
        self.assertEqual(list(self.calls), [0]*8)
        self.assertEqual(bytes(self.filename), b'Z'*22)
        self.assertEqual(self.byte('udeks_iec_filename_length').value, 0x5a)

    def test_second_create_preserves_live_writer(self):
        self.assertEqual(self.create(), 0)
        before, filename = list(self.calls), bytes(self.filename)
        self.assertEqual(self.create(b'OTHER', 9), EBUSY)
        self.assertEqual(list(self.calls), before)
        self.assertEqual(bytes(self.filename), filename)
        self.assertEqual(self.write(b'OK'), 0)
        self.assertEqual(self.close(), 0)

    def test_empty_file_still_checks_close(self):
        self.assertEqual(self.create(), 0)
        before = list(self.calls)
        self.assertEqual(self.lib.udeks_cbm_write(None, 0), 0)
        self.assertEqual(list(self.calls), before)
        self.assertEqual(self.close(), 0)
        self.assertEqual(self.calls[7], 1)
        self.assertEqual(self.calls[4], 2)
        self.assertEqual(self.word('test_finish_count').value, 1)

    def test_binary_chunks_no_encoding_no_added_newline_eoi_on_last_byte_only(self):
        for length in (1, 23, 24, 253, 254, 255, 256, 508, 515):
            self.lib.test_reset()
            self.assertEqual(self.create(), 0)
            data = bytes(i % 256 for i in range(length))
            expected = []
            for start in range(0, length, 24):
                chunk = data[start:start+24]
                self.assertEqual(self.write(chunk), 0)
                self.assertEqual(self.byte('udeks_cbm_written').value, len(chunk))
                expected.extend(list(chunk[:-1])+[chunk[-1]+256])
            values = (c.c_uint16*2048).in_dll(self.lib, 'test_values')
            self.assertEqual(list(values[:length]), expected)
            self.assertEqual(self.word('test_bytes').value, length)
            self.assertEqual(self.close(), 0)

    def test_bad_count_and_null_do_not_poison_writer(self):
        self.create(); before = list(self.calls)
        self.assertEqual(self.write(b'A'*25), EINVAL)
        self.assertEqual(self.lib.udeks_cbm_write(None, 1), EINVAL)
        self.assertEqual(list(self.calls), before)
        self.assertEqual(self.write(b'OK'), 0)
        self.assertEqual(self.close(), 0)

    def test_every_partial_failure_is_sticky_and_close_releases(self):
        for n in range(24):
            self.lib.test_reset(); self.create()
            self.word('test_fail_at').value = n
            self.assertEqual(self.write(bytes(range(24))), EIO)
            self.assertEqual(self.byte('udeks_cbm_written').value, n)
            before = list(self.calls)
            self.word('test_fail_at').value = 65535
            self.assertEqual(self.write(b'NOT RETRIED'), EIO)
            self.assertEqual(self.write(b''), EIO)
            self.assertEqual(self.byte('udeks_cbm_written').value, 0)
            self.assertEqual(list(self.calls), before)
            self.assertEqual(self.close(), EIO)
            self.assertEqual(self.create(b'NEXT'), 0)
            self.assertEqual(self.close(), 0)

    def test_dos_errors_are_meaningful_on_create_and_slot_is_reusable(self):
        for code, error in ((26, EROFS), (60, EBUSY), (62, 2), (63, EEXIST),
                            (70, EBUSY), (72, ENOSPC), (74, ENODEV), (25, EIO), (73, EIO)):
            self.dos(code)
            self.assertEqual(self.create(), error)
            self.assertEqual(self.close(), EBADF)
            self.dos(0)
            self.assertEqual(self.create(), 0)
            self.assertEqual(self.close(), 0)

    def test_dos_failure_after_acknowledged_bytes_is_not_durable_success(self):
        self.create(); self.dos(72)
        self.assertEqual(self.write(b'ABC'), ENOSPC)
        self.assertEqual(self.byte('udeks_cbm_written').value, 3)
        self.dos(0)
        self.assertEqual(self.close(), ENOSPC)

    def test_close_checks_flush_error_and_consumes_handle(self):
        for code, error in ((26, EROFS), (72, ENOSPC), (74, ENODEV)):
            self.dos(0); self.create(); self.write(b'ABC'); self.dos(code)
            self.assertEqual(self.close(), error)
            self.assertEqual(self.close(), EBADF)
            self.assertEqual(self.write(b'X'), EBADF)

    def test_transport_failures_release_on_failed_create(self):
        for code, error in ((2, EIO), (3, ENODEV)):
            self.byte('test_open_error').value = code
            before = self.word('test_finish_count').value
            self.assertEqual(self.create(), error)
            self.assertEqual(self.word('test_finish_count').value, before+1)
            self.byte('test_open_error').value = 0
            self.assertEqual(self.create(), 0); self.close()

    def test_listen_unlisten_status_and_untalk_failures_poison_until_close(self):
        for fault in ('test_listen_error', 'test_unlisten_error', 'test_status_error', 'test_untalk_error'):
            self.create(); self.byte(fault).value = 2
            self.assertEqual(self.write(b'ABC'), EIO)
            self.byte(fault).value = 0
            self.assertEqual(self.close(), EIO)

    def test_close_handshake_failure_cannot_be_hidden_by_ok_dos_status(self):
        self.create(); self.byte('test_close_error').value = 2
        self.assertEqual(self.close(), EIO)
        self.assertEqual(self.word('test_finish_count').value, 1)
        self.assertEqual(self.close(), EBADF)

    def test_malformed_status_is_bounded_never_success(self):
        for reply in ([48], [304], [48, 304], [48, 48, 300], [48, 48, 44, 266],
                      [48, 48, 59, 269], [65, 48, 44, 269], [48, 65, 44, 269],
                      [48, 48, 44, 512], [48, 48, 44]+[65]*61):
            self.lib.test_reset(); self.status(reply)
            self.assertEqual(self.create(), EIO)
            self.assertLessEqual(self.calls[5], 128)  # OPEN + cleanup status
            self.assertEqual(self.calls[6], 2)
            self.assertEqual(self.word('test_finish_count').value, 1)

    def test_no_handle_means_no_io(self):
        self.assertEqual(self.write(b'x'), EBADF)
        self.assertEqual(self.close(), EBADF)
        self.assertEqual(list(self.calls), [0]*8)


if __name__ == '__main__': unittest.main()
