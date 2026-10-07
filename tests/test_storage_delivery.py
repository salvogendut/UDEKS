# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_storage import install_router, wrap_storage, install_bootfs, USH_BSS
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
        self.assertEqual(payload[2+0xB000-0x1200:2+0xB000-0x1200+6], b'POLICY')
        self.assertEqual(payload[2+0xE300-0x1200:2+0xE306-0x1200], b'DRIVER')
        self.assertEqual(payload[2+0xA000-0x1200:2+0xB000-0x1200], bytes(0x1000))
        self.assertEqual(len(payload), 2+0xE900-0x1200)
        self.assertIn('USOV = $6000\n', constants)
        self.assertIn('SECONDARY_PAYLOAD_LOAD = $1200', constants)
        self.assertIn('SECONDARY_PAYLOAD_END = $e900', constants)

    def test_guarded_image_uses_boot_only_sources_without_growing_envelope(self):
        module=b'\x4c\x15\x12UIEC\0\3'
        installer=b'\x4c\x09\x32SINS\0\1\x60'
        args=dict(module=module, hidden=b'H'*0xefe, installer=installer)
        baseline,_=self.wrap()
        result,_=self.wrap(**args)
        self.assertEqual(len(result),len(baseline))
        start=2+0x2300-0x1200
        self.assertEqual(result[start:start+0xf00], b'H'*0xefe+b'\0\0')
        self.assertEqual(result[start+0xf00:start+0xf00+len(installer)],installer)
        self.assertEqual(result[start+0x1000:],baseline[start+0x1000:])
        for change in ({'hidden':b''},{'installer':b''},{'hidden':b'H'*0xf01},
                       {'installer':installer+bytes(0x100)},{'installer':b'bad'},
                       {'module':module[:8]+b'\1'}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                self.wrap(**(args|change))

    def test_secondary_bootfs_does_not_change_any_other_service_byte(self):
        payload, _ = self.wrap()
        offset = 2+0xA000-0x1200
        fs = build_bootfs([('ush', b'program'), ('mount', b'command')])
        result = install_bootfs(payload, fs)
        self.assertEqual(result[:offset], payload[:offset])
        self.assertEqual(result[offset:offset+0x1000], fs.ljust(0x1000, b'\0'))
        self.assertEqual(result[offset+0x1000:], payload[offset+0x1000:])
        self.assertEqual(len(result), len(payload))
        with self.assertRaises(ValueError): install_bootfs(result, fs)

    def test_banked_loader_uses_only_reserved_secondary_padding(self):
        baseline, constants = self.wrap()
        loader = b'\x4c\x09\xd9BLOD\0\1' + bytes(0x700-9)
        image, new_constants = self.wrap(banked_loader=loader)
        offset = 2+0xD900-0x1200
        self.assertEqual(image[:offset], baseline[:offset])
        self.assertEqual(image[offset:offset+0x700], loader)
        self.assertEqual(image[offset+0x700:], baseline[offset+0x700:])
        self.assertEqual(len(image), len(baseline))
        self.assertEqual(constants, new_constants)
        for bad in (loader+b'\0', b'bad', b'\0'+loader[1:],
                    loader[:3]+b'FAIL'+loader[7:]):
            with self.assertRaises(ValueError): self.wrap(banked_loader=bad)

    def test_graphics_delivery_cannot_overwrite_policy_or_retained_images(self):
        baseline, _ = self.wrap()
        module = b'G'*0x600
        image, _ = self.wrap(banked_graphics=module)
        offset = 2+0xc700-0x1200
        self.assertEqual(image[:offset], baseline[:offset])
        self.assertEqual(image[offset:offset+0x600], module)
        self.assertEqual(image[offset+0x600:], baseline[offset+0x600:])
        self.assertEqual(image[offset+0x600:offset+0x900], bytes(0x300))
        for changes in ({'banked_graphics':module[:-1]},
                        {'banked_graphics':module+b'G'},
                        {'banked_graphics':module,'policy':b'P'*0x1701}):
            with self.assertRaises(ValueError): self.wrap(**changes)

    def test_relocator_and_access_only_fill_service_slack(self):
        loader = b'\x4c\x09\xd9BLOD\0\1\x60'
        reloc = b'\x4c\x89\x18BREL\0\1' + bytes(0x180-9)
        access = b'\x4c\x09\x1fBACC\0\1' + bytes(0x100-9)
        baseline, constants = self.wrap(banked_loader=loader)
        image, updated = self.wrap(banked_loader=loader, banked_reloc=reloc,
                                   banked_access=access)
        expected = bytearray(baseline)
        for address, blob in ((0x1880, reloc), (0x1f00, access)):
            offset = 2 + address - 0x1200
            expected[offset:offset+len(blob)] = blob
        self.assertEqual(image, bytes(expected))
        self.assertEqual(updated, constants)
        self.assertEqual(image[2+0xd100-0x1200:2+0xd900-0x1200], bytes(0x800))
        args = dict(banked_loader=loader, banked_reloc=reloc, banked_access=access)
        for changes in ({'banked_reloc':b''}, {'banked_access':b''},
                        {'banked_loader':b''}, {'banked_reloc':reloc+b'\0'},
                        {'banked_access':access+b'\0'},
                        {'banked_reloc':b'\0'+reloc[1:]},
                        {'banked_access':access[:3]+b'FAIL'+access[7:]},
                        {'module':baseline[2:11]+bytes(0x681-9)},
                        {'lookup':b'\x4c\x09\x1aULKP\0\1'+bytes(0x501-9)}):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError): self.wrap(**(args | changes))

    def test_paths_delivery_exact_sizes_and_policy_boundary(self):
        graphics=b'G'*1792; paths=b'S'*1008
        baseline,_=self.wrap()
        payload,_=self.wrap(banked_graphics=graphics,retained_paths=paths)
        start=2+0xc600-0x1200
        self.assertEqual(payload[:start],baseline[:start])
        self.assertEqual(payload[start:start+2800],graphics+paths)
        self.assertEqual(payload[start+2800:],baseline[start+2800:])
        args=dict(banked_graphics=graphics,retained_paths=paths)
        self.wrap(**args,policy=b'P'*0x1600)
        for change in ({'policy':b'P'*0x1601},{'retained_paths':paths[:-1]},
                       {'retained_paths':paths+b'\0'},{'banked_graphics':b''}):
            with self.assertRaises(ValueError): self.wrap(**(args|change))

    def test_secondary_bootfs_rejects_overflow_and_malformed_inputs(self):
        payload, _ = self.wrap()
        fs = build_bootfs([('ush', b'program')])
        for image, filesystem in ((payload[:-1], fs), (payload, b'bad'),
                                  (payload, fs+bytes(0x1000)),
                                  (payload, fs[:-1]),
                                  (b'\0\x13'+payload[2:], fs)):
            with self.assertRaises(ValueError): install_bootfs(image, filesystem)

    def test_oversized_or_missing_pieces_fail_closed(self):
        for changes in (dict(module=bytes(2049)), dict(module=b'bad'),
                        dict(lookup=b''), dict(lookup=bytes(1537)), dict(lookup=b'bad'),
                        dict(policy=bytes(8193)), dict(driver=bytes(1537)),
                        dict(policy=b''), dict(driver=b''),
                        dict(ush=bytes(0x1000-USH_BSS+1)), dict(payload=b'\0\x41X'),
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
        source = (ROOT/'src/boot/stage1-gateway.s').read_text().split('storage_gate:',1)[1].split('.segment "BOOTINIT"',1)[0]
        self.assertIn('storage_gate = $fe20', source)
        self.assertIn('* <= $fe80', source)
        self.assertIn('lda $02,x', source)
        self.assertIn('sta $02,x', source)
        self.assertIn('cpx #30', source)
        self.assertIn('sta $ff03', source)
        self.assertIn('sta $ff01', source)
        self.assertIn('#>$e200', source)
