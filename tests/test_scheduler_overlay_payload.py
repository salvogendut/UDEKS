# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_scheduler_overlay import (
    ABI_MAJOR, ABI_MINOR, HEADER_SIZE, LOAD_ADDRESS, MAGIC, build_overlay,
)


def overlay_map(page_size: int = 5, tail_size: int = 7, bss_size: int = 3) -> str:
    page_end = 0x1C00 + page_size - 1
    tail_end = 0xC120 + tail_size - 1
    bss_start = tail_end + 1
    bss_end = bss_start + bss_size - 1
    return (
        "Segment list:\n-------------\nName Start End Size Align\n"
        f"SCHEDULER 001C00 {page_end:06X} {page_size:06X} 00001\n"
        f"CODE 00C120 {tail_end:06X} {tail_size:06X} 00001\n"
        f"BSS {bss_start:06X} {bss_end:06X} {bss_size:06X} 00001\n"
    )


class SchedulerOverlayPayloadTests(unittest.TestCase):
    def test_envelope_records_both_images_bss_and_checksum(self):
        page, tail = b"page!", b"tail123"
        payload, constants = build_overlay(page, tail, overlay_map())
        self.assertEqual(payload[:2], LOAD_ADDRESS.to_bytes(2, "little"))
        header = payload[2 : 2 + HEADER_SIZE]
        self.assertEqual(header[:4], MAGIC)
        self.assertEqual(header[4:6], bytes((ABI_MAJOR, ABI_MINOR)))
        self.assertEqual(int.from_bytes(header[6:8], "little"), 0x1C00)
        self.assertEqual(int.from_bytes(header[8:10], "little"), len(page))
        self.assertEqual(int.from_bytes(header[10:12], "little"), 0xC120)
        self.assertEqual(int.from_bytes(header[12:14], "little"), len(tail))
        self.assertEqual(int.from_bytes(header[14:16], "little"), 0xC127)
        self.assertEqual(int.from_bytes(header[16:18], "little"), 3)
        self.assertEqual(
            int.from_bytes(header[18:20], "little"),
            (sum(page) + sum(tail)) & 0xFFFF,
        )
        self.assertEqual(payload[2 + HEADER_SIZE :], page + tail)
        self.assertIn("SCHEDULER_OVERLAY_TAIL_SOURCE = $5019", constants)
        self.assertIn("SCHEDULER_OVERLAY_END = $5020", constants)

    def test_map_and_image_drift_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected \\$1C00"):
            build_overlay(
                b"page!", b"tail123", overlay_map().replace("001C00", "001C01")
            )
        with self.assertRaisesRegex(ValueError, "page image"):
            build_overlay(b"short", b"tail123", overlay_map(page_size=6))
        with self.assertRaisesRegex(ValueError, "tail image"):
            build_overlay(b"page!", b"short", overlay_map(tail_size=6))
        with self.assertRaisesRegex(ValueError, "reaches \\$CE00"):
            build_overlay(b"p", b"t", overlay_map(1, 1, 0x0CE0))

    def test_init_registers_ush_through_the_fixed_overlay_gate(self):
        scheduler = (ROOT / "src/scheduler/scheduler.s").read_text(
            encoding="utf-8"
        ).lower()
        init = (ROOT / "src/services/init/descriptor.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn(
            "_udeks_scheduler_lifecycle_bootstrap_gate = $1c1e", scheduler
        )
        self.assertIn("jsr _udeks_lifecycle_bootstrap", scheduler)
        self.assertIn("jsr $ff10", scheduler)
        self.assertIn("jmp $ff13", scheduler)
        self.assertIn("lifecycle_bootstrap     = $1c1e", init)
        load = init.index("jsr persistent_load")
        bootstrap = init.index("jsr lifecycle_bootstrap", load)
        self.assertLess(load, bootstrap)
        self.assertNotIn("jsr task_bank_reset", init)


if __name__ == "__main__":
    unittest.main()
