# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def c_defines(path: Path) -> dict[str, int]:
    values = {}
    pattern = re.compile(r"^#define\s+(UDEKS_[A-Z0-9_]+)\s+(0x[0-9A-Fa-f]+)(?:u|ul)?$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = int(match.group(2), 16)
    return values


def asm_defines(path: Path) -> dict[str, int]:
    values = {}
    pattern = re.compile(r"^(UDEKS_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = int(match.group(2), 16)
    return values


class MemoryMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.memory = c_defines(ROOT / "include/udeks/memory.h")

    def test_primary_regions_are_ordered_and_non_overlapping(self):
        memory = self.memory
        self.assertLess(memory["UDEKS_BOOT_SECTOR_BASE"], memory["UDEKS_BOOTSTRAP_BASE"])
        self.assertEqual(
            memory["UDEKS_RECLAIMED_STATE_BASE"],
            memory["UDEKS_BOOT_SECTOR_BASE"] + 0x100,
        )
        self.assertEqual(
            memory["UDEKS_RECLAIMED_STATE_LIMIT"],
            memory["UDEKS_APP2_BASE"],
        )
        self.assertEqual(memory["UDEKS_APP1_LIMIT"], memory["UDEKS_RECLAIMED_STATE_BASE"])
        self.assertEqual(memory["UDEKS_APP2_LIMIT"], memory["UDEKS_BOOTSTRAP_BASE"])
        self.assertLess(memory["UDEKS_BOOTSTRAP_BASE"], memory["UDEKS_KERNEL_BASE"])
        self.assertLess(memory["UDEKS_KERNEL_BASE"], memory["UDEKS_KERNEL_LIMIT"])
        self.assertEqual(memory["UDEKS_KERNEL_LIMIT"], memory["UDEKS_IO_BASE"])
        self.assertEqual(memory["UDEKS_IO_LIMIT"], memory["UDEKS_KERNEL_HIGH_BASE"])
        self.assertEqual(memory["UDEKS_KERNEL_HIGH_LIMIT"], memory["UDEKS_COMMON_BASE"])
        self.assertEqual(
            memory["UDEKS_COMMON_BASE"] + memory["UDEKS_COMMON_SIZE"],
            memory["UDEKS_COMMON_LIMIT"],
        )

    def test_common_region_contains_protocol_and_hardware_windows(self):
        memory = self.memory
        common_base = memory["UDEKS_COMMON_BASE"]
        common_limit = memory["UDEKS_COMMON_LIMIT"]
        for name in (
            "UDEKS_GATEWAY_BASE",
            "UDEKS_MMU_MIRROR_BASE",
            "UDEKS_HANDOFF_BASE",
            "UDEKS_VECTOR_BASE",
        ):
            self.assertGreaterEqual(memory[name], common_base)
            self.assertLess(memory[name], common_limit)
        self.assertEqual(memory["UDEKS_MMU_MIRROR_LIMIT"] - memory["UDEKS_MMU_MIRROR_BASE"], 5)

    def test_worker_and_vic_reservations_do_not_overlap(self):
        memory = self.memory
        self.assertLessEqual(memory["UDEKS_Z80_CODE_LIMIT"], memory["UDEKS_VIC_WINDOW_BASE"])
        self.assertLess(memory["UDEKS_VIC_WINDOW_BASE"], memory["UDEKS_VIC_WINDOW_LIMIT"])
        self.assertEqual(memory["UDEKS_VIC_WINDOW_LIMIT"] - memory["UDEKS_VIC_WINDOW_BASE"], 0x4000)
        self.assertLess(memory["UDEKS_Z80_STACK_TOP"], memory["UDEKS_COMMON_BASE"])

    def test_initial_c_stack_uses_reserved_kernel_high_ram(self):
        memory = self.memory
        self.assertEqual(
            memory["UDEKS_VIC_ROW_TABLE_BASE"],
            memory["UDEKS_KERNEL_HIGH_BASE"],
        )
        self.assertEqual(
            memory["UDEKS_VIC_ROW_TABLE_LIMIT"],
            memory["UDEKS_VIC_DIRTY_MAP_BASE"],
        )
        self.assertEqual(
            memory["UDEKS_VIC_DIRTY_MAP_LIMIT"],
            memory["UDEKS_VIC_CLIP_STATE_BASE"],
        )
        self.assertEqual(
            memory["UDEKS_VIC_CLIP_STATE_LIMIT"],
            memory["UDEKS_MODULE_HIGH_BSS_BASE"],
        )
        self.assertEqual(
            memory["UDEKS_MODULE_HIGH_BSS_LIMIT"],
            memory["UDEKS_C_STACK_BOTTOM"],
        )
        self.assertLess(memory["UDEKS_C_STACK_BOTTOM"], memory["UDEKS_C_STACK_TOP"])
        self.assertGreaterEqual(
            memory["UDEKS_C_STACK_TOP"], memory["UDEKS_KERNEL_HIGH_BASE"]
        )
        self.assertLess(memory["UDEKS_C_STACK_TOP"], memory["UDEKS_KERNEL_HIGH_LIMIT"])

    def test_assembly_mmu_profiles_match_c_contract(self):
        assembly = asm_defines(ROOT / "src/8502/mmu.inc")
        for name in (
            "UDEKS_MMU_KERNEL_IO",
            "UDEKS_MMU_KERNEL_FLAT",
            "UDEKS_MMU_WORKER_IO",
            "UDEKS_MMU_WORKER_FLAT",
            "UDEKS_MMU_RCR_TOP_4K",
        ):
            self.assertEqual(assembly[name], self.memory[name])

    def test_linker_kernel_region_matches_public_contract(self):
        linker = (ROOT / "cfg/8502-bootstrap.cfg").read_text(encoding="utf-8")
        match = re.search(
            r"KERNEL:\s+start\s*=\s*\$([0-9A-Fa-f]+),\s*"
            r"size\s*=\s*\$([0-9A-Fa-f]+)",
            linker,
        )
        self.assertIsNotNone(match)
        start = int(match.group(1), 16)
        size = int(match.group(2), 16)
        self.assertEqual(start, self.memory["UDEKS_KERNEL_BASE"])
        self.assertEqual(start + size, self.memory["UDEKS_KERNEL_LIMIT"])
        low = re.search(
            r"LOWMEM:\s+start\s*=\s*\$([0-9A-Fa-f]+),\s*"
            r"size\s*=\s*\$([0-9A-Fa-f]+)",
            linker,
        )
        self.assertIsNotNone(low)
        low_start = int(low.group(1), 16)
        low_size = int(low.group(2), 16)
        self.assertEqual(low_start, self.memory["UDEKS_RECLAIMED_STATE_BASE"])
        self.assertEqual(
            low_start + low_size,
            self.memory["UDEKS_RECLAIMED_STATE_LIMIT"],
        )
        for region, base_name, limit_name in (
            ("APP1", "UDEKS_APP1_BASE", "UDEKS_APP1_LIMIT"),
            ("APP2", "UDEKS_APP2_BASE", "UDEKS_APP2_LIMIT"),
        ):
            app = re.search(
                rf"{region}:\s+start\s*=\s*\$([0-9A-Fa-f]+),\s*"
                rf"size\s*=\s*\$([0-9A-Fa-f]+)",
                linker,
            )
            self.assertIsNotNone(app)
            app_start = int(app.group(1), 16)
            app_size = int(app.group(2), 16)
            self.assertEqual(app_start, self.memory[base_name])
            self.assertEqual(app_start + app_size, self.memory[limit_name])
        high = re.search(
            r"HIGHMEM:\s+start\s*=\s*\$([0-9A-Fa-f]+),\s*"
            r"size\s*=\s*\$([0-9A-Fa-f]+)",
            linker,
        )
        self.assertIsNotNone(high)
        high_start = int(high.group(1), 16)
        high_size = int(high.group(2), 16)
        self.assertEqual(high_start, self.memory["UDEKS_MODULE_HIGH_BSS_BASE"])
        self.assertEqual(
            high_start + high_size, self.memory["UDEKS_MODULE_HIGH_BSS_LIMIT"]
        )


if __name__ == "__main__":
    unittest.main()
