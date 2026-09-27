# SPDX-License-Identifier: GPL-3.0-or-later
"""Record semantics; actual cc65 stores are qualified by native drag stress."""
import ctypes
import hashlib
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/services/display/vic_graphics.c"


class OutlineMaskTests(unittest.TestCase):
    def test_preserved_linked_regression_evidence(self):
        report = ROOT / "bench/results/2026-09-27-xwave-drag-freeze"
        artifacts = ROOT / "bench/artifacts/2026-09-27-xwave-drag-freeze"
        for directory in (report, artifacts):
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split(maxsplit=1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        self.assertEqual((report / "raw/baseline-dispatch.bin").read_bytes()[0x15], 0x80)
        self.assertIn("FAIL: stress drag did not finish", (report / "baseline-1986.log").read_text())
        for disk, log in (("d71", "1986-d71-clock.log"), ("d64", "1986-d64-wave.log")):
            page = (report / f"raw/{disk}-dispatch.bin").read_bytes()
            self.assertEqual(page[0x15:0x18], b"\x4C\x00\xC9")
            text = (report / log).read_text()
            self.assertIn("stress 31:", text)
            self.assertIn("row=21", text)
            self.assertIn("PASS: repeated native wave drags and console cancellation", text)
            diagnostics = (report / f"raw/{disk}-diagnostics.bin").read_bytes()
            self.assertEqual(diagnostics[11], 0)  # lifecycle canary failures
            self.assertEqual(diagnostics[0x138], 0)  # no active drag
            self.assertEqual(diagnostics[0x148:0x14C], b"\x20\x00\x20\x00")
            self.assertEqual(diagnostics[0x155], 2)  # foreground wave stopped
            self.assertEqual(diagnostics[0x15C:0x160], b"\x15\x00\x00\x00")
            if disk == "d71":
                self.assertEqual(diagnostics[0x115], 3)  # background clock survived

    def test_reference_compiler_workaround_is_local_to_outline(self):
        body = SOURCE.read_text().split("static void prepare_outline(", 1)[1].split(
            "static unsigned char outline_valid(", 1)[0]
        self.assertIn("~(0x7Fu >> (right & 7u))", body)
        self.assertNotIn("0xFFu <<", body)

    @unittest.skipUnless(shutil.which("cc"), "host C compiler unavailable")
    def test_every_alignment_stays_inside_two_fifteen_byte_records(self):
        source = SOURCE.read_text()
        offset = "static unsigned int bitmap_offset(" + source.split(
            "static unsigned int bitmap_offset(", 1)[1].split(
            "static unsigned int unsigned_magnitude(", 1)[0]
        outline = "static void outline_word(" + source.split(
            "static void outline_word(", 1)[1].split(
            "static unsigned char outline_valid(", 1)[0]
        harness = """
#include <string.h>
unsigned char records[288];
#define OUTLINE_BUFFER (records + 16)
""" + offset + outline + """
void prepare(unsigned char base, unsigned int x, unsigned char y) {
    memset(records, 0xA5, sizeof(records));
    prepare_outline(base, x, y, 168, 104);
}
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "outline.c"
            path.write_text(harness)
            library = Path(directory) / "outline.so"
            subprocess.run(["cc", "-std=c99", "-shared", "-fPIC", "-O2",
                            str(path), "-o", str(library)], check=True,
                           capture_output=True)
            loaded = ctypes.CDLL(str(library))
            loaded.prepare.argtypes = [ctypes.c_ubyte, ctypes.c_uint, ctypes.c_ubyte]
            record = (ctypes.c_ubyte * 288).in_dll(loaded, "records")
            for base in (0, 15):
                for x in range(153):
                    for y in (0, 1, 7, 8, 88, 96):
                        loaded.prepare(base, x, y)
                        data = bytes(record)
                        begin = 16 + base
                        self.assertEqual(data[:begin], b"\xA5" * begin)
                        self.assertEqual(data[begin + 15:], b"\xA5" * (288 - begin - 15))
                        right = x + 167
                        self.assertEqual(data[begin + 6], (0xFF << (7 - (right & 7))) & 255)
                        self.assertEqual(data[begin + 5], 0xFF >> (x & 7))
                        self.assertEqual(data[begin + 4], (right >> 3) - (x >> 3) + 1)
                        self.assertEqual(data[begin + 13], 102)
                        self.assertEqual(data[begin + 14], (y + 1) & 7)


if __name__ == "__main__":
    unittest.main()
