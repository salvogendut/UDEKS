# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from test_window_repaint_policy import Rect, Window, Job, Work, Ticket, clone, fields

ROOT = Path(__file__).resolve().parents[1]
U8, U16 = C.c_uint8, C.c_uint16
OK, IDLE, INVALID, STALE, EXHAUSTED, YIELD = range(6)
CLEAR, SELECT, CHROME, CLIENT, RESTORE, COMMIT, FAILED = range(1, 8)


class Lane(C.Structure):
    _fields_ = [('current', Rect), ('pending', Rect), ('epoch', U16), ('cursor', U16),
                ('state', U8), ('selector', U8)]


class LaneTicket(C.Structure):
    _fields_ = [('epoch', U16), ('cursor', U16), ('phase', U8), ('selector', U8)]


class LaneWork(C.Structure):
    _fields_ = [('ticket', LaneTicket), ('clip', Rect)]


class RepaintLaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        lib = Path(cls.directory.name) / 'lane.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unknown-pragmas',
            '-shared', '-fPIC', '-I' + str(ROOT / 'include'),
            str(ROOT / 'src/services/window/repaint_lane.c'),
            str(ROOT / 'src/services/window/repaint_policy.c'), '-o', str(lib)], check=True)
        cls.lib = C.CDLL(str(lib))
        prototypes = {
            'udeks_repaint_init': ([C.POINTER(Job), U16], U8),
            'udeks_repaint_request': ([C.POINTER(Job), C.POINTER(Rect)], U8),
            'udeks_repaint_scene_changed': ([C.POINTER(Job), U16, C.POINTER(Rect)], U8),
            'udeks_repaint_abort': ([C.POINTER(Job)], U8),
            'udeks_repaint_peek': ([C.POINTER(Job), U16, C.POINTER(Window), U8, C.POINTER(Work)], U8),
            'udeks_repaint_validate': ([C.POINTER(Job), U16, C.POINTER(Ticket)], U8),
            'udeks_repaint_ack': ([C.POINTER(Job), U16, C.POINTER(Ticket), U8], U8),
            'udeks_lane_init': ([], None), 'udeks_lane_abort': ([], U8),
            'udeks_lane_request': ([C.POINTER(Rect)], U8), 'udeks_lane_changed': ([C.POINTER(Rect)], U8),
            'udeks_lane_peek': ([C.POINTER(Window), U8, C.POINTER(LaneWork)], U8),
            'udeks_lane_validate': ([C.POINTER(LaneTicket)], U8),
            'udeks_lane_ack': ([C.POINTER(LaneTicket), U8], U8),
        }
        for name, (args, ret) in prototypes.items():
            fn = getattr(cls.lib, name)
            fn.argtypes, fn.restype = args, ret

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.job = Job()
        self.lib.udeks_repaint_init(C.byref(self.job), 1)
        self.lib.udeks_lane_init()
        self.lane = Lane.in_dll(self.lib, 'udeks_repaint_lane')
        self.windows = [Window(Rect(10, 108, 10, 90), 1, 1, 1),
                        Window(Rect(50, 140, 40, 130), 2, 2, 3),
                        Window(Rect(270, 320, 160, 200), 4, 4, 0)]
        self.shadow = bytearray(64000)
        self.display = bytearray(64000)

    def equivalent(self):
        self.assertEqual(fields(self.lane.current), fields(self.job.current))
        self.assertEqual(fields(self.lane.pending), fields(self.job.pending))
        self.assertEqual(self.lane.epoch, self.job.generation)
        self.assertEqual(self.lane.cursor, self.job.cursor)
        self.assertEqual(self.lane.state & 7, self.job.phase)
        self.assertEqual(bool(self.lane.state & 8), bool(self.job.pending_valid))
        self.assertEqual(self.lane.selector & 7, self.job.handle)
        self.assertEqual(self.lane.selector >> 3, self.job.rank)

    def request(self, rect):
        pointer = C.byref(rect) if rect is not None else None
        old = bytes(self.lane), bytes(self.job)
        a = self.lib.udeks_lane_request(pointer)
        b = self.lib.udeks_repaint_request(C.byref(self.job), pointer)
        self.assertEqual(a, b)
        self.equivalent()
        if a == INVALID:
            self.assertEqual(old, (bytes(self.lane), bytes(self.job)))
        return a

    def changed(self, rect):
        pointer = C.byref(rect) if rect is not None else None
        a = self.lib.udeks_lane_changed(pointer)
        b = self.lib.udeks_repaint_scene_changed(C.byref(self.job), self.job.revision + 1, pointer)
        self.assertEqual(a, b)
        self.equivalent()
        return a

    def peek(self):
        scene = (Window * len(self.windows))(*self.windows)
        a, b = LaneWork(), Work()
        C.memset(C.byref(a), 0xA5, C.sizeof(a))
        C.memset(C.byref(b), 0xA5, C.sizeof(b))
        old_a, old_b = bytes(a), bytes(b)
        ra = self.lib.udeks_lane_peek(scene, len(scene), C.byref(a))
        rb = self.lib.udeks_repaint_peek(C.byref(self.job), self.job.revision, scene, len(scene), C.byref(b))
        self.assertEqual(ra, rb)
        self.equivalent()
        if ra == OK:
            self.assertEqual(fields(a.clip), fields(b.clip))
            self.assertEqual((a.ticket.epoch, a.ticket.cursor, a.ticket.phase,
                              a.ticket.selector >> 3, a.ticket.selector & 7),
                             (b.ticket.generation, b.ticket.cursor, b.ticket.phase, b.ticket.rank, b.ticket.handle))
        else:
            self.assertEqual((bytes(a), bytes(b)), (old_a, old_b))
        return ra, (a, b)

    def validate(self, pair):
        a, b = pair
        ra = self.lib.udeks_lane_validate(C.byref(a.ticket))
        rb = self.lib.udeks_repaint_validate(C.byref(self.job), self.job.revision, C.byref(b.ticket))
        self.assertEqual(ra, rb)
        return ra

    def ack(self, pair, result=0):
        a, b = pair
        ra = self.lib.udeks_lane_ack(C.byref(a.ticket), result)
        rb = self.lib.udeks_repaint_ack(C.byref(self.job), self.job.revision, C.byref(b.ticket), result)
        self.assertEqual(ra, rb)
        self.equivalent()
        return ra

    def pixel(self, window, x, y):
        l, r, t, b = fields(window.bounds)
        if l + 3 <= x < r - 3 and t + 14 <= y < b - 3:
            return int(((x - l) * 3 + (y - t) * 5 + window.handle) % 7 == 0)
        return int(x in (l, r - 1) or y in (t, t + 13, b - 1))

    def expected(self):
        pixels = bytearray(64000)
        for w in sorted(self.windows, key=lambda w: w.rank):
            if w.flags & 1:
                l, r, t, b = fields(w.bounds)
                for y in range(t, b):
                    for x in range(l, r):
                        pixels[y * 320 + x] = self.pixel(w, x, y)
        return pixels

    def step(self):
        status, pair = self.peek()
        if status != OK:
            return status
        self.assertEqual(self.validate(pair), OK)  # BEFORE pixels.
        work = pair[0]
        l, r, t, b = fields(work.clip)
        phase = work.ticket.phase
        result = 0
        if phase == CLEAR:
            self.assertLessEqual(b - t, 4)
            for y in range(t, b):
                self.shadow[y * 320 + l:y * 320 + r] = bytes(r - l)
        elif phase == COMMIT:
            # Model the VIC-II byte-interleaved page layout, one 256-byte page
            # per work record (last page 64 bytes), not a whole-frame commit.
            page = work.ticket.cursor
            self.assertLess(page, 32)
            for offset in range(page * 256, min((page + 1) * 256, 8000)):
                band, rest = divmod(offset, 320)
                column, row = divmod(rest, 8)
                y, x = band * 8 + row, column * 8
                start = y * 320 + x
                self.display[start:start + 8] = self.shadow[start:start + 8]
            result = int(page != 31)
        else:
            y = t + work.ticket.cursor
            self.assertLess(y, b)
            handle = work.ticket.selector & 7
            w = next(w for w in self.windows if w.handle == handle)
            for x in range(l, r):
                value = self.pixel(w, x, y)
                if phase == CHROME and w.bounds.left + 3 <= x < w.bounds.right - 3 and w.bounds.top + 14 <= y < w.bounds.bottom - 3:
                    value = 0
                self.shadow[y * 320 + x] = value
            result = int(y + 1 < b)
        self.assertEqual(self.ack(pair, result), OK)
        return OK

    def drain(self):
        for _ in range(5000):
            if self.step() == IDLE:
                return
        self.fail('continuation did not drain')

    def reach(self, phase):
        for _ in range(1000):
            status, pair = self.peek()
            if status == OK and pair[0].ticket.phase == phase:
                return pair
            self.step()
        self.fail('phase never reached')

    def test_full_canvas_work_and_progress_match_reference_including_one_page_commit(self):
        self.request(Rect(0, 320, 0, 200))
        self.drain()
        self.assertEqual(self.shadow, self.expected())
        self.assertEqual(self.display, self.shadow)

    def test_pending_request_does_not_change_active_receipt_or_current_extent(self):
        self.request(Rect(4, 80, 5, 45))
        _, pair = self.peek()
        current, cursor, epoch = fields(self.lane.current), self.lane.cursor, self.lane.epoch
        self.request(Rect(250, 320, 150, 200))
        self.request(Rect(200, 270, 130, 180))
        self.assertEqual((fields(self.lane.current), self.lane.cursor, self.lane.epoch), (current, cursor, epoch))
        self.assertEqual(fields(self.lane.pending), (200, 320, 130, 200))
        self.assertEqual(self.validate(pair), OK)
        self.ack(pair)
        self.assertEqual(self.ack(pair), STALE)
        self.drain()

    def test_changes_during_clear_chrome_client_restore_and_commit_revoke_before_drawing(self):
        for phase in (CLEAR, CHROME, CLIENT, RESTORE, COMMIT):
            self.setUp()
            self.request(Rect(0, 320, 0, 200))
            old = self.reach(phase)
            if phase != CLEAR:
                self.step()  # Let a partial stage, including commit, survive.
                _, old = self.peek()
            self.request(Rect(280, 320, 170, 200))
            self.changed(Rect(1, 160, 2, 140))
            # Destroy/reuse the selected handle and reorder a sparse scene.
            self.windows = [Window(Rect(2, 100, 4, 90), 2, 4, 1),
                            Window(Rect(130, 300, 80, 180), 1, 1, 1)]
            pixels = bytes(self.shadow), bytes(self.display)
            self.assertEqual(self.validate(old), STALE)
            self.assertEqual(self.ack(old), STALE)
            self.assertEqual(pixels, (bytes(self.shadow), bytes(self.display)))
            self.drain()
            self.assertEqual(self.shadow, self.expected())
            self.assertEqual(self.display, self.shadow)

    def test_empty_hidden_and_title_only_damage_match_reference(self):
        for windows, damage in (([], Rect(0, 320, 0, 200)),
            ([Window(Rect(0, 50, 0, 50), 1, 3, 0)], Rect(0, 50, 0, 50)),
            ([Window(Rect(0, 100, 0, 80), 4, 4, 1)], Rect(0, 100, 0, 14))):
            self.setUp()
            self.windows = windows
            self.request(damage)
            seen = []
            for _ in range(500):
                status, pair = self.peek()
                if status == IDLE:
                    break
                if status == OK:
                    seen.append(pair[0].ticket.phase)
                self.step()
            else:
                self.fail('empty/title repair did not finish')
            self.assertNotIn(CLIENT, seen)
            self.assertEqual(self.display, self.shadow)

    def test_reject_invalid_damage_and_records_atomically(self):
        for rect in (None, Rect(2, 2, 0, 10), Rect(0, 321, 0, 10), Rect(0, 20, 10, 201)):
            self.assertEqual(self.request(rect), INVALID)
            before = bytes(self.lane), bytes(self.job)
            self.assertEqual(self.changed(rect), INVALID)
            self.assertEqual(before, (bytes(self.lane), bytes(self.job)))
        self.request(Rect(0, 320, 0, 200))
        _, pair = self.peek()
        before = bytes(self.lane), bytes(self.job)
        self.assertEqual(self.ack(pair, 1), INVALID)  # CLEAR accepts DONE only.
        self.assertEqual(self.ack(pair, 2), INVALID)
        self.assertEqual(before, (bytes(self.lane), bytes(self.job)))
        for field in ('epoch', 'cursor', 'phase', 'selector'):
            ticket = clone(pair[0].ticket)
            setattr(ticket, field, getattr(ticket, field) + 1)
            self.assertEqual(self.lib.udeks_lane_validate(C.byref(ticket)), STALE)
            self.assertEqual(self.lib.udeks_lane_ack(C.byref(ticket), 0), STALE)
            self.assertEqual(bytes(self.lane), before[0])

    def test_abort_retires_receipts_and_epoch_cursor_exhaustion_never_wrap(self):
        self.request(Rect(0, 320, 0, 200))
        _, old = self.peek()
        self.assertEqual(self.lib.udeks_lane_abort(), self.lib.udeks_repaint_abort(C.byref(self.job)))
        self.equivalent()
        self.assertEqual(self.validate(old), STALE)
        self.assertEqual(self.peek()[0], IDLE)
        self.lane.epoch = self.job.generation = 65535
        self.request(Rect(0, 320, 0, 200))
        self.assertEqual(self.peek()[0], EXHAUSTED)
        self.assertEqual(self.request(Rect(0, 320, 0, 200)), EXHAUSTED)
        self.setUp()
        self.request(Rect(0, 320, 0, 200))
        self.reach(CHROME)
        self.lane.cursor = self.job.cursor = 65535
        _, pair = self.peek()
        self.assertEqual(self.ack(pair, 1), EXHAUSTED)
        self.assertEqual(self.lane.epoch, 0)
        self.assertEqual(self.lane.state & 7, FAILED)

    def test_seeded_queue_and_scene_changes_preserve_reference_trace_and_pixels(self):
        rng = random.Random(14)
        self.request(Rect(0, 320, 0, 200))
        self.drain()
        for _ in range(40):
            window = rng.choice(self.windows)
            old = clone(window.bounds)
            self.request(old)
            for _ in range(rng.randrange(1, 30)):
                self.step()
            width, height = old.right - old.left, old.bottom - old.top
            left, top = rng.randrange(321 - width), rng.randrange(201 - height)
            new = Rect(left, left + width, top, top + height)
            # Fence with old + new extent before changing any metadata.
            self.changed(Rect(min(old.left, new.left), max(old.right, new.right),
                              min(old.top, new.top), max(old.bottom, new.bottom)))
            window.bounds = new
            window.flags ^= 2
            self.windows.reverse()
            if rng.randrange(3) == 0:
                self.request(Rect(0, 320, 0, 200))
            self.drain()
            self.assertEqual(self.shadow, self.expected())
            self.assertEqual(self.display, self.shadow)


if __name__ == '__main__':
    unittest.main()
