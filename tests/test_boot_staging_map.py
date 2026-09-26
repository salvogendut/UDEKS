# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from boot_staging_map import analyze, free_holes, staged_regions


# Synthetic map mirroring the 2026-09-26 layout: the sequential shadow at
# $AB2D-$CA6C and the two remaining boot-only objects.
FIXTURE = """\
Modules list:
-------------
hardware_capability.o:
    CODE              Offs=000000  Size=0003C7  Align=00001  Fill=0000
    BSS               Offs=000000  Size=000001  Align=00001  Fill=0000
boot_console.o:
    CODE              Offs=000000  Size=00038F  Align=00001  Fill=0000
    RODATA            Offs=000000  Size=00021B  Align=00001  Fill=0000

Segment list:
-------------
Name                   Start     End    Size  Align
----------------------------------------------------
VICSHADOW             00AB2D  00CA6C  001F40  00001

"""

# stage0's last nonzero byte is at $0B3D.
STAGE0 = bytes(0x3D) + b"\x01"


class BootStagingMapTests(unittest.TestCase):
    def test_staged_regions_are_disjoint(self):
        regions = sorted(staged_regions(), key=lambda region: region.start)
        for first, second in zip(regions, regions[1:]):
            self.assertLess(first.end, second.start)

    def test_free_hole_arithmetic_is_byte_accurate(self):
        holes = free_holes(0xAB2D, 0x0B3D)
        self.assertEqual(
            holes,
            [
                ("staging hole", 0xAB2D, 0xACFF),
                ("staging hole", 0xC409, 0xC4EE),
                ("staging hole", 0xCDF0, 0xCDFF),
                ("staging hole", 0xCECB, 0xCEFF),
                ("boot-sector hole", 0x0B3E, 0x0BFF),
            ],
        )
        total = sum(end - start + 1 for _, start, end in holes)
        largest = max(end - start + 1 for _, start, end in holes)
        self.assertEqual(total, 960)
        self.assertEqual(largest, 467)

    def test_remaining_boot_objects_are_blocked(self):
        result = analyze(FIXTURE, STAGE0)
        self.assertEqual(result["objects"]["hardware_capability.o"], 968)
        self.assertEqual(result["objects"]["boot_console.o"], 1450)
        self.assertEqual(result["hole_total"], 960)
        self.assertEqual(result["largest_hole"], 467)
        for name in ("hardware_capability.o", "boot_console.o"):
            self.assertFalse(result["fits"][name]["single_hole"])
            self.assertFalse(result["fits"][name]["aggregate"])


if __name__ == "__main__":
    unittest.main()
