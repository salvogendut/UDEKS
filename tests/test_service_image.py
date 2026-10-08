# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from service_image import HEADER_SIZE, TIME_BASE, TIME_LIMIT, checksum, seal, validate


def candidate():
    image = bytearray(80)
    image[:8] = b'USVM\x00\x01\x04\x01'
    struct.pack_into('<7H', image, 8, TIME_BASE, len(image), 10, 0, 0, 1, TIME_BASE+48)
    image[32:42] = b'USVC\x00\x01\x04\x01\x00\x10'
    struct.pack_into('<3H', image, 42, TIME_BASE+51, TIME_BASE+54, TIME_BASE+57)
    image[48:] = b'\x60'*32
    return bytearray(seal(image))


class ServiceImageTests(unittest.TestCase):
    def rejected(self, image, pattern):
        before = bytes(image)
        with self.assertRaisesRegex(ValueError, pattern):
            validate(image)
        self.assertEqual(bytes(image), before)

    def test_accepts_complete_bounded_image_without_mutation(self):
        image = candidate(); before = bytes(image)
        record = validate(image)
        self.assertEqual((record['allocation'], record['revision']), (90, 1))
        self.assertEqual(record['spare'], TIME_LIMIT-TIME_BASE-90)
        self.assertEqual(bytes(image), before)

    def test_all_truncated_headers_rejected(self):
        for n in range(HEADER_SIZE):
            with self.subTest(n=n): self.rejected(candidate()[:n], 'truncated')

    def test_format_identity_and_descriptor_bytes(self):
        for offset in (*range(8), *range(32,42)):
            image=candidate(); image[offset]^=0x80
            with self.subTest(offset=offset): self.rejected(image, 'format|identity|descriptor')

    def test_all_reserved_bytes_rejected(self):
        for offset in (14,15,*range(22,32)):
            image=candidate(); image[offset]=1
            with self.subTest(offset=offset): self.rejected(image, 'reserved')

    def test_wrong_load_address_and_size(self):
        for offset,value in ((8,TIME_BASE-1),(8,TIME_BASE+1),(10,79),(10,81),(10,0)):
            image=candidate(); struct.pack_into('<H',image,offset,value)
            with self.subTest(offset=offset,value=value): self.rejected(image, 'placement|size')

    def test_trailing_and_missing_bytes_are_not_silently_accepted(self):
        self.rejected(candidate()+b'\0','size')
        self.rejected(candidate()[:-1],'size')

    def test_bss_exact_boundary_accepted_and_overflow_rejected(self):
        image=candidate(); struct.pack_into('<H',image,12,TIME_LIMIT-TIME_BASE-len(image))
        self.assertEqual(validate(seal(image))['spare'],0)
        struct.pack_into('<H',image,12,TIME_LIMIT-TIME_BASE-len(image)+1)
        self.rejected(image,'reservation')
        struct.pack_into('<H',image,12,0xffff)
        self.rejected(image,'reservation')

    def test_every_vector_must_target_emitted_code_not_header_or_bss(self):
        for offset in (20,42,44,46):
            for entry in (0,TIME_BASE-1,TIME_BASE,TIME_BASE+47,TIME_BASE+80,0xffff):
                image=candidate(); struct.pack_into('<H',image,offset,entry)
                with self.subTest(offset=offset,entry=entry): self.rejected(image,'entry')

    def test_zero_revision_rejected(self):
        image=candidate(); image[18:20]=b'\0\0'
        self.rejected(image,'revision')

    def test_corrupt_payload_and_checksum_rejected(self):
        for offset in (16,17,48,79):
            image=candidate(); image[offset]^=1
            with self.subTest(offset=offset): self.rejected(image,'checksum')

    def test_checksum_excludes_only_its_own_word(self):
        image=candidate(); value=checksum(image)
        image[16:18]=b'\xff\xff'
        self.assertEqual(checksum(image),value)
        image[18]+=1
        self.assertEqual(checksum(image),(value+1)&0xffff)

    def test_invalid_reservation_rejected(self):
        for base,limit in ((-1,0xffff),(0x1000,0x1000),(0x1001,0x1000),(0,0x10001)):
            with self.subTest(base=base,limit=limit), self.assertRaisesRegex(ValueError,'reservation'):
                validate(candidate(),base=base,limit=limit)

    def test_standalone_runtime_uses_published_zp_without_kernel_code_bridge(self):
        runtime=(ROOT/'src/services/time/runtime.s').read_text()
        for line in ('sp = $06','sreg = $08','ptr1 = $0e','tmp1 = $16','regbank = $1a'):
            self.assertIn(line,runtime)
        self.assertNotIn('.import',runtime)
        build=(ROOT/'tools/build_time_module.py').read_text()
        self.assertNotIn('udeks-8502.map',build)
        self.assertIn("'-t', 'none'",build)

    def test_boot_does_not_install_unqualified_candidate(self):
        make=(ROOT/'mk/services.mk').read_text()
        self.assertNotRegex(make,r'(?m)^boot:')
        self.assertIn('not a dependency of normal boot',make)
        self.assertIn('BASELINE resident',(ROOT/'cfg/8502-time-module.cfg').read_text())


if __name__ == '__main__': unittest.main()
