# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as C
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from reu_store_probe import decode

U8, U16 = C.c_uint8, C.c_uint16


class Object(C.Structure):
    _fields_ = [(n, U16) for n in ('owner', 'handle', 'size', 'received')] + [('state', U8)]


class State(C.Structure):
    _fields_ = [('objects', Object * 4), ('serial', U16), ('device', U8)]


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        library = Path(cls.tmp.name) / 'store.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/memory/reu_store.c'),
                        str(ROOT/'bench/reu/store_mock.c'), '-o', str(library)], check=True)
        cls.lib = C.CDLL(str(library))
        for name, args in {
            'init': [U8], 'begin': [U16, U16, C.POINTER(U16)],
            'write': [U16, U16, U16, C.POINTER(U8), U16],
            'read': [U16, U16, U16, C.POINTER(U8), U16],
            'commit': [U16, U16], 'release': [U16, U16], 'release_owner': [U16],
        }.items():
            fn = getattr(cls.lib, 'udeks_reu_store_'+name)
            fn.argtypes = args
            fn.restype = None if name == 'release_owner' else U8

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, name, *args):
        return getattr(self.lib, 'udeks_reu_store_'+name)(*args)

    def word(self, name):
        return C.c_uint.in_dll(self.lib, 'mock_'+name)

    def setUp(self):
        self.state = State.in_dll(self.lib, 'udeks_reu_store')
        C.memset(C.addressof(self.state), 0, C.sizeof(self.state))
        self.ram = (U8*32770).in_dll(self.lib, 'mock_ram')
        self.ram[:] = bytes((i*7+11)&255 for i in range(len(self.ram)))
        self.buffer = (U8*256)()
        for name in ('calls', 'fail', 'address', 'count'):
            self.word(name).value = 0
        U8.in_dll(self.lib, 'mock_partial').value = 0
        self.assertEqual(self.call('init', 2), 0)

    def begin(self, owner, size):
        handle = U16(0xaaaa)
        self.assertEqual(self.call('begin', owner, size, C.byref(handle)), 0)
        self.assertNotEqual(handle.value, 0)
        return handle.value

    def snapshot(self):
        return bytes(self.state), bytes(self.ram), bytes(self.buffer), self.word('calls').value

    def reject(self, expected, op, *args):
        before = self.snapshot()
        self.assertEqual(self.call(op, *args), expected)
        self.assertEqual(self.snapshot(), before)

    def upload(self, owner, handle, data, chunk=19):
        for at in range(0, len(data), chunk):
            part = data[at:at+chunk]
            self.buffer[:len(part)] = part
            self.assertEqual(self.call('write', owner, handle, at, self.buffer, len(part)), 0)
        self.assertEqual(self.call('commit', owner, handle), 0)

    def read(self, owner, handle, size, chunk=256):
        result = bytearray()
        for at in range(0, size, chunk):
            count = min(chunk, size-at)
            self.buffer[:] = bytes([0xcd]*256)
            self.assertEqual(self.call('read', owner, handle, at, self.buffer, count), 0)
            result.extend(self.buffer[:count])
            self.assertEqual(bytes(self.buffer[count:]), bytes([0xcd]*(256-count)))
        return bytes(result)

    def test_absent_and_supported_capacity_prefixes(self):
        for banks in (0, 2, 4, 8):
            self.assertEqual(self.call('init', banks), 0)
            handle = U16(0xbeef)
            if not banks:
                self.reject(19, 'begin', 1, 2000, C.byref(handle))
                self.assertEqual(handle.value, 0xbeef)
            else:
                self.assertEqual(self.call('begin', 1, 2000, C.byref(handle)), 0)
                self.assertEqual(self.call('release', 1, handle), 0)
        for banks in (1, 3, 5, 7, 9, 16, 255):
            self.reject(22, 'init', banks)

    def test_begin_rejection_is_atomic_including_output(self):
        result = U16(0xbeef)
        for owner, size in ((0, 1), (1, 0), (1, 8193), (1, 65535)):
            self.reject(22, 'begin', owner, size, C.byref(result))
            self.assertEqual(result.value, 0xbeef)
        self.reject(22, 'begin', 1, 1, None)
        self.begin(1, 2000)
        self.reject(16, 'begin', 1, 1, C.byref(result))
        self.reject(16, 'init', 0)
        self.reject(16, 'init', 8)

    def test_four_full_extents_exhaustion_and_stale_handle_reuse(self):
        preimage = bytes(self.ram)
        handles = [self.begin(owner, 8192) for owner in range(1, 5)]
        output = U16(0xbeef)
        self.reject(12, 'begin', 5, 1, C.byref(output))
        self.assertEqual(output.value, 0xbeef)
        for owner, handle in enumerate(handles, 1):
            data = bytes((owner*33+i)&255 for i in range(8192))
            self.upload(owner, handle, data, 256)
        for owner, handle in enumerate(handles, 1):
            self.assertEqual(self.read(owner, handle, 8192),
                             bytes((owner*33+i)&255 for i in range(8192)))
        self.assertEqual((self.ram[0], self.ram[-1]), (preimage[0], preimage[-1]))
        self.assertEqual(self.call('release', 2, handles[1]), 0)
        new = self.begin(2, 1)
        self.assertNotEqual(new, handles[1])
        for op in ('read', 'write'):
            self.reject(9, op, 2, handles[1], 0, self.buffer, 1)
        self.reject(9, 'commit', 2, handles[1])
        self.reject(9, 'release', 2, handles[1])
        self.reject(22, 'read', 2, new, 0, self.buffer, 1)
        self.upload(2, new, b'z')
        self.assertEqual(self.read(2, new, 1), b'z')
        # Reusing one extent did not compact/move or alter any peer extent.
        for owner in (1, 3, 4):
            self.assertEqual(self.read(owner, handles[owner-1], 8192),
                             bytes((owner*33+i)&255 for i in range(8192)))

    def test_clock160_plus_three_maximum_bitmap_objects(self):
        sizes = (2008, 5258, 5258, 5258)
        handles = [self.begin(i+1, size) for i, size in enumerate(sizes)]
        for i, size in enumerate(sizes):
            data = bytes((j*13+i*23)&255 for j in range(size))
            self.upload(i+1, handles[i], data)  # same 19-byte stream as UTRQ
        for i, size in enumerate(sizes):
            self.assertEqual(self.read(i+1, handles[i], size, 30),
                             bytes((j*13+i*23)&255 for j in range(size)))

    def test_pending_visibility_sequential_upload_and_bounds(self):
        handle = self.begin(7, 257)
        self.reject(22, 'read', 7, handle, 0, self.buffer, 1)
        self.reject(22, 'commit', 7, handle)
        for at, count in ((0, 0), (0, 257), (1, 1), (65535, 2)):
            self.reject(22, 'write', 7, handle, at, self.buffer, count)
        self.reject(22, 'write', 7, handle, 0, None, 1)
        self.assertEqual(self.call('write', 7, handle, 0, self.buffer, 256), 0)
        self.reject(22, 'write', 7, handle, 0, self.buffer, 1)
        self.reject(22, 'write', 7, handle, 256, self.buffer, 2)
        self.assertEqual(self.call('write', 7, handle, 256, self.buffer, 1), 0)
        self.reject(22, 'read', 7, handle, 0, self.buffer, 1)
        self.assertEqual(self.call('commit', 7, handle), 0)
        self.reject(22, 'commit', 7, handle)
        self.reject(22, 'write', 7, handle, 257, self.buffer, 1)
        for at, count in ((0, 0), (0, 257), (257, 1), (256, 2), (65535, 2)):
            self.reject(22, 'read', 7, handle, at, self.buffer, count)
        self.reject(22, 'read', 7, handle, 0, None, 1)
        self.assertEqual(self.call('read', 7, handle, 1, self.buffer, 256), 0)

    def test_foreign_owner_and_zero_or_unknown_handles(self):
        handle = self.begin(1, 1)
        for owner, token in ((0, handle), (2, handle), (1, 0), (1, 65535)):
            for op in ('write', 'read'):
                self.reject(9, op, owner, token, 0, self.buffer, 1)
            for op in ('commit', 'release'):
                self.reject(9, op, owner, token)

    def test_owner_retirement_clears_pending_and_ready_and_preserves_peers(self):
        first = self.begin(1, 1)
        second = self.begin(2, 1)
        self.upload(2, second, b'q')
        third = self.begin(3, 1)
        for owner in (0, 4, 65535):
            before = self.snapshot()
            self.call('release_owner', owner)
            self.assertEqual(self.snapshot(), before)
        for owner, token in ((1, first), (2, second)):
            self.call('release_owner', owner)
            self.assertEqual(bytes(self.state.objects[owner-1]), bytes(C.sizeof(Object)))
            self.reject(9, 'release', owner, token)
        self.assertEqual(self.state.objects[2].handle, third)
        self.upload(3, third, b'r')
        self.assertEqual(self.read(3, third, 1), b'r')

    def test_failed_dma_never_publishes_or_advances_and_requires_full_cleanup(self):
        for partial in (0, 1):
            for fail_at in range(1, 33):
                with self.subTest(partial=partial, call=fail_at):
                    self.setUp()
                    peer = self.begin(2, 1)
                    self.upload(2, peer, b'p')
                    handle = self.begin(1, 8192)
                    calls = self.word('calls').value
                    self.word('fail').value = calls + fail_at
                    U8.in_dll(self.lib, 'mock_partial').value = partial
                    for at in range(0, 8192, 256):
                        self.buffer[:] = bytes([0xee]*256)
                        error = self.call('write', 1, handle, at, self.buffer, 256)
                        if error:
                            self.assertEqual(error, 5)
                            self.assertEqual(self.state.objects[1].received, at)
                            break
                    else:
                        self.fail('injected DMA error not observed')
                    self.assertEqual(self.state.device, 2)
                    self.reject(5, 'write', 1, handle, at, self.buffer, 256)
                    self.reject(5, 'read', 2, peer, 0, self.buffer, 1)
                    self.reject(16, 'init', 8)
                    self.call('release_owner', 1)
                    self.reject(16, 'init', 8)
                    self.call('release_owner', 2)
                    self.assertEqual(self.call('init', 8), 0)
                    fresh = self.begin(1, 1)
                    self.assertNotEqual(fresh, handle)
                    self.upload(1, fresh, b'n')

    def test_read_failure_stops_store_and_cannot_commit_other_completed_upload(self):
        ready = self.begin(1, 256)
        self.upload(1, ready, bytes([0xee]*256), 256)
        pending = self.begin(2, 1)
        self.assertEqual(self.call('write', 2, pending, 0, self.buffer, 1), 0)
        self.word('fail').value = self.word('calls').value + 1
        U8.in_dll(self.lib, 'mock_partial').value = 1
        self.buffer[:] = bytes(256)
        self.assertEqual(self.call('read', 1, ready, 0, self.buffer, 256), 5)
        self.assertEqual(bytes(self.buffer), bytes([0xee]*128)+bytes(128))
        self.reject(5, 'commit', 2, pending)
        self.reject(5, 'read', 1, ready, 0, self.buffer, 1)
        out = U16(0xbeef)
        self.reject(5, 'begin', 3, 1, C.byref(out))
        self.assertEqual(out.value, 0xbeef)

    def test_handle_exhaustion_never_wraps_even_after_init(self):
        self.state.serial = 65534
        handle = self.begin(65535, 1)
        self.assertEqual(handle, 65535)
        self.call('release_owner', 65535)
        self.assertEqual(self.call('init', 2), 0)
        out = U16(0xbeef)
        self.reject(12, 'begin', 1, 1, C.byref(out))
        self.assertEqual(out.value, 0xbeef)

    def test_random_owner_lifecycles_match_byte_oracle(self):
        rng = random.Random(128)
        live = {}
        stale = []
        for _ in range(1000):
            owner = rng.randrange(1, 7)
            if owner not in live:
                size = rng.choice((1, 19, 257, 2008, 5258, 8192))
                if len(live) == 4:
                    self.reject(12, 'begin', owner, size, C.byref(U16()))
                else:
                    live[owner] = (self.begin(owner, size), rng.randbytes(size), False)
                continue
            handle, payload, ready = live[owner]
            if rng.randrange(3) == 0:
                self.call('release_owner', owner)
                del live[owner]
                stale.append((owner, handle))
            elif not ready:
                self.upload(owner, handle, payload, rng.choice((1, 19, 255, 256)))
                live[owner] = handle, payload, True
            else:
                self.assertEqual(self.read(owner, handle, len(payload)), payload)
            if stale:
                old_owner, old_handle = rng.choice(stale)
                self.reject(9, 'read', old_owner, old_handle, 0, self.buffer, 1)


class StoreRecordTests(unittest.TestCase):
    @staticmethod
    def record(banks):
        record = bytearray(32)
        record[:10] = b'RSTQ\x01\x02\x00'+bytes((banks, min(banks, 8), 7 if banks else 1))
        if banks:
            record[10:14] = bytes.fromhex('45070180')  # 1861 calls, 32769 bytes
            record[14:19] = bytes((14, 1, 2, 6, 0))
        else:
            record[14] = 1
        record[19] = 39
        return record

    def test_strict_coverage_including_all_reserved_bytes(self):
        for banks in (0, 2, 4, 8, 16):
            self.assertEqual(decode(self.record(banks), banks)['offered_kib'], 32 if banks else 0)
            for offset in range(32):
                raw = self.record(banks)
                raw[offset] ^= 1
                with self.subTest(banks=banks, byte=offset), self.assertRaises(ValueError):
                    decode(raw, banks)

    def test_invalid_size_config_and_negative_record(self):
        for raw, banks in ((bytes(31), 2), (bytes(33), 2), (self.record(2), 4),
                           (self.record(1), 1), (b'RSTQ\x01\x80\x09'+bytes(25), 8)):
            with self.assertRaises(ValueError):
                decode(raw, banks)

    def test_preserved_evidence_and_current_source_binding(self):
        folder = ROOT/'bench/results/2026-10-09-reu-store'
        report = json.loads((folder/'report.json').read_text())
        for name, expected in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected, name)
        for name, expected in report['artifact_sha256'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), expected, name)
        self.assertEqual([r['case'] for r in report['records']],
                         ['vice-0', 'vice-128', 'vice-256', 'vice-512', 'vice-1024', 'corrupt-read'])
        for item in report['records']:
            raw = (folder/(item['case']+'.bin')).read_bytes()
            self.assertEqual(raw.hex(), item['raw'])
            if item['case'] == 'corrupt-read':
                self.assertEqual(raw[:7], b'RSTQ\x01\x80\x09')
                with self.assertRaises(ValueError):
                    decode(raw, 8)
            else:
                self.assertEqual(decode(raw, int(item['case'].split('-')[1])//64), item['decoded'])
        listed = set()
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            expected, name = line.split('  ', 1)
            self.assertNotIn(name, listed)
            listed.add(name)
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), expected, name)
        self.assertEqual(listed, {p.name for p in folder.iterdir()
                                 if p.suffix in ('.prg', '.map', '.bin', '.json', '.log')})


if __name__ == '__main__':
    unittest.main()
