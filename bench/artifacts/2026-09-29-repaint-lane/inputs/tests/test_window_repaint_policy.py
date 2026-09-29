# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
U8, U16 = C.c_uint8, C.c_uint16
OK, IDLE, INVALID, STALE, EXHAUSTED, YIELD = range(6)
CLEAR, SELECT, CHROME, CLIENT, RESTORE, COMMIT, FAILED = range(1, 8)


class Rect(C.Structure):
    _fields_ = [('left', U16), ('right', U16), ('top', U8), ('bottom', U8)]


class Window(C.Structure):
    _fields_ = [('bounds', Rect), ('handle', U8), ('rank', U8), ('flags', U8)]


class Job(C.Structure):
    _fields_ = [('current', Rect), ('pending', Rect), ('generation', U16), ('revision', U16),
                ('cursor', U16), ('phase', U8), ('rank', U8), ('handle', U8), ('pending_valid', U8)]


class Ticket(C.Structure):
    _fields_ = [('generation', U16), ('revision', U16), ('cursor', U16),
                ('phase', U8), ('rank', U8), ('handle', U8)]


class Work(C.Structure):
    _fields_ = [('ticket', Ticket), ('clip', Rect)]


def fields(rect):
    return rect.left, rect.right, rect.top, rect.bottom


def clone(value):
    return type(value).from_buffer_copy(bytes(value))


class WindowRepaintPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        library = Path(cls.directory.name) / 'policy.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-I' + str(ROOT / 'include'), str(ROOT / 'src/services/window/repaint_policy.c'),
                        '-o', str(library)], check=True)
        cls.lib = C.CDLL(str(library))
        signatures = {
            'init': [C.POINTER(Job), U16], 'request': [C.POINTER(Job), C.POINTER(Rect)],
            'scene_changed': [C.POINTER(Job), U16, C.POINTER(Rect)], 'abort': [C.POINTER(Job)],
            'peek': [C.POINTER(Job), U16, C.POINTER(Window), U8, C.POINTER(Work)],
            'validate': [C.POINTER(Job), U16, C.POINTER(Ticket)],
            'ack': [C.POINTER(Job), U16, C.POINTER(Ticket), U8],
        }
        for name, args in signatures.items():
            fn = getattr(cls.lib, 'udeks_repaint_' + name)
            fn.argtypes, fn.restype = args, U8

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.job = Job()
        self.assertEqual(self.lib.udeks_repaint_init(C.byref(self.job), 1), OK)
        self.windows = [Window(Rect(10, 108, 10, 90), 1, 1, 1),
                        Window(Rect(50, 140, 40, 130), 2, 2, 3),
                        Window(Rect(280, 320, 160, 200), 4, 4, 0)]
        self.shadow = bytearray(320 * 200)
        self.screen = bytearray(320 * 200)
        self.drawn = []

    def request(self, rect):
        return self.lib.udeks_repaint_request(C.byref(self.job), C.byref(rect))

    def change(self, rect, revision=None):
        return self.lib.udeks_repaint_scene_changed(C.byref(self.job),
            self.job.revision + 1 if revision is None else revision, C.byref(rect))

    def peek(self, windows=None, revision=None):
        windows = self.windows if windows is None else windows
        array = (Window * len(windows))(*windows)
        work = Work()
        status = self.lib.udeks_repaint_peek(C.byref(self.job),
            self.job.revision if revision is None else revision, array, len(windows), C.byref(work))
        return status, work

    def ack(self, work, result=0, revision=None):
        return self.lib.udeks_repaint_ack(C.byref(self.job),
            self.job.revision if revision is None else revision, C.byref(work.ticket), result)

    def validate(self, work):
        return self.lib.udeks_repaint_validate(C.byref(self.job), self.job.revision, C.byref(work.ticket))

    def pixel(self, window, x, y, client=True):
        l, r, t, b = fields(window.bounds)
        if l + 3 <= x < r - 3 and t + 14 <= y < b - 3:
            return int(client and ((x - l) * 3 + (y - t) * 5 + window.handle) % 7 == 0)
        return int(x in (l, r - 1) or y in (t, t + 13, b - 1))

    def expected(self):
        pixels = bytearray(320 * 200)
        for window in sorted(self.windows, key=lambda w: w.rank):
            if not window.flags & 1:
                continue
            l, r, t, b = fields(window.bounds)
            for y in range(t, b):
                for x in range(l, r):
                    pixels[y * 320 + x] = self.pixel(window, x, y)
        return pixels

    def render(self, work):
        self.assertEqual(self.validate(work), OK)  # Required before changing pixels.
        phase = work.ticket.phase
        l, r, t, b = fields(work.clip)
        self.drawn.append((phase, work.ticket.handle, l, r, t, b))
        if phase == CLEAR:
            self.assertLessEqual(b - t, 4)
            for y in range(t, b):
                self.shadow[y * 320 + l:y * 320 + r] = bytes(r - l)
            result = 0
        else:
            y = t + work.ticket.cursor
            self.assertLess(y, b)
            if phase == COMMIT:
                self.screen[y * 320 + l:y * 320 + r] = self.shadow[y * 320 + l:y * 320 + r]
            else:
                window = next(w for w in self.windows if w.handle == work.ticket.handle)
                for x in range(l, r):
                    self.shadow[y * 320 + x] = self.pixel(window, x, y, phase != CHROME)
            result = int(y + 1 < b)  # Modern mock backend: one row per step.
        self.assertEqual(self.ack(work, result), OK)

    def drive(self):
        for _ in range(2000):
            status, work = self.peek()
            if status == IDLE:
                self.assertEqual(self.job.phase, 0)
                self.assertFalse(self.job.pending_valid)
                return
            if status == YIELD:
                self.assertEqual(self.job.phase, SELECT)
            else:
                self.assertEqual(status, OK)
                self.render(work)
        self.fail('continuation did not converge')

    def reach(self, phase):
        for _ in range(1000):
            status, work = self.peek()
            if status == YIELD:
                continue
            self.assertEqual(status, OK)
            if work.ticket.phase == phase:
                return work
            self.render(work)
        self.fail('phase not reached')

    def test_initialization_and_invalid_requests_are_atomic(self):
        original = bytes(self.job)
        self.assertEqual(self.lib.udeks_repaint_init(C.byref(self.job), 0), INVALID)
        self.assertEqual(bytes(self.job), original)
        self.assertEqual(self.lib.udeks_repaint_init(None, 1), INVALID)
        for rect in (Rect(0, 0, 0, 1), Rect(0, 321, 0, 1), Rect(0, 1, 10, 10),
                     Rect(0, 1, 0, 201), Rect(65535, 1, 0, 1)):
            self.assertEqual(self.request(rect), INVALID)
            self.assertEqual(bytes(self.job), original)
        self.assertEqual(self.lib.udeks_repaint_request(C.byref(self.job), None), INVALID)

    def test_pending_damage_is_coalesced_without_changing_the_active_clip(self):
        self.assertEqual(self.request(Rect(20, 40, 30, 50)), OK)
        self.assertEqual(self.request(Rect(10, 30, 10, 35)), OK)
        self.assertEqual(fields(self.job.pending), (10, 40, 10, 50))
        _, work = self.peek()
        current, ticket = bytes(self.job.current), bytes(work.ticket)
        self.assertEqual(self.request(Rect(300, 320, 190, 200)), OK)
        self.assertEqual(bytes(self.job.current), current)
        self.assertEqual(bytes(self.peek()[1].ticket), ticket)
        self.assertEqual(fields(self.job.pending), (300, 320, 190, 200))

    def test_clear_is_at_most_four_rows_repeatable_and_rejects_old_receipts(self):
        self.request(Rect(0, 320, 197, 200))
        status, work = self.peek()
        self.assertEqual(status, OK)
        self.assertEqual(fields(work.clip), (0, 320, 197, 200))
        self.assertEqual(bytes(work), bytes(self.peek()[1]))
        before = bytes(self.job)
        self.assertEqual(self.ack(work, 1), INVALID)
        self.assertEqual(bytes(self.job), before)
        self.assertEqual(self.ack(work), OK)
        self.assertEqual(self.ack(work), STALE)

    def test_invalid_scene_or_wrong_revision_does_not_consume_work(self):
        self.request(Rect(0, 320, 0, 200))
        for mutate in (lambda w: setattr(w, 'flags', 4), lambda w: setattr(w, 'handle', 0),
                       lambda w: setattr(w, 'rank', 0), lambda w: setattr(w.bounds, 'right', 321)):
            windows = [clone(w) for w in self.windows]
            mutate(windows[0])
            before = bytes(self.job)
            self.assertEqual(self.peek(windows)[0], INVALID)
            self.assertEqual(bytes(self.job), before)
        for field in ('rank', 'handle'):
            windows = [clone(w) for w in self.windows]
            setattr(windows[1], field, getattr(windows[0], field))
            self.assertEqual(self.peek(windows)[0], INVALID)
        before = bytes(self.job)
        self.assertEqual(self.peek(revision=2)[0], STALE)
        self.assertEqual(bytes(self.job), before)

    def test_ticket_identity_and_result_are_checked_before_progress(self):
        self.request(Rect(0, 320, 0, 200))
        _, work = self.peek()
        before = bytes(self.job)
        for field, _ in Ticket._fields_:
            bad = clone(work)
            setattr(bad.ticket, field, getattr(bad.ticket, field) + 1)
            self.assertEqual(self.ack(bad), STALE, field)
            self.assertEqual(bytes(self.job), before)
        self.assertEqual(self.ack(work, 2), INVALID)
        self.assertEqual(bytes(self.job), before)

    def test_rejected_peek_leaves_the_output_record_and_job_untouched(self):
        self.request(Rect(0, 320, 0, 200))
        work = Work()
        C.memset(C.byref(work), 0xA5, C.sizeof(work))
        before, output = bytes(self.job), bytes(work)
        array = (Window * len(self.windows))(*self.windows)
        for revision, count, pointer in ((2, 3, array), (1, 5, array), (1, 1, None)):
            status = self.lib.udeks_repaint_peek(C.byref(self.job), revision, pointer, count, C.byref(work))
            self.assertIn(status, (INVALID, STALE))
            self.assertEqual(bytes(self.job), before)
            self.assertEqual(bytes(work), output)
        self.assertEqual(self.lib.udeks_repaint_peek(C.byref(self.job), 1, array, 3, None), INVALID)
        self.assertEqual(bytes(self.job), before)

    def test_more_advances_only_the_current_stage_and_fences_old_cursor(self):
        self.request(Rect(0, 320, 0, 200))
        work = self.reach(CLIENT)
        self.assertEqual(self.ack(work, 1), OK)
        self.assertEqual(self.job.phase, CLIENT)
        self.assertEqual(self.job.cursor, 1)
        before = bytes(self.job)
        self.assertEqual(self.ack(work), STALE)
        self.assertEqual(bytes(self.job), before)

    def test_scene_change_requeues_active_pending_and_new_damage(self):
        self.request(Rect(20, 50, 30, 70))
        _, old = self.peek()
        self.request(Rect(100, 130, 0, 10))
        self.assertEqual(self.change(Rect(300, 320, 190, 200)), OK)
        self.assertEqual(fields(self.job.pending), (20, 320, 0, 200))
        self.assertEqual(self.validate(old), STALE)
        before = bytes(self.job)
        self.assertEqual(self.ack(old), STALE)
        self.assertEqual(bytes(self.job), before)

    def test_same_revision_or_invalid_change_is_atomic(self):
        self.request(Rect(0, 320, 0, 200))
        self.peek()
        for revision, damage in ((1, Rect(0, 1, 0, 1)), (0, Rect(0, 1, 0, 1)),
                                 (2, Rect(0, 0, 0, 1))):
            before = bytes(self.job)
            self.assertEqual(self.change(damage, revision), INVALID)
            self.assertEqual(bytes(self.job), before)

    def test_abort_retires_tickets_and_pending_for_surface_shutdown(self):
        self.request(Rect(0, 320, 0, 200))
        old = self.reach(CLIENT)
        self.request(Rect(0, 10, 0, 10))
        self.assertEqual(self.lib.udeks_repaint_abort(C.byref(self.job)), OK)
        self.assertEqual((self.job.phase, self.job.handle, self.job.pending_valid), (0, 0, 0))
        self.assertEqual(self.validate(old), STALE)
        self.assertEqual(self.peek()[0], IDLE)

    def test_generations_do_not_wrap_or_alias_after_exhaustion(self):
        self.request(Rect(0, 320, 0, 200))
        self.job.generation = 65534
        old = self.reach(CLIENT)
        self.assertEqual(old.ticket.generation, 65535)
        self.assertEqual(self.change(Rect(0, 1, 0, 1)), EXHAUSTED)
        self.assertEqual((self.job.phase, self.job.generation, self.job.handle), (FAILED, 0, 0))
        self.assertEqual(self.validate(old), EXHAUSTED)
        self.assertEqual(self.peek()[0], EXHAUSTED)
        self.assertEqual(self.request(Rect(0, 1, 0, 1)), EXHAUSTED)

    def test_cursor_exhaustion_retires_the_job_instead_of_repeating_a_receipt(self):
        self.request(Rect(0, 320, 0, 200))
        self.reach(CLIENT)
        self.job.cursor = 65535
        _, old = self.peek()
        self.assertEqual(self.ack(old, 1), EXHAUSTED)
        self.assertEqual(self.validate(old), EXHAUSTED)

    def test_progressive_full_canvas_matches_reference_with_retained_top_window(self):
        self.windows.reverse()  # Rank, not array order, owns stacking.
        self.request(Rect(0, 320, 0, 200))
        self.drive()
        self.assertEqual(self.shadow, self.expected())
        self.assertEqual(self.screen, self.expected())
        self.assertFalse(any(h == 4 for _, h, *_ in self.drawn))
        self.assertFalse(any(p in (CHROME, CLIENT) and h == 2 for p, h, *_ in self.drawn))
        self.assertTrue(any(p == RESTORE and h == 2 for p, h, *_ in self.drawn))

    def test_partial_damage_and_damage_queued_during_a_job_converge(self):
        self.request(Rect(0, 320, 0, 200))
        self.drive()
        self.request(Rect(15, 80, 16, 60))
        work = self.reach(CLIENT)
        self.request(Rect(0, 320, 0, 200))
        self.render(work)
        self.drive()
        self.assertEqual(self.screen, self.expected())

    def test_title_only_damage_skips_client_but_not_commit(self):
        self.request(Rect(10, 108, 10, 20))
        self.drive()
        self.assertFalse(any(p == CLIENT for p, *_ in self.drawn))
        self.assertTrue(any(p == COMMIT for p, *_ in self.drawn))

    def test_empty_scene_clears_and_commits_damage_without_callbacks(self):
        self.windows = []
        self.shadow[:] = self.screen[:] = bytes([1]) * 64000
        self.request(Rect(0, 320, 0, 200))
        self.drive()
        self.assertEqual(self.screen, bytes(64000))
        self.assertEqual({p for p, *_ in self.drawn}, {CLEAR, COMMIT})

    def test_move_resize_restack_destroy_reuse_and_cancel_mid_commit_repair_pixels(self):
        for phase in (CLIENT, RESTORE, COMMIT):
            with self.subTest(phase=phase):
                self.setUp()
                self.request(Rect(0, 320, 0, 200))
                old = self.reach(phase)
                self.render(old)  # Already drawn pixels must also be repaired.
                # Destroy/reuse handle1, move/resize handle2, restack, reveal4.
                self.assertEqual(self.change(Rect(0, 320, 0, 200)), OK)
                self.windows = [Window(Rect(0, 48, 150, 200), 1, 3, 1),
                                Window(Rect(190, 290, 20, 80), 2, 1, 1),
                                Window(Rect(280, 320, 160, 200), 4, 4, 1)]
                before = bytes(self.shadow)
                self.assertEqual(self.validate(old), STALE)
                self.assertEqual(bytes(self.shadow), before)  # Driver never paints stale work.
                self.drive()
                self.assertEqual(self.shadow, self.expected())
                self.assertEqual(self.screen, self.expected())


if __name__ == '__main__':
    unittest.main()
