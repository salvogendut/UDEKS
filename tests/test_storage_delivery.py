# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_storage import install_router, wrap_storage, install_bootfs
from build_bootfs import build_bootfs
from shadow_boot_probe import scheduler_installed_tail


class StorageDelivery(unittest.TestCase):
    def test_shadow_probe_decodes_all_secondary_envelopes(self):
        header = bytearray(b'USOV\0\3' + bytes(14))
        header[8:10] = (0x400).to_bytes(2, 'little')
        header[12:14] = (4).to_bytes(2, 'little')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'secondary.prg'
            for load, source in ((0x5000, 0x5000), (0x4200, 0x6000), (0x1200, 0x6000)):
                path.write_bytes(load.to_bytes(2, 'little') + bytes(source-load) +
                                 header + bytes(0x400) + b'TAIL')
                self.assertEqual(scheduler_installed_tail(path), b'TAIL')
            path.write_bytes(b'\0\x12bad')
            with self.assertRaises(ValueError): scheduler_installed_tail(path)

    def wrap(self, **overrides):
        args = dict(payload=b'\0\x42' + bytes(0x3000), constants='USOV = $6000\n',
                    module=b'\x4c\x09\x12UIEC\0\1', policy=b'P', driver=b'D',
                    ush=bytes(2121), lookup=b'\x4c\x09\x1aULKP\0\1')
        args.update(overrides)
        return wrap_storage(**args)

    def test_delivery_keeps_scheduler_cache_and_usov_bounds(self):
        payload, constants = self.wrap(policy=b'POLICY', driver=b'DRIVER')
        self.assertEqual(payload[2+0x1A03-0x1200:2+0x1A09-0x1200], b'ULKP\0\1')
        self.assertEqual(payload[:2], b'\0\x12')
        self.assertEqual(payload[2+0x8A00-0x1200:2+0x8A00-0x1200+6], b'POLICY')
        self.assertEqual(payload[2+0xE300-0x1200:2+0xE306-0x1200], b'DRIVER')
        self.assertEqual(payload[2+0xA000-0x1200:2+0xD100-0x1200], bytes(0x3100))
        self.assertEqual(len(payload), 2+0xE900-0x1200)
        self.assertIn('USOV = $6000\n', constants)
        self.assertIn('SECONDARY_PAYLOAD_LOAD = $1200', constants)
        self.assertIn('SECONDARY_PAYLOAD_END = $e900', constants)

    def test_secondary_bootfs_does_not_change_any_other_service_byte(self):
        payload, _ = self.wrap()
        offset = 2+0xA000-0x1200
        fs = build_bootfs([('ush', b'program'), ('mount', b'command')])
        result = install_bootfs(payload, fs)
        self.assertEqual(result[:offset], payload[:offset])
        self.assertEqual(result[offset:offset+0x3100], fs.ljust(0x3100, b'\0'))
        self.assertEqual(result[offset+0x3100:], payload[offset+0x3100:])
        self.assertEqual(len(result), len(payload))
        with self.assertRaises(ValueError): install_bootfs(result, fs)

    def test_secondary_bootfs_rejects_overflow_and_malformed_inputs(self):
        payload, _ = self.wrap()
        fs = build_bootfs([('ush', b'program')])
        for image, filesystem in ((payload[:-1], fs), (payload, b'bad'),
                                  (payload, fs+bytes(0x3100)),
                                  (payload, fs[:-1]),
                                  (b'\0\x13'+payload[2:], fs)):
            with self.assertRaises(ValueError): install_bootfs(image, filesystem)

    def test_oversized_or_missing_pieces_fail_closed(self):
        for changes in (dict(module=bytes(2049)), dict(module=b'bad'),
                        dict(lookup=b''), dict(lookup=bytes(1537)), dict(lookup=b'bad'),
                        dict(policy=bytes(1537)), dict(driver=bytes(1537)),
                        dict(policy=b''), dict(driver=b''),
                        dict(ush=bytes(0x1000-0x180+1)), dict(payload=b'\0\x41X'),
                        dict(payload=b'\0\x42'+bytes(0x3E01))):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError): self.wrap(**changes)

    def test_router_cannot_overwrite_scheduler_state_or_handler(self):
        tail = b'T'*0x6B9
        installed = install_router(tail, 0xC120, 0xC872, b'ROUTER')
        self.assertEqual(installed[:len(tail)], tail)
        self.assertEqual(installed[0xC880-0xC120:], b'ROUTER')
        for args in ((tail, 0xC120, 0xC880, b'R'),
                     (bytes(0x761), 0xC120, 0xC872, b'R'),
                     (tail, 0xC120, 0xC872, bytes(129)),
                     (tail, 0xC120, 0xC872, b'')):
            with self.assertRaises(ValueError): install_router(*args)

    def test_gateway_stays_below_transient_stack_and_owns_context(self):
        source = (ROOT/'src/services/filesystem/iec_router.s').read_text()
        self.assertIn('gateway_end-gateway <= $f700', source)
        self.assertIn('lda $02,x', source)
        self.assertIn('sta $02,x', source)
        self.assertIn('cpx #30', source)
        self.assertIn('sta $ff03', source)
        self.assertIn('sta $ff01', source)
        self.assertIn('#>$e200', source)
