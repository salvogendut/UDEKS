# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from boot_staging_map import analyze, free_holes, staged_regions


# Synthetic map mirroring the 2026-09-26 layout: the sequential shadow at
# $AB2D-$CA6C, the staged boot pages, and the two remaining boot-only objects.
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
PROBECODE             000B00  000BD0  0000D1  00001
STARTUP               001C00  001CCE  0000CF  00001
VICSHADOW             00AB2D  00CA6C  001F40  00001

"""

# Emitted staging artifacts, byte-accurate for the 2026-09-26 build.
EMITTED = {
    "bootfs": 11707,
    "module": 836,
    "task_request": 265,
    "bootfs_request": 667,
    "task_loader": 1520,
    "task_gate": 203,
}

# stage0's last nonzero byte is at $0B3D.
STAGE0 = bytes(0x3D) + b"\x01"


class BootStagingMapTests(unittest.TestCase):
    def test_copied_ranges_are_disjoint_or_nested(self):
        regions = sorted(staged_regions({**EMITTED, "probe": 209, "crt0": 207}),
                         key=lambda region: region.start)
        for index, first in enumerate(regions):
            for second in regions[index + 1:]:
                disjoint = first.copied_end < second.start
                nested = (
                    first.start <= second.start
                    and second.copied_end <= first.copied_end
                )
                self.assertTrue(
                    disjoint or nested,
                    f"{first.name} partially overlaps {second.name}",
                )

    def test_free_hole_arithmetic_is_byte_accurate(self):
        regions = staged_regions({**EMITTED, "probe": 209, "crt0": 207})
        holes = free_holes(0xAB2D, 0x0B3D, regions)
        self.assertEqual(
            holes,
            [
                ("staging hole", 0xAB2D, 0xACFF),
                ("staging hole", 0xC409, 0xC4EE),
                ("staging hole", 0xC78A, 0xC7FF),
                ("staging hole", 0xCDF0, 0xCDFF),
                ("staging hole", 0xCECB, 0xCEFF),
                ("boot-sector hole", 0x0B3E, 0x0BFF),
            ],
        )
        total = sum(end - start + 1 for _, start, end in holes)
        largest = max(end - start + 1 for _, start, end in holes)
        self.assertEqual(total, 1078)
        self.assertEqual(largest, 467)

    def test_objects_are_measured_as_staged_and_runtime(self):
        result = analyze(FIXTURE, STAGE0, EMITTED)
        self.assertEqual(
            result["objects"]["hardware_capability.o"],
            {"staged": 967, "runtime": 968},
        )
        self.assertEqual(
            result["objects"]["boot_console.o"],
            {"staged": 1450, "runtime": 1450},
        )
        self.assertEqual(result["hole_total"], 1078)
        self.assertEqual(result["largest_hole"], 467)
        self.assertFalse(
            result["fits"]["hardware_capability.o"]["single_hole"]
        )
        self.assertTrue(
            result["fits"]["hardware_capability.o"]["aggregate"]
        )
        self.assertFalse(result["fits"]["boot_console.o"]["single_hole"])
        self.assertFalse(result["fits"]["boot_console.o"]["aggregate"])

    def test_dead_padding_is_reported_separately(self):
        result = analyze(FIXTURE, STAGE0, EMITTED)
        padding = {item["name"]: item for item in result["padding"]}
        self.assertEqual(padding["probe staging"]["size"], 47)
        self.assertEqual(padding["crt0 staging"]["size"], 49)
        self.assertEqual(padding["module staging"]["size"], 1)
        self.assertNotIn("bootfs tail staging", padding)
        unowned = {name: end - start + 1 for name, start, end, _ in
                   result["unowned_padding"]}
        self.assertEqual(unowned["stage-1 code padding"], 21)
        self.assertEqual(unowned["z80 tail padding"], 105)


if __name__ == "__main__":
    unittest.main()
