# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("input_smoke", ROOT / "tools/1986_input_smoke_build.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class InputSmokeTests(unittest.TestCase):
    def test_build_uses_machine_sources_without_frontend_main(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Makefile.am").write_text(
                "1986_SOURCES = src/main.c \\\n src/c128.c src/kbd.c\nnoinst_HEADERS = src/c128.h\n")
            self.assertEqual(smoke.emulator_sources(root), [root / "src/c128.c", root / "src/kbd.c"])

    def test_slot_binding_is_measured_from_map(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "overlay.map"
            path.write_text("_udeks_lifecycle_slots_private 00C7D9 RLA\n")
            self.assertEqual(smoke.slot_address(path), "0x00C7D9")
            path.write_text("_udeks_lifecycle_slots_private 00C7D9 REA\n")
            with self.assertRaises(ValueError):
                smoke.slot_address(path)

    def test_guest_input_is_not_injected_into_queues_or_requests(self):
        source = (ROOT / "tools/1986_input_smoke.c").read_text()
        self.assertNotIn("c128_mem_write", source)
        self.assertNotIn("machine->mem.ram[address] =", source)
        self.assertIn("c128_key_event", source)
        self.assertIn("joyports_mouse_motion", source)
        self.assertIn("joyports_mouse_button", source)
        self.assertIn("typed submission differs", source)
        self.assertIn("history submitted different text", source)
        self.assertIn("Ctrl+C stopped background clock", source)

    def test_drag_stress_covers_partial_cached_render_and_dispatcher_integrity(self):
        source = (ROOT / "tools/1986_input_smoke.c").read_text()
        self.assertIn("stress must start during partial painting", source)
        self.assertIn("wait_byte(0xF27A, 21", source)
        self.assertIn("outline preparation corrupted lifecycle dispatcher", source)
        self.assertIn("drag release corrupted lifecycle dispatcher", source)
        self.assertIn("cached drag reacquired Z80", source)
        self.assertIn("stress Ctrl+C did not stop wave", source)
        self.assertIn('command("echo console alive")', source)

    def test_preserved_input_evidence_is_complete_and_hash_verified(self):
        report = ROOT / "bench/results/2026-09-27-event-waits-1986"
        artifacts = ROOT / "bench/artifacts/2026-09-27-event-waits-input"
        for directory in (report, artifacts):
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split(maxsplit=1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        for disk in ("d71", "d64"):
            record = (report / "raw" / f"{disk}-diagnostics.bin").read_bytes()
            self.assertEqual(len(record), 400)
            self.assertEqual(record[:4], b"UTSK")
            self.assertEqual(record[11], 0)  # no lifecycle canary failures
            self.assertEqual(record[0x5c:0x5e], b"\x01\x00")  # history recall
            self.assertEqual(record[0x115], 3)  # background clock running
            self.assertEqual(record[0x155], 2)  # foreground wave stopped
            self.assertEqual(record[0x148:0x14a], b"\x01\x00")  # drag starts
            self.assertEqual(record[0x14a:0x14c], b"\x01\x00")  # drag finishes
            slots = (report / "raw" / f"{disk}-slots.bin").read_bytes()
            self.assertEqual(len(slots), 64)
            self.assertEqual(slots[1:3], b"\x04\x02")  # WAITING for INPUT
            self.assertIn("PASS:", (report / f"1986-input-smoke-{disk}.log").read_text())


if __name__ == "__main__":
    unittest.main()
